"""员工视角服务:把算法模块的输出组装成产品视图。

只做「组合与翻译」,不重复实现任何业务逻辑:
- 画像/差距 → profile 模块
- 推荐理由的转译 → recommendation 模块的 reasons
- 周计划 → learning_path 模块(只取重排后的当前计划)
- 进度 → feedback 模块的回放状态
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from feedback import build_feedback_state
from feedback.store import PostgresTrainingStore
from learning_path import generate_learning_path
from profile import build_gap_report
from profile.__main__ import DEFAULT_DATA_DIR
from recommendation import recommend_courses
from skillbridge.db import neo4j_driver

from webapp.services.viewmodels import (
    CourseCardView,
    EmployeeHomeView,
    GapView,
    ProgressView,
    SkillView,
    WeekPlanView,
    duration_label,
    readiness_percent,
)


def _load_employee_record(employee_id: str) -> dict[str, Any]:
    import json

    data = json.loads((Path(DEFAULT_DATA_DIR) / "employees.json").read_text("utf-8"))
    for record in data["employees"]:
        if record["employee_id"] == employee_id:
            return record
    raise KeyError(f"员工不存在:{employee_id}")


def _skill_status(level: int, required: int | None) -> str:
    if required is None:
        return "extra"
    if level >= required:
        return "met"
    if level == 0:
        return "missing"
    return "learning"


def build_employee_home(employee_id: str, *, hours: float = 4.0, weeks: int = 8) -> EmployeeHomeView:
    """一次组装员工端首页全部数据。

    算法细节(向量分、加权差距、gap_ratio)在此全部吸收,
    返回的视图模型只含产品语义。
    """
    record = _load_employee_record(employee_id)
    store = PostgresTrainingStore()
    store.ensure_schema()
    state = build_feedback_state(store, employee_id)
    gap = state.gap_after

    # 技能视图:当前等级 + 目标岗位要求
    required_levels: dict[str, int] = {}
    for g in gap.gaps:
        required_levels[g.skill_name] = g.required_level
    for m in gap.met:
        required_levels[m.skill_name] = m.required_level
    skills = [
        SkillView(
            name=name,
            level=info.level,
            required_level=required_levels.get(name),
            status=_skill_status(info.level, required_levels.get(name)),
        )
        for name, info in state.profile.skills.items()
    ]

    # 差距视图:只保留产品语义(是否核心、一句话建议)
    top_gaps = [
        GapView(
            skill=g.skill_name,
            current=g.current_level,
            required=g.required_level,
            is_core=(g.importance or 0) >= 5,
            suggestion="建议优先安排学习" if (g.importance or 0) >= 5 else "按计划逐步提升",
        )
        for g in gap.gaps
    ]

    driver = neo4j_driver()
    try:
        driver.verify_connectivity()
        rec_report = recommend_courses(driver, state.profile, gap, top_k=5)
        path_report = generate_learning_path(
            driver,
            state.profile,
            gap,
            hours_per_week=hours,
            deadline_weeks=weeks,
            completed=tuple(state.update.passed_course_ids),
        )
    finally:
        driver.close()

    # 推荐卡片:评分小数吸收为顺序,理由保留纯文字
    recommendations = [
        CourseCardView(
            name=r.course.name,
            difficulty=r.course.difficulty,
            duration_minutes=r.course.duration_minutes,
            duration_label=duration_label(r.course.duration_minutes),
            url=r.course.url,
            reasons=list(r.reasons),
            covers=[g.skill_name for g in r.covered_gaps],
        )
        for r in rec_report.recommendations
    ]

    plan = [
        WeekPlanView(
            week=w.week,
            courses=[
                {
                    "course_id": c.course.course_id,
                    "name": c.course.name,
                    "minutes": c.minutes,
                    "difficulty": c.course.difficulty,
                    "continued": c.continued,
                }
                for c in w.courses
            ],
        )
        for w in path_report.weeks
    ]

    records = store.list_records(employee_id)
    passed = [r for r in records if r.passed]
    scores = [r.exam_score for r in passed]
    completed_ids = set(state.update.passed_course_ids)
    next_course = None
    for w in path_report.weeks:
        for c in w.courses:
            if c.course.course_id not in completed_ids:
                next_course = c.course.name
                break
        if next_course:
            break

    progress = ProgressView(
        completed_count=len(passed),
        passed_count=len(passed),
        average_score=round(sum(scores) / len(scores), 1) if scores else None,
        current_week=min(len(records) + 1, len(plan) or 1),
        total_weeks=len(plan),
        next_course=next_course,
    )

    return EmployeeHomeView(
        employee={
            "id": record["employee_id"],
            "name": gap.employee_name,
            "department": gap.department,
        },
        readiness_percent=readiness_percent(gap.readiness),
        target_position=gap.target_position_name,
        current_position=gap.current_position_name,
        skills=skills,
        top_gaps=top_gaps,
        recommendations=recommendations,
        plan=plan,
        progress=progress,
    )
