"""图谱查询:候选课程的传递前置闭包(学习路径 DAG 的输入)。

一次 Cypher(单会话):给定候选课程(根),沿 ``PREREQUISITE*0..``
做传递闭包,返回根 + 全部前置课程的完整元数据——名称 / 难度 /
时长 / URL / 所授技能 / 直接前置,即大纲第八节「补齐必须前置
课程」所需的全部信息。零长度路径使根本身(候选课程)也在结果中,
候选与前置统一为 :data:`learning_path.models.PathCourse` 对象。
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from neo4j import Driver

from learning_path.models import PathCourse
from skillbridge.config import get_settings

# 候选课程(根)→ 传递前置闭包(含根本身),携带 DAG 所需全部元数据
_QUERY_CLOSURE = """
UNWIND $root_ids AS rid
MATCH (root:Course {course_id: rid})
MATCH (root)-[:PREREQUISITE*0..]->(pre:Course)
WITH DISTINCT pre
OPTIONAL MATCH (pre)-[:TEACHES]->(s:Skill)
WITH pre, collect(DISTINCT s.skill_id) AS skills
OPTIONAL MATCH (pre)-[:PREREQUISITE]->(direct:Course)
RETURN pre.course_id AS course_id, pre.name AS name,
       pre.difficulty AS difficulty,
       pre.duration_minutes AS duration_minutes, pre.url AS url,
       skills,
       collect(DISTINCT direct.course_id) AS prerequisite_ids
ORDER BY course_id
"""


def fetch_course_closure(
    driver: Driver,
    root_ids: Iterable[str],
    *,
    database: str | None = None,
) -> dict[str, PathCourse]:
    """拉取根课程及其全部传递前置课程(完整元数据)。

    :param driver: Neo4j 驱动(见 :func:`skillbridge.db.neo4j_driver`)。
    :param root_ids: 根课程 id(通常是候选课程的 course_id)。
    :param database: Neo4j 数据库(默认取 ``NEO4J_DATABASE`` 配置)。
    :return: course_id → 课程对象(含根与全部前置);空输入返回空目录。
    """
    roots = sorted(set(root_ids))
    if not roots:
        return {}

    catalog: dict[str, PathCourse] = {}
    with driver.session(
        database=database or get_settings().neo4j_database
    ) as session:
        for record in session.run(_QUERY_CLOSURE, root_ids=roots):
            row: dict[str, Any] = dict(record)
            catalog[row["course_id"]] = PathCourse(
                course_id=row["course_id"],
                name=row["name"],
                difficulty=row["difficulty"],
                duration_minutes=int(row["duration_minutes"]),
                url=row["url"] or "",
                taught_skills=frozenset(row["skills"]),
                prerequisites=frozenset(row["prerequisite_ids"]),
            )
    return catalog
