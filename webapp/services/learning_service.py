"""站内学习服务:课程内容 → 单元进度 → 结业测验 → 自动记录。

闭环:员工在站内读单元(learning_store 记进度)→ 全部读完解锁
结业测验(题目从课程学习目标确定性生成)→ 达标(≥70%)自动调用
feedback.record_completion 写入培训记录并触发画像/差距/课表重算。
员工全程不离开平台,也不手填任何分数。
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from profile.__main__ import DEFAULT_DATA_DIR

from webapp.services.learning_store import PostgresLearningProgressStore

LEARNING_DIR = Path(DEFAULT_DATA_DIR).parent / "learning"
PASS_THRESHOLD_PERCENT = 70


@dataclass(frozen=True)
class UnitView:
    """课程的一个单元(站内学习视图)。"""

    index: int
    title: str
    paragraphs: list[str]
    completed: bool


@dataclass(frozen=True)
class CourseLearningView:
    """一门课的站内学习视图。"""

    course_id: str
    course_name: str
    units: list[UnitView]
    completed_units: int
    total_units: int
    quiz_unlocked: bool
    already_passed: bool


@dataclass(frozen=True)
class QuizQuestion:
    """一道结业测验题(从学习目标生成)。"""

    index: int
    question: str
    options: list[str]
    answer_index: int  # 服务端持有,不下发


def _load_course(course_id: str) -> dict[str, Any]:
    data = json.loads((Path(DEFAULT_DATA_DIR) / "courses.json").read_text("utf-8"))
    items = data.get("courses", data) if isinstance(data, dict) else data
    for course in items:
        if course["course_id"] == course_id:
            return course
    raise KeyError(f"课程不存在:{course_id}")


def _load_learning_markdown(course_id: str) -> str | None:
    for path in sorted(LEARNING_DIR.glob(f"{course_id}-*.md")):
        return path.read_text("utf-8")
    return None


def _parse_units(markdown: str) -> list[tuple[str, list[str]]]:
    """标题级 Markdown → [(单元标题, [段落])](与 RAG 分块策略同构)。"""
    units: list[tuple[str, list[str]]] = []
    current_title = None
    current_paras: list[str] = []
    for block in markdown.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("## "):
            if current_title is not None:
                units.append((current_title, current_paras))
            current_title = block[3:].strip()
            current_paras = []
        elif current_title is not None:
            current_paras.append(block)
    if current_title is not None:
        units.append((current_title, current_paras))
    return units


def build_course_learning(employee_id: str, course_id: str) -> CourseLearningView:
    """组装站内学习视图:单元内容 + 我的进度 + 测验解锁状态。"""
    from feedback.store import PostgresTrainingStore

    course = _load_course(course_id)
    markdown = _load_learning_markdown(course_id)
    if markdown is None:
        raise FileNotFoundError(f"课程内容未就绪(先运行 python -m crawler run-units):{course_id}")

    progress = PostgresLearningProgressStore()
    progress.ensure_schema()
    done = set(progress.completed_units(employee_id, course_id))

    training = PostgresTrainingStore()
    training.ensure_schema()
    already_passed = any(
        r.course_id == course_id and r.passed
        for r in training.list_records(employee_id)
    )
    training.close()

    units = [
        UnitView(
            index=i + 1,
            title=title,
            paragraphs=paras,
            completed=(i + 1) in done,
        )
        for i, (title, paras) in enumerate(_parse_units(markdown))
    ]
    completed_count = sum(1 for u in units if u.completed)
    return CourseLearningView(
        course_id=course_id,
        course_name=course["name"],
        units=units,
        completed_units=completed_count,
        total_units=len(units),
        quiz_unlocked=completed_count == len(units) and len(units) > 0,
        already_passed=already_passed,
    )


def mark_unit_complete(employee_id: str, course_id: str, unit_index: int) -> dict[str, Any]:
    """标记单元完成,返回最新进度(全部完成时提示测验解锁)。"""
    progress = PostgresLearningProgressStore()
    progress.ensure_schema()
    progress.mark_unit(employee_id, course_id, unit_index)
    view = build_course_learning(employee_id, course_id)
    return {
        "unit_index": unit_index,
        "completed_units": view.completed_units,
        "total_units": view.total_units,
        "quiz_unlocked": view.quiz_unlocked,
    }


def build_quiz(course_id: str) -> list[dict[str, Any]]:
    """从学习目标确定性生成结业测验(不下发答案)。

    每题:「以下哪项是《课程》的学习目标?」正确项为本课程目标,
    干扰项取自其他课程的目标(确定性随机,可复现)。
    """
    data = json.loads((Path(DEFAULT_DATA_DIR) / "courses.json").read_text("utf-8"))
    items = data.get("courses", data) if isinstance(data, dict) else data
    by_id = {c["course_id"]: c for c in items}
    course = by_id.get(course_id)
    if course is None:
        raise KeyError(f"课程不存在:{course_id}")

    objectives = [o.strip() for o in course.get("learning_objectives", []) if o.strip()]
    if not objectives:
        objectives = [course["description"].strip()]

    others: list[str] = []
    for cid, c in by_id.items():
        if cid == course_id:
            continue
        others.extend(o.strip() for o in c.get("learning_objectives", []) if o.strip())
    rng = random.Random(course_id)  # 确定性:同课程同题目
    rng.shuffle(others)

    questions: list[dict[str, Any]] = []
    for i, objective in enumerate(objectives[:5]):
        distractors = others[i * 2 : i * 2 + 3][:3]
        while len(distractors) < 3 and others:
            candidate = others[len(distractors) % len(others)]
            if candidate not in distractors and candidate != objective:
                distractors.append(candidate)
        options = distractors + [objective]
        rng.shuffle(options)
        questions.append(
            {
                "index": i + 1,
                "question": f"以下哪项是《{course['name']}》的学习目标?",
                "options": options,
                "answer_index": options.index(objective),  # 仅服务端持有
            }
        )
    return questions


def grade_quiz(
    employee_id: str, course_id: str, answers: list[int]
) -> dict[str, Any]:
    """判卷;达标(≥70%)自动写入培训记录并触发反馈闭环。

    返回产品语义:得分、是否通过、等级变化、下一步建议——
    员工不需要也不应该手动登记任何分数。
    """
    from feedback import record_completion
    from feedback.store import PostgresTrainingStore
    from skillbridge.db import neo4j_driver

    questions = build_quiz(course_id)
    if len(answers) != len(questions):
        raise ValueError("答案数量与题目不一致")

    correct = sum(
        1
        for q, a in zip(questions, answers)
        if 0 <= a < len(q["options"]) and a == q["answer_index"]
    )
    score = round(100 * correct / len(questions)) if questions else 0
    passed = score >= PASS_THRESHOLD_PERCENT

    result: dict[str, Any] = {
        "score": score,
        "correct": correct,
        "total": len(questions),
        "passed": passed,
        "changes": [],
        "suggestions": [],
    }
    if not passed:
        result["message"] = "未达到结业标准(70 分),建议复习单元内容后重考。"
        return result

    store = PostgresTrainingStore()
    store.ensure_schema()
    driver = neo4j_driver()
    try:
        driver.verify_connectivity()
        completion = record_completion(
            driver, store, employee_id, course_id, exam_score=score, source="in_app"
        )
    finally:
        driver.close()

    result["changes"] = [
        {
            "skill": c.skill_name,
            "from_level": c.from_level,
            "to_level": c.to_level,
        }
        for c in completion.update.changes
    ]
    result["suggestions"] = [
        {"course": s.course_name, "reason": s.reason}
        for s in completion.record.suggestions
    ]
    result["message"] = "恭喜完成课程!学习记录已自动登记,能力画像与课表已更新。"
    return result
