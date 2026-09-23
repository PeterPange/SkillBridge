"""Course Ranking(大纲第七节):候选课程加权打分与排序——纯算法,不用 LLM。

五因子(全部归一到 0-1,加权求和):

1. **Gap 覆盖度** ``gap_coverage``
   课程覆盖的加权缺口(差距 × 岗位重要度)占全部加权缺口的比例;
   同时覆盖多门缺口技能、且缺口大的课程得分高。
2. **技能重要性** ``importance``
   覆盖缺口技能的最高岗位重要度 / 5;核心技能(重要度 5)优先。
3. **难度匹配** ``difficulty_match``
   按员工在课程所授技能上的平均等级推导期望难度
   (0-1 → beginner,2 → intermediate,3-4 → advanced),
   与课程实际难度按等级距离打分:完全匹配 1.0,差一级 0.5,差两级 0。
4. **前置满足** ``prerequisite``
   直接前置课程逐门判定:所授技能的平均等级 ≥ 2(基础)视为已满足
   (员工可凭已有技能跳过,而非必须学过该课);满足率即得分,
   无前置课程得 1.0(可立即开始)。
5. **时间成本** ``time_cost``
   ``1 / (1 + 小时数)``:时长越短得分越高,40 分钟 ≈ 0.60,2 小时 = 0.5。

排序规则(保证确定性):总分降序 → course_id 升序。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from profile.models import SkillGap
from recommendation.models import (
    CandidateCourse,
    CandidatePool,
    CourseRef,
    ScoreBreakdown,
    ScoringWeights,
)

#: 难度等级 → 数值(beginner=0 / intermediate=1 / advanced=2)
DIFFICULTY_RANK = {"beginner": 0, "intermediate": 1, "advanced": 2}

#: 前置课程视为「已满足」的技能平均等级阈值(2 = 基础)
PREREQUISITE_SATISFY_LEVEL = 2

#: level_of:skill_id → 当前等级(0-4);由 EmployeeProfile.level_of 提供
LevelOf = Callable[[str], int]


def covered_gaps(
    course: CandidateCourse, gaps: Sequence[SkillGap]
) -> tuple[SkillGap, ...]:
    """课程覆盖的缺口(保持差距报告顺序:差距降序 → 重要度降序)。"""
    return tuple(gap for gap in gaps if gap.skill_id in course.taught_skills)


def gap_coverage_score(
    course: CandidateCourse, gaps: Sequence[SkillGap]
) -> float:
    """Gap 覆盖度:覆盖的加权缺口 / 全部加权缺口。"""
    total = sum(gap.gap * gap.importance for gap in gaps)
    if total <= 0:
        return 0.0
    covered = sum(gap.gap * gap.importance for gap in covered_gaps(course, gaps))
    return covered / total


def importance_score(
    course: CandidateCourse, gaps: Sequence[SkillGap]
) -> float:
    """技能重要性:覆盖缺口技能的最高岗位重要度 / 5。"""
    covered = covered_gaps(course, gaps)
    if not covered:
        return 0.0
    return max(gap.importance for gap in covered) / 5.0


def course_level_average(course: CandidateCourse, level_of: LevelOf) -> float:
    """员工在课程所授技能上的平均当前等级(难度匹配的依据)。"""
    if not course.taught_skills:
        return 0.0
    return sum(level_of(skill_id) for skill_id in course.taught_skills) / len(
        course.taught_skills
    )


def expected_difficulty_rank(course: CandidateCourse, level_of: LevelOf) -> int:
    """按课程技能平均等级推导期望难度:0-1 → beginner,2 → intermediate,3-4 → advanced。"""
    average = course_level_average(course, level_of)
    if average <= 1:
        return 0
    if average <= 2:
        return 1
    return 2


def difficulty_match_score(
    course: CandidateCourse, level_of: LevelOf
) -> float:
    """难度匹配:1 − |课程难度等级 − 期望难度等级| / 2,∈ [0, 1]。"""
    if not course.taught_skills:
        return 1.0  # 无技能信息时不惩罚(图谱召回的候选恒有所授技能)
    distance = abs(
        DIFFICULTY_RANK[course.difficulty] - expected_difficulty_rank(course, level_of)
    )
    return 1.0 - distance / 2.0


def prerequisite_status(
    course: CandidateCourse,
    pool: CandidatePool,
    level_of: LevelOf,
) -> tuple[tuple[CourseRef, ...], tuple[CourseRef, ...]]:
    """逐门判定直接前置课程是否已满足。

    判定依据:前置课程所授技能的平均等级 ≥ 2(基础)即视为满足——
    员工可凭已有技能基础跳过,而非必须学过该门课程。
    图谱中查不到所授技能的前置课程按未满足处理(保守)。

    :return: ``(已满足, 未满足)``,各按 course_id 升序。
    """
    satisfied: list[CourseRef] = []
    missing: list[CourseRef] = []
    for prereq_id in sorted(course.prerequisites):
        skills = pool.taught_skills_of(prereq_id)
        is_satisfied = bool(skills) and (
            sum(level_of(skill_id) for skill_id in skills) / len(skills)
            >= PREREQUISITE_SATISFY_LEVEL
        )
        reference = CourseRef(
            course_id=prereq_id, name=pool.name_of(prereq_id) or prereq_id
        )
        (satisfied if is_satisfied else missing).append(reference)
    return tuple(satisfied), tuple(missing)


def prerequisite_score(
    course: CandidateCourse,
    pool: CandidatePool,
    level_of: LevelOf,
) -> float:
    """前置满足率:已满足前置数 / 前置总数;无前置课程得 1.0。"""
    if not course.prerequisites:
        return 1.0
    satisfied, _ = prerequisite_status(course, pool, level_of)
    return len(satisfied) / len(course.prerequisites)


def time_cost_score(course: CandidateCourse) -> float:
    """时间成本:``1 / (1 + 小时数)``,时长越短得分越高。"""
    if course.duration_minutes <= 0:
        return 1.0
    return 1.0 / (1.0 + course.duration_minutes / 60.0)


def score_candidate(
    course: CandidateCourse,
    gaps: Sequence[SkillGap],
    pool: CandidatePool,
    level_of: LevelOf,
    weights: ScoringWeights,
) -> ScoreBreakdown:
    """计算单门课程的五因子分项得分与加权总分。"""
    breakdown = ScoreBreakdown(
        gap_coverage=gap_coverage_score(course, gaps),
        importance=importance_score(course, gaps),
        difficulty_match=difficulty_match_score(course, level_of),
        prerequisite=prerequisite_score(course, pool, level_of),
        time_cost=time_cost_score(course),
        total=0.0,
    )
    total = (
        weights.gap_coverage * breakdown.gap_coverage
        + weights.importance * breakdown.importance
        + weights.difficulty_match * breakdown.difficulty_match
        + weights.prerequisite * breakdown.prerequisite
        + weights.time_cost * breakdown.time_cost
    )
    return ScoreBreakdown(
        gap_coverage=breakdown.gap_coverage,
        importance=breakdown.importance,
        difficulty_match=breakdown.difficulty_match,
        prerequisite=breakdown.prerequisite,
        time_cost=breakdown.time_cost,
        total=total,
    )


def rank_candidates(
    pool: CandidatePool,
    gaps: Sequence[SkillGap],
    level_of: LevelOf,
    *,
    weights: ScoringWeights | None = None,
    top_k: int | None = None,
) -> list[tuple[CandidateCourse, ScoreBreakdown, tuple[SkillGap, ...]]]:
    """全部候选打分并排序，返回前 ``top_k`` 名。

    不覆盖任何缺口技能的课程不参与排序（候选生成已保证覆盖，
    此处兜底过滤，保证“无缺口 → 无推荐”的语义）。

    :return: ``(课程, 分项得分, 覆盖缺口)`` 列表，按总分降序 →
        course_id 升序（确定性）；``top_k`` 为 ``None`` 时返回全部。
    """
    weights = weights or ScoringWeights()
    scored: list[
        tuple[CandidateCourse, ScoreBreakdown, tuple[SkillGap, ...]]
    ] = []
    for course in pool.candidates:
        covered = covered_gaps(course, gaps)
        if not covered:
            continue
        scored.append(
            (
                course,
                score_candidate(course, gaps, pool, level_of, weights),
                covered,
            )
        )
    scored.sort(key=lambda item: (-item[1].total, item[0].course_id))
    if top_k is not None:
        scored = scored[:top_k]
    return scored


# ---------------------------------------------------------------------------
# 推荐理由(大纲第七节:LLM 解释为什么推荐的输入)
# ---------------------------------------------------------------------------

def _time_cost_label(duration_minutes: int) -> str:
    if duration_minutes <= 60:
        return "较低"
    if duration_minutes <= 120:
        return "适中"
    return "较高"


def build_reasons(
    course: CandidateCourse,
    breakdown: ScoreBreakdown,
    covered: Sequence[SkillGap],
    satisfied: Sequence[CourseRef],
    missing: Sequence[CourseRef],
    level_of: LevelOf,
) -> tuple[str, ...]:
    """生成结构化推荐理由,每条对应一个评分因子(供 LLM 解释复用)。"""
    reasons: list[str] = []

    # 1) Gap 覆盖度 + 技能重要性
    if covered:
        detail = "、".join(
            f"{gap.skill_name}(当前 {gap.current_level} → 要求 "
            f"{gap.required_level},重要度 {gap.importance:.1f})"
            for gap in covered
        )
        reasons.append(f"覆盖 {len(covered)} 项能力缺口:{detail}")

    # 2) 难度匹配
    average = course_level_average(course, level_of)
    if breakdown.difficulty_match >= 1.0:
        reasons.append(
            f"课程难度 {course.difficulty} 与当前基础匹配"
            f"(课程所授技能平均等级 {average:.1f})"
        )
    elif DIFFICULTY_RANK[course.difficulty] > expected_difficulty_rank(
        course, level_of
    ):
        reasons.append(
            f"课程难度 {course.difficulty} 高于当前基础"
            f"(课程所授技能平均等级 {average:.1f}),学习挑战较大"
        )
    else:
        reasons.append(
            f"课程难度 {course.difficulty} 低于当前基础"
            f"(课程所授技能平均等级 {average:.1f}),内容可能偏简单"
        )

    # 3) 前置满足
    if not course.prerequisites:
        reasons.append("无前置课程,可立即开始")
    elif not missing:
        names = "、".join(ref.name for ref in satisfied)
        reasons.append(f"前置课程已满足:{names},可直接学习")
    elif not satisfied:
        names = "、".join(ref.name for ref in missing)
        reasons.append(
            f"前置课程未满足:{names}(建议先补齐基础,或确认已具备对应技能)"
        )
    else:
        satisfied_names = "、".join(ref.name for ref in satisfied)
        missing_names = "、".join(ref.name for ref in missing)
        reasons.append(
            f"前置课程部分满足:{satisfied_names} 已具备,"
            f"{missing_names} 未满足"
        )

    # 4) 时间成本
    reasons.append(
        f"学习时长约 {course.duration_minutes} 分钟,"
        f"时间成本{_time_cost_label(course.duration_minutes)}"
    )
    return tuple(reasons)


def scored_to_dict(
    course: CandidateCourse, breakdown: ScoreBreakdown
) -> dict[str, Any]:
    """(课程, 得分) → 字典(调试与测试辅助)。"""
    return {"course": course.to_dict(), "breakdown": breakdown.to_dict()}
