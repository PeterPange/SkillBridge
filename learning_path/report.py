"""学习路径报告的文本渲染(供 CLI 输出与 Agent 解释复用)。"""

from __future__ import annotations

import unicodedata

from learning_path.models import LearningPathReport


def _display_width(text: str) -> int:
    """终端显示宽度(中日韩宽字符计 2)。"""
    return sum(
        2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text
    )


def _ljust(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


def _fmt_minutes(minutes: float) -> str:
    """分钟数显示:整数值去掉小数点(240.0 → 240)。"""
    return f"{minutes:g}"


def _render_week(index: int, report: LearningPathReport, plan) -> list[str]:
    """单周块:周标题 + 课程条目(名称 / 难度 / 本周时长 / 覆盖缺口)。"""
    lines = [
        f"第 {plan.week} 周   {_fmt_minutes(plan.minutes)} / "
        f"{_fmt_minutes(plan.budget_minutes)} 分钟"
    ]
    for position, item in enumerate(plan.courses, start=1):
        course = item.course
        lines.append(f"  {position}. {course.name}({course.course_id})")
        time_text = (
            f"续 {_fmt_minutes(item.minutes)} / 共 {course.duration_minutes} 分钟"
            if item.continued
            else f"{_fmt_minutes(item.minutes)} 分钟"
        )
        detail = f"     {course.difficulty} · {time_text}"
        covered = report.covered_gaps.get(course.course_id, ())
        if covered:
            gaps_text = "、".join(
                f"{gap.skill_name}(+{gap.gap})" for gap in covered
            )
            detail += f" · 覆盖 {gaps_text}"
        lines.append(detail)
        if course.url:
            lines.append(f"     课程链接 : {course.url}")
    return lines


def render_learning_path_report(report: LearningPathReport) -> str:
    """渲染人类可读的周计划学习路径。"""
    width = 62
    bar = "=" * width
    thin = "-" * width

    deadline_text = (
        f" · 截止 {report.deadline_weeks} 周" if report.deadline_weeks else ""
    )
    lines: list[str] = [
        bar,
        f"自适应学习路径:{report.employee_name} → {report.target_position_name}",
        bar,
        f"员工     : {report.employee_name}({report.employee_id})",
        f"目标岗位 : {report.target_position_name}({report.target_position_id})",
        f"时间约束 : 每周 {report.hours_per_week:g} 小时"
        f"(预算 {_fmt_minutes(report.hours_per_week * 60.0)} 分钟){deadline_text}",
        f"课程规划 : 待学 {report.course_count} 门 · 剪枝已掌握 "
        f"{len(report.pruned)} 门 · 共 {_fmt_minutes(report.total_minutes)} 分钟"
        f"(约 {report.total_hours:.1f} 小时)",
        thin,
    ]

    if not report.weeks:
        lines.append("无需规划学习路径:没有缺口,或候选课程均已掌握。")
        lines.append(thin)
    else:
        for index, plan in enumerate(report.weeks):
            if index:
                lines.append(thin)
            lines.extend(_render_week(index, report, plan))
        lines.append(thin)

    if report.pruned:
        lines.append(f"已掌握,跳过({len(report.pruned)} 门,凭已有技能可免修):")
        for item in report.pruned:
            lines.append(
                f"  - {item.course.name}({item.course.course_id})"
                f"{item.course.difficulty} · 所授技能平均等级 "
                f"{item.average_level:.1f} ≥ 掌握门槛 {_fmt_minutes(item.threshold)}"
            )
        lines.append(thin)

    if report.uncovered_skills:
        uncovered = "、".join(
            f"{gap.skill_name}(差距 +{gap.gap})" for gap in report.uncovered_skills
        )
        lines.append(
            f"未覆盖缺口({len(report.uncovered_skills)} 项,"
            f"图谱中暂无课程教授):{uncovered}"
        )
        lines.append(thin)

    if report.deadline_weeks:
        if report.fits_deadline:
            status = f"可按期完成(截止 {report.deadline_weeks} 周)"
        else:
            status = (
                f"超出截止期限 {report.planned_weeks - report.deadline_weeks} 周"
                f"(截止 {report.deadline_weeks} 周,建议增加每周学习时间"
                f"或协商延长期限)"
            )
        lines.append(
            f"计划汇总 : {report.course_count} 门课程 · "
            f"{report.planned_weeks} 周完成 · {status}"
        )
    else:
        lines.append(
            f"计划汇总 : {report.course_count} 门课程 · "
            f"{report.planned_weeks} 周完成"
        )
    lines.append(bar)
    return "\n".join(lines)
