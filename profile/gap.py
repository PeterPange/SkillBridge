"""Skill Gap 计算(大纲第六节)——纯算法,不使用 LLM。

对目标岗位的每项技能要求::

    gap = required_level - current_level

员工未登记的技能当前等级按 0 计(大纲第二节:李明 GenAI / AI Agent = 0)。
只保留 ``gap > 0`` 的缺失技能,排序规则(保证确定性):

1. 差距降序(缺失程度优先);
2. 岗位重要度降序(同等差距先补关键技能);
3. skill_id 升序。

输出 :class:`~profile.models.GapReport` 结构化差距报告(缺失技能 +
差距值 + 重要度 + 岗位准备度),作为课程推荐模块(大纲第七节
Candidate Generation)的输入。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from data import skilllib
from profile.loader import build_position_requirements
from profile.models import (
    EmployeeProfile,
    ExtraSkill,
    GapReport,
    MetSkill,
    PositionRequirement,
    SkillGap,
)


def calculate_skill_gaps(
    profile: EmployeeProfile,
    requirements: Iterable[PositionRequirement],
) -> list[SkillGap]:
    """计算缺失技能列表(纯算法)。

    :param profile: 员工画像(当前等级 + Evidence)。
    :param requirements: 目标岗位技能要求。
    :return: 按差距 / 重要度排序的 ``SkillGap`` 列表;空列表 = 完全达标。
    """
    gaps: list[SkillGap] = []
    for requirement in requirements:
        if requirement.required_level <= 0:
            continue  # 要求等级 0 = 不构成差距
        current = profile.level_of(requirement.skill_id)
        gap = requirement.required_level - current
        if gap <= 0:
            continue  # 已达标
        gaps.append(
            SkillGap(
                skill_id=requirement.skill_id,
                skill_name=requirement.skill_name,
                category=requirement.category,
                current_level=current,
                required_level=requirement.required_level,
                importance=requirement.importance,
                gap=gap,
                gap_ratio=gap / requirement.required_level,
                weighted_gap=gap * requirement.importance,
            )
        )
    gaps.sort(key=lambda g: (-g.gap, -g.importance, g.skill_id))
    return gaps


def _readiness(
    profile: EmployeeProfile,
    requirements: Iterable[PositionRequirement],
) -> float:
    """按重要度加权的岗位准备度。

    ``readiness = Σ min(当前, 要求) × 重要度 / Σ 要求 × 重要度``;
    无有效要求(全部要求等级为 0)时视为 1.0。
    """
    attained = 0.0
    total = 0.0
    for requirement in requirements:
        if requirement.required_level <= 0:
            continue
        weight = requirement.importance
        total += requirement.required_level * weight
        attained += (
            min(profile.level_of(requirement.skill_id), requirement.required_level)
            * weight
        )
    return attained / total if total > 0 else 1.0


def build_gap_report(
    profile: EmployeeProfile,
    position: Mapping[str, Any],
    *,
    current_position: Mapping[str, Any] | None = None,
) -> GapReport:
    """构建结构化差距报告:员工 vs 目标岗位。

    :param profile: 员工画像。
    :param position: 目标岗位记录(``positions.json`` 单条)。
    :param current_position: 当前岗位记录(可选,仅用于报告展示名称)。
    """
    requirements = build_position_requirements(position)
    gaps = calculate_skill_gaps(profile, requirements)

    met = tuple(
        MetSkill(
            skill_id=requirement.skill_id,
            skill_name=requirement.skill_name,
            current_level=profile.level_of(requirement.skill_id),
            required_level=requirement.required_level,
            importance=requirement.importance,
        )
        for requirement in requirements
        if requirement.required_level > 0
        and profile.level_of(requirement.skill_id) >= requirement.required_level
    )

    required_ids = {requirement.skill_id for requirement in requirements}
    extra_skills = tuple(
        ExtraSkill(
            skill_id=skill_id,
            skill_name=skilllib.get_skill(skill_id)["name"],
            level=assessment.level,
        )
        for skill_id, assessment in sorted(profile.skills.items())
        if skill_id not in required_ids
    )

    return GapReport(
        employee_id=profile.employee_id,
        employee_name=profile.name,
        department=profile.department,
        years_of_experience=profile.years_of_experience,
        current_position_id=profile.current_position_id,
        current_position_name=(
            current_position["name"] if current_position else profile.current_position_id
        ),
        target_position_id=str(position["position_id"]),
        target_position_name=position["name"],
        gaps=tuple(gaps),
        met=met,
        extra_skills=extra_skills,
        readiness=_readiness(profile, requirements),
    )
