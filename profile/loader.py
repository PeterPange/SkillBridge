"""画像构建器:``data/processed`` JSON 记录 → 领域对象。

- :func:`build_employee_profile` 消费 ``employees.json`` 单条记录;
- :func:`build_position_requirements` 消费 ``positions.json`` 单条记录,
  经统一技能库(:mod:`data.skilllib`)补全技能名称与类别。

校验两层:等级范围(0-4)与 Evidence 四类字段完整性在构建时兜底
(skill_id 引用完整性由 :mod:`data.schemas` 在采集阶段保证,
这里对未知 skill_id 抛出带上下文的 ``ValueError``)。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from data import skilllib
from profile.models import (
    EmployeeProfile,
    PositionRequirement,
    SkillAssessment,
    SkillEvidence,
    check_level,
)

#: 统一技能库全部 skill_id(用于员工技能引用校验)
_SKILL_IDS = frozenset(skilllib.all_skill_ids())


def build_employee_profile(employee: Mapping[str, Any]) -> EmployeeProfile:
    """从 ``employees.json`` 单条记录构建员工画像(等级 + Evidence)。

    :raises ValueError: 等级越界、Evidence 字段缺失、技能重复或引用未知技能。
    """
    skills: dict[str, SkillAssessment] = {}
    for item in employee.get("skills", []):
        skill_id = item["skill_id"]
        if skill_id in skills:
            raise ValueError(
                f"员工 {employee.get('employee_id', '?')} 重复技能 {skill_id}"
            )
        if skill_id not in _SKILL_IDS:
            raise ValueError(
                f"员工 {employee.get('employee_id', '?')} 引用未知技能 {skill_id}"
            )
        skills[skill_id] = SkillAssessment(
            skill_id=skill_id,
            level=check_level(item["level"]),
            evidence=SkillEvidence.from_dict(item["evidence"]),
        )
    return EmployeeProfile(
        employee_id=employee["employee_id"],
        name=employee["name"],
        department=employee["department"],
        current_position_id=employee["current_position_id"],
        target_position_id=employee["target_position_id"],
        years_of_experience=employee["years_of_experience"],
        skills=skills,
    )


def build_position_requirements(
    position: Mapping[str, Any],
) -> list[PositionRequirement]:
    """从 ``positions.json`` 单条记录构建岗位技能要求列表。

    :raises ValueError: 要求等级越界、重要度越界或引用未知技能。
    """
    requirements: list[PositionRequirement] = []
    for item in position.get("skills", []):
        skill_id = item["skill_id"]
        try:
            skill = skilllib.get_skill(skill_id)
        except KeyError as exc:
            raise ValueError(
                f"岗位 {position.get('position_id', '?')} 引用未知技能 {skill_id}"
            ) from exc
        requirements.append(
            PositionRequirement(
                skill_id=skill_id,
                skill_name=skill["name"],
                category=skill["category"],
                importance=float(item["importance"]),
                required_level=check_level(item["required_level"], "岗位要求等级"),
            )
        )
    return requirements
