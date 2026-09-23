"""推荐报告的文本渲染(供 CLI 输出与 Agent 解释复用)。"""

from __future__ import annotations

import unicodedata

from recommendation.models import RecommendationReport


def _display_width(text: str) -> int:
    """终端显示宽度(中日韩宽字符计 2)。"""
    return sum(
        2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text
    )


def _ljust(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


def _format_weights(report: RecommendationReport) -> str:
    weights = report.weights
    return (
        f"Gap覆盖 {weights.gap_coverage:.0%} · "
        f"技能重要性 {weights.importance:.0%} · "
        f"难度匹配 {weights.difficulty_match:.0%} · "
        f"前置满足 {weights.prerequisite:.0%} · "
        f"时间成本 {weights.time_cost:.0%}"
    )


def _render_recommendation(index: int, rec) -> list[str]:
    """单条推荐块:标题行 + 覆盖缺口 + 难度时长 + 前置 + 理由。"""
    course = rec.course
    lines = [
        f"{index:>2}. {course.name}({course.course_id})"
        f"  评分 {rec.score:.3f}",
    ]
    if rec.covered_gaps:
        gaps_text = "、".join(
            f"{gap.skill_name}({gap.current_level}→{gap.required_level})"
            for gap in rec.covered_gaps
        )
        lines.append(f"    覆盖缺口 : {gaps_text}")
    lines.append(
        f"    难度时长 : {course.difficulty} · {course.duration_minutes} 分钟"
    )
    if not course.prerequisites:
        lines.append("    前置课程 : 无,可立即开始")
    elif rec.missing_prerequisites:
        missing = "、".join(
            ref.name for ref in rec.missing_prerequisites
        )
        lines.append(f"    前置课程 : 未满足 → {missing}")
    else:
        satisfied = "、".join(
            ref.name for ref in rec.satisfied_prerequisites
        )
        lines.append(f"    前置课程 : 已满足 → {satisfied}")
    lines.append("    推荐理由 :")
    lines.extend(f"      - {reason}" for reason in rec.reasons)
    lines.append(f"    课程链接 : {course.url}" if course.url else "")
    return [line for line in lines if line]


def render_recommendation_report(report: RecommendationReport) -> str:
    """渲染人类可读的 Top-K 推荐报告。"""
    width = 62
    bar = "=" * width
    thin = "-" * width
    lines: list[str] = [
        bar,
        f"个性化课程推荐:{report.employee_name} → {report.target_position_name}",
        bar,
        f"员工     : {report.employee_name}({report.employee_id})",
        f"目标岗位 : {report.target_position_name}({report.target_position_id})",
        f"评分权重 : {_format_weights(report)}",
        f"候选课程 : {report.candidate_count} 门"
        f"(按缺口技能 TEACHES 关系召回)→ 推荐前 {len(report.recommendations)} 门",
        thin,
    ]

    if not report.recommendations:
        if report.candidate_count == 0:
            lines.append("图谱中未找到教授缺口技能的课程,暂无可推荐内容。")
        else:
            lines.append("无推荐结果。")
        lines.append(thin)
    else:
        for index, rec in enumerate(report.recommendations, start=1):
            if index > 1:
                lines.append(thin)
            lines.extend(_render_recommendation(index, rec))
        lines.append(thin)

    if report.uncovered_skills:
        uncovered = "、".join(
            f"{gap.skill_name}(差距 +{gap.gap})" for gap in report.uncovered_skills
        )
        lines.append(f"未覆盖缺口({len(report.uncovered_skills)} 项,图谱中暂无课程教授):{uncovered}")
        lines.append(thin)

    lines.append(bar)
    return "\n".join(lines)
