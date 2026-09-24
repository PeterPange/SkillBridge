"""反馈模块的文本渲染(供 CLI 输出与 Agent 解释复用)。

- :func:`render_completion` 渲染一次完成登记的结果
  (等级提升 + Evidence + 闭环重算 + 培训历史 + 当前准备度);
- :func:`render_status` 渲染培训档案(历史 + 画像变化 + 准备度前后);
- :func:`render_plan_diff` 渲染学习路径前后对比
  (大纲第十一节的核心演示:学完 A/B 后只剩 C → D)。
"""

from __future__ import annotations

import unicodedata

from feedback.models import (
    FLAG_CONSOLIDATE,
    CompletionResult,
    FeedbackState,
    PlanDiff,
)
from feedback.replay import OUTCOME_CONSOLIDATE, OUTCOME_FAIL, score_outcome
from learning_path.models import PRUNE_REASON_COMPLETED, LearningPathReport

_WIDTH = 64


def _display_width(text: str) -> int:
    """终端显示宽度(中日韩宽字符计 2)。"""
    return sum(
        2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text
    )


def _ljust(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


def _bar(width: int = _WIDTH) -> str:
    return "=" * width


def _thin(width: int = _WIDTH) -> str:
    return "-" * width


def _fmt_pct(value: float) -> str:
    """准备度百分比(29.577% → 29.6%)。"""
    return f"{value:.1%}"


def _pp(before: float, after: float) -> str:
    """准备度变化(百分点,带符号)。"""
    delta = (after - before) * 100
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.1f}"


def _score_line(score: int) -> str:
    """考试分数 → 档位说明。"""
    outcome = score_outcome(score)
    if outcome == OUTCOME_FAIL:
        return f"{score} 分 → 未通过(<70,不提升等级,生成补基础建议)"
    if outcome == OUTCOME_CONSOLIDATE:
        return f"{score} 分 → 通过(70-84,提升 1 级,标记「{FLAG_CONSOLIDATE}」)"
    return f"{score} 分 → 优秀(≥85,提升 1 级,无需巩固)"


def _render_history(records, catalog) -> list[str]:
    """培训历史(按时间倒序,最近在前)。"""
    if not records:
        return ["培训历史 : 暂无记录"]
    lines = [f"培训历史({len(records)} 条,最近在前):"]
    for record in reversed(records):
        course = catalog.get(record.course_id)
        name = course.name if course else record.course_id
        verdict = "通过" if record.passed else "未通过"
        lines.append(
            f"  #{record.record_id} 《{name}》({record.course_id})"
            f"  考试 {record.exam_score} 分 · {verdict}"
        )
        for change in record.level_changes:
            if change.from_level != change.to_level:
                lines.append(
                    f"      技能提升 : {change.skill_name} "
                    f"Level {change.from_level} → {change.to_level}"
                    + (f" [{change.flag}]" if change.flag else "")
                )
        for suggestion in record.suggestions:
            lines.append(
                f"      建议 : {suggestion.kind} → 《{suggestion.course_name}》"
                f"({suggestion.course_id})"
            )
    return lines


def _render_changes(result: CompletionResult) -> list[str]:
    """本次完成引发的技能等级变化(可解释:为什么涨级)。"""
    changes = result.record.level_changes
    lines: list[str] = []
    if not changes:
        lines.append("技能提升 : 本次无等级变化(同难度已完成,不再重复涨级)")
        return lines
    promoted = [c for c in changes if c.from_level != c.to_level]
    if promoted:
        lines.append("技能提升(证据已写入画像,可解释「为什么涨级」):")
    else:
        lines.append("证据追加(本次未提升等级,考试记录写入对应技能):")
    for change in changes:
        if change.from_level != change.to_level:
            lines.append(
                f"  {change.skill_name}  Level {change.from_level} → "
                f"{change.to_level}"
                + (f"  [{change.flag}]" if change.flag else "")
            )
            lines.append(f"    证据 : {change.note}")
        else:
            lines.append(f"  {change.skill_name}  {change.note}")
    return lines


def _render_loop(result: CompletionResult) -> list[str]:
    """闭环重算摘要:准备度 / 缺口 / 推荐 / 课表。"""
    before = result.gap_before
    after = result.loop_after.gap_report
    recommendations = result.loop_after.recommendations
    path = result.loop_after.path
    top_names = "、".join(
        f"《{rec.course.name}》" for rec in recommendations.recommendations[:3]
    )
    completed_pruned = sum(
        1 for item in path.pruned if item.reason == PRUNE_REASON_COMPLETED
    )
    return [
        "闭环重算(画像刷新 → Skill Gap → 推荐刷新 → 课表重排):",
        f"  岗位准备度 : {_fmt_pct(before.readiness)} → "
        f"{_fmt_pct(after.readiness)}({_pp(before.readiness, after.readiness)} 个百分点)",
        f"  缺失技能   : {before.missing_count} 项 → {after.missing_count} 项"
        f"(总差距 {before.total_gap} → {after.total_gap} 级)",
        f"  推荐 Top-{recommendations.top_k} : {top_names or '无'}"
        f"(候选 {recommendations.candidate_count} 门,已完成课程已排除)",
        f"  学习路径   : {path.course_count} 门 · {path.planned_weeks} 周 · "
        f"约 {path.total_hours:.1f} 小时"
        f"(已完成剪枝 {completed_pruned} 门,已掌握剪枝 "
        f"{len(path.pruned) - completed_pruned} 门)",
    ]


def render_completion(result: CompletionResult, catalog) -> str:
    """渲染一次完成登记:登记结果 + 闭环重算 + 培训历史 + 当前准备度。"""
    record = result.record
    course = catalog.get(record.course_id)
    course_name = course.name if course else record.course_id
    bar, thin = _bar(), _thin()
    lines: list[str] = [
        bar,
        f"培训反馈闭环:{result.gap_before.employee_name} 完成《{course_name}》",
        bar,
        f"考试分数 : {_score_line(record.exam_score)}",
        f"落库     : training_record #{record.record_id} + assessment"
        f"(等级变化 {len(record.level_changes)} 项,"
        f"建议 {len(record.suggestions)} 条)",
        thin,
    ]
    lines.extend(_render_changes(result))
    for suggestion in record.suggestions:
        lines.append(
            f"补基础建议 : 先完成《{suggestion.course_name}》"
            f"({suggestion.course_id})——{suggestion.reason.split('，')[0]}"
        )
    lines.append(thin)
    lines.extend(_render_loop(result))
    lines.append(thin)
    lines.extend(_render_history(result.update.records, catalog))
    lines.append(
        f"当前准备度 : {_fmt_pct(result.loop_after.gap_report.readiness)}"
        f"(基础画像 {_fmt_pct(result.gap_before.readiness)})"
    )
    lines.append(bar)
    return "\n".join(lines)


def render_status(state: FeedbackState, catalog) -> str:
    """渲染培训档案:培训历史 + 画像变化 + 准备度前后对比。"""
    update = state.update
    before, after = state.gap_before, state.gap_after
    bar, thin = _bar(), _thin()
    lines: list[str] = [
        bar,
        f"培训档案:{after.employee_name}({after.employee_id})",
        bar,
        f"当前岗位 : {after.current_position_name}",
        f"目标岗位 : {after.target_position_name}({after.target_position_id})",
        thin,
    ]
    lines.extend(_render_history(update.records, catalog))
    lines.append(thin)

    if update.changes:
        lines.append("培训带来的画像变化(基础画像 + 培训记录回放):")
        changed_skills: dict[str, list[str]] = {}
        for change in update.changes:
            if change.from_level != change.to_level:
                changed_skills.setdefault(change.skill_name, []).append(
                    f"Level {change.from_level} → {change.to_level}"
                )
        for name, transitions in changed_skills.items():
            lines.append(f"  {name}  {' → '.join(transitions)}")
        flagged = update.flags
        if flagged:
            names = "、".join(
                f"{_skill_display(update, skill_id)}" for skill_id in sorted(flagged)
            )
            lines.append(f"  带「{FLAG_CONSOLIDATE}」标记:{names}(70-84 分通过,建议巩固)")
        else:
            lines.append("  当前无「需巩固」标记")
    else:
        lines.append("培训带来的画像变化:暂无(基础画像即当前画像)")
    lines.append(thin)
    lines.append(
        f"岗位准备度 : {_fmt_pct(before.readiness)} → "
        f"{_fmt_pct(after.readiness)}({_pp(before.readiness, after.readiness)} 个百分点)"
    )
    lines.append(
        f"缺失技能   : {before.missing_count} 项 → {after.missing_count} 项"
        f"(总差距 {before.total_gap} → {after.total_gap} 级)"
    )
    lines.append(bar)
    return "\n".join(lines)


def _skill_display(update, skill_id: str) -> str:
    """技能显示名(从变化明细或技能库解析)。"""
    from data import skilllib

    for change in update.changes:
        if change.skill_id == skill_id:
            return change.skill_name
    try:
        return skilllib.get_skill(skill_id)["name"]
    except KeyError:
        return skill_id


def _render_path_compact(report: LearningPathReport) -> list[str]:
    """紧凑版学习路径:每周课程一行(供前后对比展示)。"""
    lines: list[str] = []
    if not report.weeks:
        lines.append("  (无需排课:没有缺口,或候选课程均已掌握/已完成)")
        return lines
    for plan in report.weeks:
        courses_text = "、".join(
            f"{item.course.name}({item.course.course_id})" for item in plan.courses
        )
        lines.append(
            f"  第 {plan.week} 周   {plan.minutes:g} / "
            f"{plan.budget_minutes:g} 分钟 : {courses_text}"
        )
    completed_pruned = [
        item for item in report.pruned
        if item.reason == PRUNE_REASON_COMPLETED
    ]
    mastered_pruned = [
        item for item in report.pruned if item.reason != PRUNE_REASON_COMPLETED
    ]
    if completed_pruned:
        names = "、".join(
            f"{item.course.name}({item.course.course_id})"
            for item in completed_pruned
        )
        lines.append(f"  已完成,不再排课({len(completed_pruned)} 门):{names}")
    if mastered_pruned:
        names = "、".join(
            f"{item.course.name}({item.course.course_id})"
            for item in mastered_pruned
        )
        lines.append(f"  已掌握,免修({len(mastered_pruned)} 门):{names}")
    return lines


def render_plan_diff(diff: PlanDiff) -> str:
    """渲染学习路径前后对比(大纲第十一节核心演示)。"""
    before, after = diff.before, diff.after
    bar, thin = _bar(), _thin()
    lines: list[str] = [
        bar,
        f"学习路径前后对比:{before.employee_name} → {before.target_position_name}",
        bar,
        f"原路径(未计入培训记录):{before.course_count} 门 · "
        f"{before.planned_weeks} 周 · {before.total_minutes:g} 分钟",
    ]
    lines.extend(_render_path_compact(before))
    lines.append(thin)
    lines.append(
        f"重排路径(计入培训记录,已完成课程剪枝):{after.course_count} 门 · "
        f"{after.planned_weeks} 周 · {after.total_minutes:g} 分钟"
    )
    lines.extend(_render_path_compact(after))
    lines.append(thin)
    lines.append("对比:")
    lines.append(
        f"  课程数   : {before.course_count} → {after.course_count}"
        f"({after.course_count - before.course_count:+d})"
    )
    lines.append(
        f"  计划周数 : {before.planned_weeks} → {after.planned_weeks}"
        f"({after.planned_weeks - before.planned_weeks:+d})"
    )
    lines.append(
        f"  总时长   : {before.total_minutes:g} → {after.total_minutes:g} 分钟"
        f"({after.total_minutes - before.total_minutes:+g})"
    )
    removed = "、".join(diff.removed_course_ids) or "无"
    added = "、".join(diff.added_course_ids) or "无"
    lines.append(f"  不再排课 : {removed}")
    lines.append(f"  新增课程 : {added}")
    lines.append(bar)
    return "\n".join(lines)
