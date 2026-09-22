"""Neo4j 图谱构建:从 ``data/processed/`` 导入节点与关系。

图模型(大纲第四节):

    (:Employee)-[:HAS_SKILL {level, assessment_score, ...evidence}]->(:Skill)
    (:Employee)-[:CURRENT_POSITION]->(:Position)
    (:Employee)-[:TARGET_POSITION]->(:Position)
    (:Position)-[:REQUIRES {importance, required_level, sources}]->(:Skill)
    (:Course)-[:TEACHES]->(:Skill)
    (:Course)-[:PREREQUISITE]->(:Course)

构建流程:创建约束与索引 → 清库(可选)→ UNWIND 分批导入。
节点与关系全部使用 MERGE 写入,重复执行结果一致(幂等);
``wipe=True``(默认)则整库重建,保证图谱与源数据完全对齐。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from neo4j import Driver, Session

from knowledge_graph.loader import DEFAULT_DATA_DIR, ProcessedData, load_processed
from skillbridge.config import get_settings

logger = logging.getLogger("knowledge_graph.builder")

#: 单批导入行数(UNWIND 分批;当前数据量小,为后续扩展预留)
BATCH_SIZE = 500

#: 唯一性约束(ID)与名称索引(查询接口按名称解析)
_SCHEMA_STATEMENTS = (
    "CREATE CONSTRAINT skill_id IF NOT EXISTS "
    "FOR (s:Skill) REQUIRE s.skill_id IS UNIQUE",
    "CREATE CONSTRAINT position_id IF NOT EXISTS "
    "FOR (p:Position) REQUIRE p.position_id IS UNIQUE",
    "CREATE CONSTRAINT course_id IF NOT EXISTS "
    "FOR (c:Course) REQUIRE c.course_id IS UNIQUE",
    "CREATE CONSTRAINT employee_id IF NOT EXISTS "
    "FOR (e:Employee) REQUIRE e.employee_id IS UNIQUE",
    "CREATE INDEX skill_name IF NOT EXISTS FOR (s:Skill) ON (s.name)",
    "CREATE INDEX position_name IF NOT EXISTS FOR (p:Position) ON (p.name)",
    "CREATE INDEX course_name IF NOT EXISTS FOR (c:Course) ON (c.name)",
    "CREATE INDEX employee_name IF NOT EXISTS FOR (e:Employee) ON (e.name)",
)

_IMPORT_SKILLS = """
UNWIND $rows AS row
MERGE (s:Skill {skill_id: row.skill_id})
SET s.name = row.name,
    s.category = row.category,
    s.description = row.description,
    s.aliases = row.aliases,
    s.sources = row.sources
"""

_IMPORT_POSITIONS = """
UNWIND $rows AS row
MERGE (p:Position {position_id: row.position_id})
SET p.name = row.name,
    p.description = row.description,
    p.responsibilities = row.responsibilities,
    p.sources = row.sources,
    p.esco_uri = row.esco_uri,
    p.onet_code = row.onet_code
"""

_IMPORT_COURSES = """
UNWIND $rows AS row
MERGE (c:Course {course_id: row.course_id})
SET c.uid = row.uid,
    c.name = row.name,
    c.description = row.description,
    c.difficulty = row.difficulty,
    c.duration_minutes = row.duration_minutes,
    c.learning_objectives = row.learning_objectives,
    c.url = row.url,
    c.source = row.source
"""

_IMPORT_EMPLOYEES = """
UNWIND $rows AS row
MERGE (e:Employee {employee_id: row.employee_id})
SET e.name = row.name,
    e.department = row.department,
    e.years_of_experience = row.years_of_experience
"""

_IMPORT_REQUIRES = """
UNWIND $rows AS row
MATCH (p:Position {position_id: row.position_id})
MATCH (s:Skill {skill_id: row.skill_id})
MERGE (p)-[r:REQUIRES]->(s)
SET r.importance = row.importance,
    r.required_level = row.required_level,
    r.sources = row.sources
"""

_IMPORT_TEACHES = """
UNWIND $rows AS row
MATCH (c:Course {course_id: row.course_id})
MATCH (s:Skill {skill_id: row.skill_id})
MERGE (c)-[:TEACHES]->(s)
"""

_IMPORT_PREREQUISITE = """
UNWIND $rows AS row
MATCH (c:Course {course_id: row.course_id})
MATCH (pre:Course {course_id: row.prerequisite_id})
MERGE (c)-[:PREREQUISITE]->(pre)
"""

_IMPORT_HAS_SKILL = """
UNWIND $rows AS row
MATCH (e:Employee {employee_id: row.employee_id})
MATCH (s:Skill {skill_id: row.skill_id})
MERGE (e)-[r:HAS_SKILL]->(s)
SET r.level = row.level,
    r.assessment_score = row.assessment_score,
    r.project_experience = row.project_experience,
    r.self_assessment = row.self_assessment,
    r.training_records = row.training_records
"""

_IMPORT_CURRENT_POSITION = """
UNWIND $rows AS row
MATCH (e:Employee {employee_id: row.employee_id})
MATCH (p:Position {position_id: row.position_id})
MERGE (e)-[:CURRENT_POSITION]->(p)
"""

_IMPORT_TARGET_POSITION = """
UNWIND $rows AS row
MATCH (e:Employee {employee_id: row.employee_id})
MATCH (p:Position {position_id: row.position_id})
MERGE (e)-[:TARGET_POSITION]->(p)
"""


# ---------------------------------------------------------------------------
# 源数据 → 导入行
# ---------------------------------------------------------------------------

def _skill_rows(data: ProcessedData) -> list[dict[str, Any]]:
    return [
        {
            "skill_id": s["skill_id"],
            "name": s["name"],
            "category": s["category"],
            "description": s["description"],
            "aliases": s["aliases"],
            "sources": s["sources"],
        }
        for s in data.skills["skills"]
    ]


def _position_rows(data: ProcessedData) -> list[dict[str, Any]]:
    rows = []
    for p in data.positions["positions"]:
        external = p.get("external_ids") or {}
        rows.append(
            {
                "position_id": p["position_id"],
                "name": p["name"],
                "description": p["description"],
                "responsibilities": p["responsibilities"],
                "sources": p["sources"],
                "esco_uri": external.get("esco_uri"),
                "onet_code": external.get("onet_code"),
            }
        )
    return rows


def _course_rows(data: ProcessedData) -> list[dict[str, Any]]:
    return [
        {
            "course_id": c["course_id"],
            "uid": c["uid"],
            "name": c["name"],
            "description": c["description"],
            "difficulty": c["difficulty"],
            "duration_minutes": c["duration_minutes"],
            "learning_objectives": c["learning_objectives"],
            "url": c["url"],
            "source": c["source"],
        }
        for c in data.courses["courses"]
    ]


def _employee_rows(data: ProcessedData) -> list[dict[str, Any]]:
    return [
        {
            "employee_id": e["employee_id"],
            "name": e["name"],
            "department": e["department"],
            "years_of_experience": e["years_of_experience"],
        }
        for e in data.employees["employees"]
    ]


def _requires_rows(data: ProcessedData) -> list[dict[str, Any]]:
    return [
        {
            "position_id": p["position_id"],
            "skill_id": s["skill_id"],
            "importance": s["importance"],
            "required_level": s["required_level"],
            "sources": s["sources"],
        }
        for p in data.positions["positions"]
        for s in p["skills"]
    ]


def _teaches_rows(data: ProcessedData) -> list[dict[str, Any]]:
    return [
        {"course_id": c["course_id"], "skill_id": skill_id}
        for c in data.courses["courses"]
        for skill_id in c["skills"]
    ]


def _prerequisite_rows(data: ProcessedData) -> list[dict[str, Any]]:
    return [
        {"course_id": c["course_id"], "prerequisite_id": pre}
        for c in data.courses["courses"]
        for pre in c["prerequisites"]
    ]


def _has_skill_rows(data: ProcessedData) -> list[dict[str, Any]]:
    rows = []
    for e in data.employees["employees"]:
        for s in e["skills"]:
            evidence = s["evidence"]
            rows.append(
                {
                    "employee_id": e["employee_id"],
                    "skill_id": s["skill_id"],
                    "level": s["level"],
                    "assessment_score": evidence["assessment_score"],
                    "project_experience": evidence["project_experience"],
                    "self_assessment": evidence["self_assessment"],
                    "training_records": evidence["training_records"],
                }
            )
    return rows


def _employee_position_rows(data: ProcessedData, key: str) -> list[dict[str, Any]]:
    return [
        {"employee_id": e["employee_id"], "position_id": e[key]}
        for e in data.employees["employees"]
    ]


# ---------------------------------------------------------------------------
# 构建入口
# ---------------------------------------------------------------------------

def build_graph(
    driver: Driver,
    data_dir: Path | None = None,
    *,
    wipe: bool = True,
    database: str | None = None,
) -> dict[str, int]:
    """从 ``data/processed/`` 导入,构建知识图谱;返回节点与关系计数。

    :param driver: Neo4j 驱动(见 :func:`skillbridge.db.neo4j_driver`)。
    :param data_dir: 标准化数据目录(默认 ``data/processed``)。
    :param wipe: 导入前清空数据库(默认 True,整库重建)。
    :param database: Neo4j 数据库(默认取 ``NEO4J_DATABASE`` 配置)。
    :return: 计数字典,键为节点标签(Skill/Position/Course/Employee)
        与关系类型(HAS_SKILL/REQUIRES/TEACHES/PREREQUISITE/
        CURRENT_POSITION/TARGET_POSITION)。
    """
    if data_dir is None:
        data_dir = DEFAULT_DATA_DIR
    data = load_processed(data_dir)
    db = database or get_settings().neo4j_database

    with driver.session(database=db) as session:
        for statement in _SCHEMA_STATEMENTS:
            session.run(statement).consume()
        if wipe:
            session.run("MATCH (n) DETACH DELETE n").consume()

        imports: tuple[tuple[str, list[dict[str, Any]]], ...] = (
            (_IMPORT_SKILLS, _skill_rows(data)),
            (_IMPORT_POSITIONS, _position_rows(data)),
            (_IMPORT_COURSES, _course_rows(data)),
            (_IMPORT_EMPLOYEES, _employee_rows(data)),
            (_IMPORT_REQUIRES, _requires_rows(data)),
            (_IMPORT_TEACHES, _teaches_rows(data)),
            (_IMPORT_PREREQUISITE, _prerequisite_rows(data)),
            (_IMPORT_HAS_SKILL, _has_skill_rows(data)),
            (
                _IMPORT_CURRENT_POSITION,
                _employee_position_rows(data, "current_position_id"),
            ),
            (
                _IMPORT_TARGET_POSITION,
                _employee_position_rows(data, "target_position_id"),
            ),
        )
        for query, rows in imports:
            _run_batched(session, query, rows)

        counts = _count_graph(session)

    logger.info(
        "知识图谱构建完成(%s):%s",
        data_dir,
        ", ".join(f"{key}={value}" for key, value in counts.items()),
    )
    return counts


def _run_batched(
    session: Session, query: str, rows: list[dict[str, Any]]
) -> int:
    """按 :data:`BATCH_SIZE` 分批执行 UNWIND 导入,返回导入行数。"""
    total = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        session.run(query, rows=batch).consume()
        total += len(batch)
    return total


def _count_graph(session: Session) -> dict[str, int]:
    """从数据库统计节点标签与关系类型计数(导入结果的权威来源)。"""
    counts: dict[str, int] = {}
    for record in session.run(
        "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS total"
    ):
        counts[record["label"]] = record["total"]
    for record in session.run(
        "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(*) AS total"
    ):
        counts[record["rel_type"]] = record["total"]
    return counts
