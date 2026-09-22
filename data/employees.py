"""模拟员工数据生成器(大纲第二节「员工数据」+ 第五节「Evidence」)。

企业真实员工数据不可公开,Demo 使用模拟数据:

- 10 名员工,覆盖 4 类当前岗位(后端 / 数据库 / 数据科学 / DevOps),
  全部以 AI Engineer 为目标岗位,贴合「Java 后端转型 AI Engineer」场景;
- 技能等级 0-4:0 无基础 / 1 入门 / 2 基础 / 3 熟练 / 4 精通;
- 每项技能等级都附带 Evidence(技能考试 / 项目经历 / 自评 / 培训记录),
  支撑后续「为什么认为你是 Level 2」的可解释画像;
- 固定随机种子保证可复现,``seed`` 可注入。
"""

from __future__ import annotations

import random
from typing import Any

from data import skilllib

#: 技能等级上限(0-4)
MAX_LEVEL = 4

#: 员工原型:姓名 / 部门 / 当前岗位 / 工龄 / 基础技能等级(skill_id → level)
ARCHETYPES: list[dict[str, Any]] = [
    {
        "name": "李明", "department": "研发中心", "current_position_id": "POS_001",
        "years_of_experience": 3,
        "base_skills": {
            "SKILL_002": 4, "SKILL_003": 3, "SKILL_001": 2, "SKILL_011": 2,
            "SKILL_013": 3, "SKILL_016": 2, "SKILL_014": 1, "SKILL_004": 1,
            "SKILL_006": 0, "SKILL_009": 0, "SKILL_010": 0,
        },
    },
    {
        "name": "王芳", "department": "研发中心", "current_position_id": "POS_001",
        "years_of_experience": 5,
        "base_skills": {
            "SKILL_002": 4, "SKILL_003": 3, "SKILL_001": 3, "SKILL_011": 2,
            "SKILL_013": 4, "SKILL_016": 2, "SKILL_014": 2, "SKILL_004": 1,
            "SKILL_006": 0, "SKILL_009": 0, "SKILL_017": 1,
        },
    },
    {
        "name": "张伟", "department": "研发中心", "current_position_id": "POS_001",
        "years_of_experience": 4,
        "base_skills": {
            "SKILL_002": 3, "SKILL_003": 2, "SKILL_001": 2, "SKILL_011": 3,
            "SKILL_012": 2, "SKILL_013": 3, "SKILL_016": 3, "SKILL_014": 2,
            "SKILL_004": 0, "SKILL_006": 1, "SKILL_009": 0,
        },
    },
    {
        "name": "刘洋", "department": "研发中心", "current_position_id": "POS_001",
        "years_of_experience": 2,
        "base_skills": {
            "SKILL_002": 3, "SKILL_003": 2, "SKILL_001": 2, "SKILL_011": 1,
            "SKILL_013": 2, "SKILL_016": 1, "SKILL_014": 1, "SKILL_004": 1,
            "SKILL_006": 0, "SKILL_009": 0,
        },
    },
    {
        "name": "陈静", "department": "研发中心", "current_position_id": "POS_001",
        "years_of_experience": 6,
        "base_skills": {
            "SKILL_002": 4, "SKILL_003": 4, "SKILL_001": 3, "SKILL_011": 2,
            "SKILL_013": 4, "SKILL_016": 2, "SKILL_014": 2, "SKILL_004": 2,
            "SKILL_006": 1, "SKILL_009": 0, "SKILL_017": 2,
        },
    },
    {
        "name": "杨帆", "department": "研发中心", "current_position_id": "POS_001",
        "years_of_experience": 3,
        "base_skills": {
            "SKILL_002": 3, "SKILL_003": 3, "SKILL_001": 2, "SKILL_011": 2,
            "SKILL_013": 3, "SKILL_016": 2, "SKILL_014": 2, "SKILL_004": 1,
            "SKILL_006": 1, "SKILL_009": 0, "SKILL_015": 1,
        },
    },
    {
        "name": "赵磊", "department": "数据平台组", "current_position_id": "POS_004",
        "years_of_experience": 4,
        "base_skills": {
            "SKILL_003": 4, "SKILL_001": 3, "SKILL_017": 3, "SKILL_002": 2,
            "SKILL_011": 2, "SKILL_014": 2, "SKILL_004": 1, "SKILL_006": 0,
            "SKILL_009": 0, "SKILL_015": 2,
        },
    },
    {
        "name": "孙悦", "department": "数据平台组", "current_position_id": "POS_004",
        "years_of_experience": 3,
        "base_skills": {
            "SKILL_003": 4, "SKILL_001": 3, "SKILL_017": 3, "SKILL_002": 1,
            "SKILL_011": 1, "SKILL_014": 2, "SKILL_004": 2, "SKILL_006": 1,
            "SKILL_009": 0,
        },
    },
    {
        "name": "周杰", "department": "AI 创新组", "current_position_id": "POS_002",
        "years_of_experience": 5,
        "base_skills": {
            "SKILL_001": 4, "SKILL_004": 4, "SKILL_005": 3, "SKILL_003": 3,
            "SKILL_006": 2, "SKILL_007": 2, "SKILL_008": 1, "SKILL_009": 1,
            "SKILL_011": 2, "SKILL_014": 2, "SKILL_017": 2,
        },
    },
    {
        "name": "吴婷", "department": "基础架构组", "current_position_id": "POS_003",
        "years_of_experience": 4,
        "base_skills": {
            "SKILL_011": 4, "SKILL_012": 3, "SKILL_016": 4, "SKILL_014": 3,
            "SKILL_015": 3, "SKILL_001": 3, "SKILL_002": 2, "SKILL_003": 2,
            "SKILL_006": 0, "SKILL_009": 0,
        },
    },
]

#: 目标岗位:全部指向 AI Engineer(POS_005)
TARGET_POSITION_ID = "POS_005"

#: 项目经历模板(按等级)
_PROJECT_TEMPLATES = {
    4: "主导过多个生产级 {name} 项目,负责架构设计与技术评审",
    3: "作为核心成员参与 {name} 项目,独立完成主要模块开发",
    2: "参与过 {name} 相关项目,在指导下完成开发任务",
    1: "完成过 {name} 入门练习或小型 Demo 项目",
    0: "无相关项目经历",
}

#: 培训记录模板(按等级)
_TRAINING_TEMPLATES = {
    4: ["{name} 高阶专题培训已完成", "通过 {name} 内部专家认证"],
    3: ["{name} 进阶培训已完成"],
    2: ["{name} 基础培训已完成"],
    1: ["{name} 入门课程学习中"],
    0: [],
}


def _jitter_level(rng: random.Random, base: int) -> int:
    """在 base ± 1 范围内做轻微随机扰动(约 1/3 概率变化)。"""
    if rng.random() < 0.34:
        return max(0, min(MAX_LEVEL, base + rng.choice((-1, 1))))
    return base


def _assessment_score(rng: random.Random, level: int) -> int:
    """技能考试分数:与等级强相关(每级约 22 分)+ 少量噪声。"""
    if level == 0:
        return 0
    return min(100, level * 22 + rng.randint(0, 12))


def _self_assessment(rng: random.Random, level: int) -> int:
    """员工自评:围绕实际等级 ±1。"""
    return max(0, min(MAX_LEVEL, level + rng.choice((-1, 0, 0, 1))))


def _build_evidence(rng: random.Random, skill: dict, level: int) -> dict[str, Any]:
    """为某项技能等级生成四类 Evidence(大纲第五节)。"""
    name = skill["name"]
    return {
        "assessment_score": _assessment_score(rng, level),
        "project_experience": _PROJECT_TEMPLATES[level].format(name=name),
        "self_assessment": _self_assessment(rng, level),
        "training_records": [t.format(name=name) for t in _TRAINING_TEMPLATES[level]],
    }


def generate_employees(seed: int = 42, count: int | None = None) -> list[dict[str, Any]]:
    """生成模拟员工列表。

    :param seed: 随机种子,固定种子输出可复现。
    :param count: 生成数量(默认全部 10 名原型)。
    """
    rng = random.Random(seed)
    archetypes = ARCHETYPES if count is None else ARCHETYPES[:count]

    employees = []
    for index, archetype in enumerate(archetypes, start=1):
        skills = []
        for skill_id, base in sorted(archetype["base_skills"].items()):
            skill = skilllib.get_skill(skill_id)
            level = _jitter_level(rng, base)
            skills.append(
                {
                    "skill_id": skill_id,
                    "level": level,
                    "evidence": _build_evidence(rng, skill, level),
                }
            )
        employees.append(
            {
                "employee_id": f"EMP_{index:03d}",
                "name": archetype["name"],
                "department": archetype["department"],
                "current_position_id": archetype["current_position_id"],
                "target_position_id": TARGET_POSITION_ID,
                "years_of_experience": archetype["years_of_experience"],
                "skills": skills,
            }
        )
    return employees
