"""差距报告与 Evidence 的文本渲染(供 CLI 输出与 Agent 解释复用)。

- :func:`render_gap_report` 渲染大纲第六节的结构化差距报告;
- :func:`render_evidence_explanation` 渲染大纲第五节的
  「为什么认为你的 X 是 Level N」证据解释。
"""

from __future__ import annotations

import unicodedata

from profile.models import EmployeeProfile, GapReport


def _display_width(text: str) -> int:
    """终端显示宽度(中日韩宽字符计 2)。"""
    return sum(
        2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text
    )


def _ljust(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


def _rjust(text: str, width: int) -> str:
    return " " * max(0, width - _display_width(text)) + text


def _render_gap_table(report: GapReport) -> list[str]:
    """缺失技能表:技能 / 当前 / 要求 / 差距 / 重要度 / 差距率。"""
    headers = ("技能", "当前", "要求", "差距", "重要度", "差距率")
    rows = [
        (
            gap.skill_name,
            str(gap.current_level),
            str(gap.required_level),
            f"+{gap.gap}",
            f"{gap.importance:.1f}",
            f"{gap.gap_ratio:.0%}",
        )
        for gap in report.gaps
    ]
    widths = [
        max(_display_width(header), *(_display_width(row[i]) for row in rows))
        for i, header in enumerate(headers)
    ]
    lines = [
        "  ".join(
            [_ljust(headers[0], widths[0])]
            + [_rjust(h, w) for h, w in zip(headers[1:], widths[1:])]
        )
    ]
    for row in rows:
        lines.append(
            "  ".join(
                [_ljust(row[0], widths[0])]
                + [_rjust(cell, w) for cell, w in zip(row[1:], widths[1:])]
            )
        )
    return lines


def render_gap_report(report: GapReport) -> str:
    """渲染人类可读的差距报告。"""
    width = 62
    bar = "=" * width
    thin = "-" * width
    lines: list[str] = [
        bar,
        f"Skill Gap 差距报告:{report.employee_name} → {report.target_position_name}",
        bar,
        f"员工     : {report.employee_name}({report.employee_id})  {report.department}",
        f"当前岗位 : {report.current_position_name}",
        f"目标岗位 : {report.target_position_name}({report.target_position_id})",
        f"工龄     : {report.years_of_experience} 年",
        thin,
    ]

    if report.gaps:
        lines.append(
            f"缺失技能({report.missing_count} 项,总差距 {report.total_gap} 级,"
            f"加权差距 {report.weighted_total_gap:g})"
        )
        lines.append("")
        lines.extend(_render_gap_table(report))
        lines.append(thin)
    else:
        lines.append("当前技能已满足目标岗位全部要求,无缺失技能。")
        lines.append(thin)

    if report.met:
        met_text = "、".join(
            f"{met.skill_name}({met.current_level}/{met.required_level})"
            for met in report.met
        )
        lines.append(f"已达标({len(report.met)} 项):{met_text}")
    else:
        lines.append("已达标:0 项")

    if report.extra_skills:
        extra_text = "、".join(
            f"{extra.skill_name}({extra.level})" for extra in report.extra_skills
        )
        lines.append(
            f"额外技能(岗位未要求,{len(report.extra_skills)} 项):{extra_text}"
        )

    lines.append(thin)
    lines.append(f"岗位准备度:{report.readiness:.1%}(按重要度加权的达标率)")
    lines.append(bar)
    return "\n".join(lines)


def render_evidence_explanation(
    profile: EmployeeProfile,
    skill_id: str,
    *,
    skill_name: str | None = None,
) -> str:
    """渲染「为什么认为你的 X 是 Level N」的证据解释(大纲第五节)。"""
    name = skill_name or skill_id
    assessment = profile.assessment_of(skill_id)
    if assessment is None:
        return f"{name}:无评估记录,当前按 Level 0 处理"
    evidence = assessment.evidence
    records = "、".join(evidence.training_records) if evidence.training_records else "无"
    project = evidence.project_experience or "无"
    return "\n".join(
        [
            f"为什么认为你的 {name} 是 Level {assessment.level}?",
            f"  技能考试 : {evidence.assessment_score} 分",
            f"  项目经历 : {project}",
            f"  员工自评 : Level {evidence.self_assessment}",
            f"  培训记录 : {records}",
        ]
    )
