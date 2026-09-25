"""HR 视角服务:团队级聚合分析。

复用员工服务的数据源(profile / feedback),在其上做团队聚合:
准备度分布、最大能力缺口排行、培训效果统计。
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from feedback import build_feedback_state
from feedback.store import PostgresTrainingStore
from profile.__main__ import DEFAULT_DATA_DIR

from webapp.services.viewmodels import (
    HrHomeView,
    TeamGapView,
    TeamMemberView,
    bucket_of,
    readiness_percent,
)


def _load_all_employees() -> list[dict[str, Any]]:
    data = json.loads((Path(DEFAULT_DATA_DIR) / "employees.json").read_text("utf-8"))
    return data["employees"]


def build_hr_home() -> HrHomeView:
    """一次组装 HR 端首页:团队总览 + 缺口排行 + 成员表 + 培训效果。"""
    store = PostgresTrainingStore()
    store.ensure_schema()
    employees = _load_all_employees()

    members: list[TeamMemberView] = []
    gap_counter: Counter[str] = Counter()
    core_skills: set[str] = set()
    readiness_values: list[float] = []
    total_passed = 0
    all_scores: list[int] = []
    recent_records: list[dict[str, Any]] = []

    for record in employees:
        employee_id = record["employee_id"]
        state = build_feedback_state(store, employee_id)
        gap = state.gap_after
        readiness_values.append(gap.readiness)

        for g in gap.gaps:
            gap_counter[g.skill_name] += 1
            if (g.importance or 0) >= 5:
                core_skills.add(g.skill_name)

        records = store.list_records(employee_id)
        passed = [r for r in records if r.passed]
        total_passed += len(passed)
        all_scores.extend(r.exam_score for r in passed)
        for r in records[-3:]:
            recent_records.append(
                {
                    "employee": gap.employee_name,
                    "course_id": r.course_id,
                    "score": r.exam_score,
                    "passed": r.passed,
                    "at": r.completed_at,
                }
            )

        members.append(
            TeamMemberView(
                employee_id=employee_id,
                name=gap.employee_name,
                department=gap.department,
                current_position=gap.current_position_name,
                target_position=gap.target_position_name,
                readiness_percent=readiness_percent(gap.readiness),
                bucket=bucket_of(gap.readiness),
                completed_courses=len(passed),
                average_score=(
                    round(sum(r.exam_score for r in passed) / len(passed), 1)
                    if passed
                    else None
                ),
            )
        )

    team_size = len(employees)
    buckets = Counter(m.bucket for m in members)
    top_gaps = [
        TeamGapView(
            skill=skill,
            lacking_count=count,
            team_size=team_size,
            is_core=skill in core_skills,
        )
        for skill, count in gap_counter.most_common(8)
    ]

    training = {
        "total_completions": total_passed,
        "pass_rate": round(100 * total_passed / len(all_scores)) if all_scores else None,
        "average_score": round(sum(all_scores) / len(all_scores), 1) if all_scores else None,
        "recent": sorted(recent_records, key=lambda r: r["at"] or "", reverse=True)[:6],
    }

    return HrHomeView(
        team_size=team_size,
        average_readiness=readiness_percent(
            sum(readiness_values) / len(readiness_values) if readiness_values else 0
        ),
        buckets={"ready": buckets.get("ready", 0), "close": buckets.get("close", 0), "far": buckets.get("far", 0)},
        top_team_gaps=top_gaps,
        members=members,
        training=training,
    )
