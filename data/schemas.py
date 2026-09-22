"""统一 JSON Schema 与校验(大纲第三节「数据标准化」)。

四类落盘数据(skills / positions / courses / employees)各有独立 Schema,
Schema 文件随采集流程一并写入 ``data/processed/schemas/`` 供外部系统参考。

校验分两层:
1. 单文件 JSON Schema 校验(:func:`validate_instance`);
2. 跨文件引用完整性校验(:func:`validate_referential`),
   包括 skill_id / position_id / course_id 引用与课程前置 DAG 无环。
"""

from __future__ import annotations

from typing import Any

import jsonschema

#: 技能等级 0-4
_LEVEL = {"type": "integer", "minimum": 0, "maximum": 4}
#: 重要度 1-5
_IMPORTANCE = {"type": "number", "minimum": 1, "maximum": 5}

_SKILL_ITEM = {
    "type": "object",
    "required": ["skill_id", "name", "category", "description", "aliases", "sources"],
    "additionalProperties": False,
    "properties": {
        "skill_id": {"type": "string", "pattern": r"^SKILL_\d{3}$"},
        "name": {"type": "string", "minLength": 1},
        "category": {
            "enum": [
                "programming-language", "database", "ai-ml", "platform",
                "engineering-practice", "data", "governance",
            ],
        },
        "description": {"type": "string", "minLength": 1},
        "aliases": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "sources": {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"enum": ["esco", "onet", "curated"]},
        },
    },
}

_POSITION_ITEM = {
    "type": "object",
    "required": [
        "position_id", "name", "description", "responsibilities",
        "sources", "external_ids", "skills",
    ],
    "additionalProperties": False,
    "properties": {
        "position_id": {"type": "string", "pattern": r"^POS_\d{3}$"},
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string", "minLength": 1},
        "responsibilities": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "sources": {
            "type": "array", "minItems": 1, "uniqueItems": True,
            "items": {"enum": ["esco", "onet", "curated"]},
        },
        "external_ids": {
            "type": "object",
            "properties": {
                "esco_uri": {"type": "string"},
                "onet_code": {"type": "string", "pattern": r"^\d{2}-\d{4}\.\d{2}$"},
            },
            "additionalProperties": False,
        },
        "skills": {
            "type": "array",
            "minItems": 3,
            "items": {
                "type": "object",
                "required": ["skill_id", "importance", "required_level", "sources"],
                "additionalProperties": False,
                "properties": {
                    "skill_id": {"type": "string", "pattern": r"^SKILL_\d{3}$"},
                    "importance": _IMPORTANCE,
                    "required_level": _LEVEL,
                    "sources": {
                        "type": "array", "minItems": 1, "uniqueItems": True,
                        "items": {"enum": ["esco", "onet", "curated"]},
                    },
                },
            },
        },
    },
}

_COURSE_ITEM = {
    "type": "object",
    "required": [
        "course_id", "uid", "name", "description", "difficulty", "duration_minutes",
        "learning_objectives", "skills", "prerequisites", "url", "source",
    ],
    "additionalProperties": False,
    "properties": {
        "course_id": {"type": "string", "pattern": r"^CRS_\d{3}$"},
        "uid": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "difficulty": {"enum": ["beginner", "intermediate", "advanced"]},
        "duration_minutes": {"type": "integer", "minimum": 1, "maximum": 2000},
        "learning_objectives": {
            "type": "array", "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
        "skills": {
            "type": "array", "minItems": 1, "uniqueItems": True,
            "items": {"type": "string", "pattern": r"^SKILL_\d{3}$"},
        },
        "prerequisites": {
            "type": "array", "uniqueItems": True,
            "items": {"type": "string", "pattern": r"^CRS_\d{3}$"},
        },
        "url": {"type": "string", "pattern": r"^https?://\S+$"},
        "source": {"const": "microsoft_learn"},
    },
}

_EMPLOYEE_ITEM = {
    "type": "object",
    "required": [
        "employee_id", "name", "department", "current_position_id",
        "target_position_id", "years_of_experience", "skills",
    ],
    "additionalProperties": False,
    "properties": {
        "employee_id": {"type": "string", "pattern": r"^EMP_\d{3}$"},
        "name": {"type": "string", "minLength": 1},
        "department": {"type": "string", "minLength": 1},
        "current_position_id": {"type": "string", "pattern": r"^POS_\d{3}$"},
        "target_position_id": {"type": "string", "pattern": r"^POS_\d{3}$"},
        "years_of_experience": {"type": "integer", "minimum": 0, "maximum": 45},
        "skills": {
            "type": "array",
            "minItems": 5,
            "items": {
                "type": "object",
                "required": ["skill_id", "level", "evidence"],
                "additionalProperties": False,
                "properties": {
                    "skill_id": {"type": "string", "pattern": r"^SKILL_\d{3}$"},
                    "level": _LEVEL,
                    "evidence": {
                        "type": "object",
                        "required": [
                            "assessment_score", "project_experience",
                            "self_assessment", "training_records",
                        ],
                        "additionalProperties": False,
                        "properties": {
                            "assessment_score": {"type": "integer", "minimum": 0, "maximum": 100},
                            "project_experience": {"type": "string"},
                            "self_assessment": _LEVEL,
                            "training_records": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
        },
    },
}

#: 四类数据的统一 JSON Schema(draft 2020-12)
SCHEMAS: dict[str, dict[str, Any]] = {
    "skills": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "skillbridge/skills.schema.json",
        "title": "SkillBridge 统一技能库",
        "type": "object",
        "required": ["generated_at", "skills"],
        "additionalProperties": False,
        "properties": {
            "generated_at": {"type": "string", "minLength": 1},
            "skills": {"type": "array", "minItems": 1, "items": _SKILL_ITEM},
        },
    },
    "positions": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "skillbridge/positions.schema.json",
        "title": "SkillBridge 岗位能力模型",
        "type": "object",
        "required": ["generated_at", "positions"],
        "additionalProperties": False,
        "properties": {
            "generated_at": {"type": "string", "minLength": 1},
            "positions": {"type": "array", "minItems": 1, "items": _POSITION_ITEM},
        },
    },
    "courses": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "skillbridge/courses.schema.json",
        "title": "SkillBridge 课程数据(Microsoft Learn)",
        "type": "object",
        "required": ["generated_at", "courses"],
        "additionalProperties": False,
        "properties": {
            "generated_at": {"type": "string", "minLength": 1},
            "courses": {"type": "array", "minItems": 1, "items": _COURSE_ITEM},
        },
    },
    "employees": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "skillbridge/employees.schema.json",
        "title": "SkillBridge 模拟员工画像",
        "type": "object",
        "required": ["generated_at", "seed", "employees"],
        "additionalProperties": False,
        "properties": {
            "generated_at": {"type": "string", "minLength": 1},
            "seed": {"type": "integer"},
            "employees": {"type": "array", "minItems": 1, "items": _EMPLOYEE_ITEM},
        },
    },
}


def validate_instance(instance: Any, schema_name: str) -> list[str]:
    """按名称校验数据实例,返回错误信息列表(空列表 = 通过)。"""
    schema = SCHEMAS[schema_name]
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{'/'.join(str(p) for p in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(instance), key=str)
    ]


def _check_dag(courses: list[dict]) -> list[str]:
    """课程前置关系必须是 DAG(无环、无自引用)。"""
    errors: list[str] = []
    ids = {course["course_id"] for course in courses}
    graph = {
        course["course_id"]: [pre for pre in course.get("prerequisites", [])]
        for course in courses
    }
    for course_id, pres in graph.items():
        if course_id in pres:
            errors.append(f"课程 {course_id} 的前置课程包含自身")
    # Kahn 拓扑排序检测环(边方向:prerequisite → course)
    dependents: dict[str, list[str]] = {cid: [] for cid in graph}
    for cid, pres in graph.items():
        for pre in pres:
            if pre in dependents:
                dependents[pre].append(cid)
    indegree = {cid: len(pres) for cid, pres in graph.items()}
    queue = [cid for cid, deg in indegree.items() if deg == 0]
    seen = 0
    while queue:
        node = queue.pop()
        seen += 1
        for dep in dependents[node]:
            indegree[dep] -= 1
            if indegree[dep] == 0:
                queue.append(dep)
    if seen != len(graph):
        cyclic = sorted(cid for cid, deg in indegree.items() if deg > 0)
        errors.append(f"课程前置关系存在环,涉及: {cyclic}")
    return errors


def validate_referential(
    skills: dict[str, Any],
    positions: dict[str, Any],
    courses: dict[str, Any],
    employees: dict[str, Any],
) -> list[str]:
    """跨文件引用完整性校验。

    - 岗位 / 课程 / 员工引用的 skill_id 必须存在于技能库;
    - 员工引用的 position_id 必须存在于岗位数据;
    - 课程 prerequisites 必须指向存在的 course_id,且构成 DAG;
    - 各类 ID 不得重复。
    """
    errors: list[str] = []

    skill_ids = [s["skill_id"] for s in skills["skills"]]
    if len(skill_ids) != len(set(skill_ids)):
        errors.append("技能库存在重复 skill_id")
    skill_id_set = set(skill_ids)

    position_ids = [p["position_id"] for p in positions["positions"]]
    if len(position_ids) != len(set(position_ids)):
        errors.append("岗位数据存在重复 position_id")
    position_id_set = set(position_ids)

    for position in positions["positions"]:
        for skill in position["skills"]:
            if skill["skill_id"] not in skill_id_set:
                errors.append(
                    f"岗位 {position['position_id']} 引用了未知技能 {skill['skill_id']}"
                )

    course_ids = [c["course_id"] for c in courses["courses"]]
    if len(course_ids) != len(set(course_ids)):
        errors.append("课程数据存在重复 course_id")
    course_id_set = set(course_ids)

    for course in courses["courses"]:
        for skill_id in course["skills"]:
            if skill_id not in skill_id_set:
                errors.append(f"课程 {course['course_id']} 引用了未知技能 {skill_id}")
        for pre in course["prerequisites"]:
            if pre not in course_id_set:
                errors.append(f"课程 {course['course_id']} 的前置课程 {pre} 不存在")
    errors.extend(_check_dag(courses["courses"]))

    employee_ids = [e["employee_id"] for e in employees["employees"]]
    if len(employee_ids) != len(set(employee_ids)):
        errors.append("员工数据存在重复 employee_id")

    for employee in employees["employees"]:
        for pid in (employee["current_position_id"], employee["target_position_id"]):
            if pid not in position_id_set:
                errors.append(f"员工 {employee['employee_id']} 引用了未知岗位 {pid}")
        for skill in employee["skills"]:
            if skill["skill_id"] not in skill_id_set:
                errors.append(
                    f"员工 {employee['employee_id']} 引用了未知技能 {skill['skill_id']}"
                )

    return errors


def validate_all(
    skills: dict[str, Any],
    positions: dict[str, Any],
    courses: dict[str, Any],
    employees: dict[str, Any],
) -> list[str]:
    """Schema + 引用完整性全量校验;返回全部错误(空列表 = 通过)。"""
    errors: list[str] = []
    for name, instance in (
        ("skills", skills), ("positions", positions),
        ("courses", courses), ("employees", employees),
    ):
        errors.extend(f"[{name}] {e}" for e in validate_instance(instance, name))
    errors.extend(validate_referential(skills, positions, courses, employees))
    return errors
