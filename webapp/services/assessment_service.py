"""技能测评服务:按技能聚合出题 → 判分定级 → Evidence 落档 → 联动推荐。

与课程结业测验(learning_service)的分工:
- 课程测验:学完一门课的验收,驱动等级变化(学习闭环);
- 技能测评:对一项技能的独立能力度量,作为可解释 Evidence 展示,
  并联动推荐补强课程(「测评为镜,课程为梯」)。
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from profile.__main__ import DEFAULT_DATA_DIR

from webapp.services.assessment_store import (
    PostgresAssessmentStore,
    SkillAssessment,
)

EXCELLENT_THRESHOLD = 85
PASS_THRESHOLD = 70
QUESTIONS_PER_ASSESSMENT = 5


def _load_courses() -> list[dict[str, Any]]:
    data = json.loads((Path(DEFAULT_DATA_DIR) / "courses.json").read_text("utf-8"))
    return data.get("courses", data) if isinstance(data, dict) else data


def _load_skills() -> list[dict[str, Any]]:
    data = json.loads((Path(DEFAULT_DATA_DIR) / "skills.json").read_text("utf-8"))
    return data.get("skills", data) if isinstance(data, dict) else data


def assessable_skills(employee_id: str) -> list[dict[str, Any]]:
    """可测评的技能列表(附员工当前等级与最近测评)。"""
    from feedback import build_feedback_state
    from feedback.store import PostgresTrainingStore

    store = PostgresTrainingStore()
    store.ensure_schema()
    state = build_feedback_state(store, employee_id)
    store.close()

    skill_by_name = {s["name"]: s for s in _load_skills()}
    current_levels = {
        info.skill_id: info.level for info in state.profile.skills.values()
    }
    name_by_id = {
        s["skill_id"]: s["name"] for s in _load_skills()
    }

    assessments = PostgresAssessmentStore()
    assessments.ensure_schema()
    history = {a.skill_id: a for a in assessments.list_for(employee_id)}
    assessments.close()

    # 可测评 = 有课程在教这门技能(有出题素材)
    teachable: dict[str, list[str]] = {}
    for course in _load_courses():
        for skill in course.get("skills", []):
            sid = skill if isinstance(skill, str) else skill.get("skill_id", "")
            teachable.setdefault(sid, []).append(course["name"])

    result = []
    for sid, courses in teachable.items():
        name = name_by_id.get(sid, sid)
        skill_meta = skill_by_name.get(name, {})
        last = history.get(sid)
        result.append(
            {
                "skill_id": sid,
                "skill_name": name,
                "category": skill_meta.get("category", ""),
                "current_level": current_levels.get(sid, 0),
                "course_count": len(courses),
                "last_score": last.score if last else None,
                "last_verdict": last.verdict if last else None,
                "last_at": last.assessed_at if last else None,
            }
        )
    result.sort(key=lambda s: (-s["current_level"] == 0, -s["course_count"]))
    return result


def build_skill_questions(skill_id: str) -> list[dict[str, Any]]:
    """为技能生成测评题:教这门技能的课程学习目标(确定性,答案不下发)。

    题型:「掌握《课程》应达到以下哪项能力?」正确项为该课程目标,
    干扰项取自其他课程目标。
    """
    courses = _load_courses()
    name_by_id = {s["skill_id"]: s["name"] for s in _load_skills()}
    skill_name = name_by_id.get(skill_id, skill_id)

    teaching = [
        c for c in courses
        if any(
            (s if isinstance(s, str) else s.get("skill_id")) == skill_id
            for s in c.get("skills", [])
        )
    ]
    if not teaching:
        raise KeyError(f"该技能暂无课程支撑,无法测评:{skill_name}")

    others: list[tuple[str, str]] = []  # (course_name, objective)
    for c in courses:
        if c in teaching:
            continue
        for o in c.get("learning_objectives", []):
            others.append((c["name"], o.strip()))

    rng = random.Random(f"assess-{skill_id}")
    questions: list[dict[str, Any]] = []
    for i, course in enumerate(teaching[:QUESTIONS_PER_ASSESSMENT]):
        objectives = [o.strip() for o in course.get("learning_objectives", []) if o.strip()]
        if not objectives:
            continue
        correct = objectives[i % len(objectives)]
        distractors = [o for _, o in others if o != correct]
        rng.shuffle(distractors)
        options = distractors[:3] + [correct]
        rng.shuffle(options)
        questions.append(
            {
                "index": len(questions) + 1,
                "question": f"学习《{course['name']}》后,应达到以下哪项能力?",
                "options": options,
                "answer_index": options.index(correct),
            }
        )
    if not questions:
        raise KeyError(f"课程缺少学习目标,无法出题:{skill_name}")
    return questions


def grade_assessment(
    employee_id: str, skill_id: str, answers: list[int]
) -> dict[str, Any]:
    """判分 → 定级(excellent/passed/failed)→ 落档 → 联动推荐。"""
    questions = build_skill_questions(skill_id)
    if len(answers) != len(questions):
        raise ValueError("答案数量与题目不一致")

    correct = sum(
        1
        for q, a in zip(questions, answers)
        if 0 <= a < len(q["options"]) and a == q["answer_index"]
    )
    score = round(100 * correct / len(questions))
    if score >= EXCELLENT_THRESHOLD:
        verdict = "excellent"
        verdict_label = "优秀"
    elif score >= PASS_THRESHOLD:
        verdict = "passed"
        verdict_label = "通过"
    else:
        verdict = "failed"
        verdict_label = "未通过"

    name_by_id = {s["skill_id"]: s["name"] for s in _load_skills()}
    skill_name = name_by_id.get(skill_id, skill_id)

    store = PostgresAssessmentStore()
    store.ensure_schema()
    store.add(
        SkillAssessment(
            employee_id=employee_id,
            skill_id=skill_id,
            skill_name=skill_name,
            score=score,
            verdict=verdict,
            correct=correct,
            total=len(questions),
            assessed_at="",
        )
    )

    # 联动推荐:未达标 → 推荐教这门技能的课程
    recommended: list[str] = []
    if verdict == "failed":
        for course in _load_courses():
            if any(
                (s if isinstance(s, str) else s.get("skill_id")) == skill_id
                for s in course.get("skills", [])
            ):
                recommended.append(course["name"])
    store.close()

    message = {
        "excellent": "能力扎实,可以考虑挑战更高阶的岗位要求。",
        "passed": "基本掌握,建议结合课程查漏补缺。",
        "failed": "建议先完成推荐课程,再回来测评。",
    }[verdict]

    return {
        "skill_name": skill_name,
        "score": score,
        "verdict": verdict,
        "verdict_label": verdict_label,
        "correct": correct,
        "total": len(questions),
        "message": message,
        "recommended_courses": recommended[:3],
    }


def assessment_history(employee_id: str) -> list[dict[str, Any]]:
    """员工的测评历史(画像 Evidence 展示用)。"""
    store = PostgresAssessmentStore()
    store.ensure_schema()
    records = store.list_for(employee_id)
    store.close()
    return [
        {
            "skill_name": r.skill_name,
            "score": r.score,
            "verdict_label": {"excellent": "优秀", "passed": "通过", "failed": "未通过"}[r.verdict],
            "at": r.assessed_at,
        }
        for r in records
    ]


def team_assessment_stats() -> dict[str, Any]:
    """HR 端:团队测评统计。"""
    store = PostgresAssessmentStore()
    store.ensure_schema()
    records = store.list_all()
    store.close()
    if not records:
        return {"total": 0, "average_score": None, "pass_rate": None, "by_skill": []}

    scores = [r.score for r in records]
    by_skill: dict[str, list[int]] = {}
    for r in records:
        by_skill.setdefault(r.skill_name, []).append(r.score)
    skill_stats = sorted(
        (
            {
                "skill": name,
                "attempts": len(scores_),
                "average": round(sum(scores_) / len(scores_)),
                "pass_rate": round(100 * sum(1 for s in scores_ if s >= PASS_THRESHOLD) / len(scores_)),
            }
            for name, scores_ in by_skill.items()
        ),
        key=lambda s: -s["attempts"],
    )
    return {
        "total": len(records),
        "average_score": round(sum(scores) / len(scores)),
        "pass_rate": round(100 * sum(1 for s in scores if s >= PASS_THRESHOLD) / len(scores)),
        "by_skill": skill_stats[:8],
    }
