"""知识图谱查询接口(阶段 2A)。

对应大纲第四节「这一模块主要解决」的前三问:

- :func:`position_required_skills`    岗位需要什么能力?
- :func:`course_taught_skills`       课程能够培养什么能力?
- :func:`course_prerequisite_chain`  课程之间有什么前置关系?

辅助查询(大纲第七节 Candidate Generation 的输入):

- :func:`courses_teaching_skill`     哪些课程教授指定技能?

所有查询的名称参数都经过统一的名称解析(:func:`resolve_key`):
ID 精确 → 名称精确(忽略大小写)→ 别名精确 → 双向包含 → 词元模糊。
因此大纲示例中的「Develop AI Agents」能解析到真实课程
「Build and extend AI agents with Microsoft Foundry」,
中文别名「智能体」能解析到技能 AI Agent。
"""

from __future__ import annotations

import re
from typing import Any

from neo4j import Driver, Session

from skillbridge.config import get_settings

#: 词元模糊匹配阈值:查询词元至少 60% 出现在目标名称 / 别名中
FUZZY_THRESHOLD = 0.6

#: 词元切分:非字母 / 数字 / 中文字符均为分隔符
_TOKEN_SPLIT = re.compile(r"[^0-9a-z\u4e00-\u9fff]+")


def _normalize(text: str) -> str:
    """名称标准化:小写、压缩空白、去首尾标点。"""
    return " ".join(text.lower().split()).strip(" .;:,")


def _tokens(text: str) -> set[str]:
    """切分词元(小写);空串与纯标点被丢弃。"""
    return {token for token in _TOKEN_SPLIT.split(text.lower()) if token}


def resolve_key(key: str, items: list[dict[str, Any]]) -> dict[str, Any] | None:
    """把用户输入解析为图中的节点;未命中返回 ``None``。

    ``items`` 为候选节点列表,每项至少含 ``id`` 与 ``name``,
    技能节点可附带 ``aliases``(别名列表)。

    解析层级:
    1. ID 精确(POS_005 / CRS_006 / SKILL_009);
    2. 名称精确(忽略大小写与多余空白);
    3. 别名精确(忽略大小写);
    4. 双向包含(「AI concepts」→「Introduction to AI concepts」);
    5. 词元模糊:查询词元 ≥ 60% 出现在目标名称 / 别名中,
       得分相同时取更短名称(更具体),仍相同取字典序。
    """
    if not key or not key.strip():
        return None
    items = sorted(items, key=lambda item: (item["name"], item["id"]))
    key_norm = _normalize(key)
    key_tokens = _tokens(key)

    # 1) ID 精确
    for item in items:
        if key.strip() == item["id"]:
            return item

    # 2) 名称精确
    for item in items:
        if key_norm == _normalize(item["name"]):
            return item

    # 3) 别名精确
    for item in items:
        for alias in item.get("aliases") or []:
            if key_norm == _normalize(alias):
                return item

    # 4) 双向包含
    for item in items:
        name_norm = _normalize(item["name"])
        if key_norm and (key_norm in name_norm or name_norm in key_norm):
            return item

    # 5) 词元模糊
    best: dict[str, Any] | None = None
    best_rank: tuple[float, int, str] | None = None
    for item in items:
        name_tokens = _tokens(item["name"])
        for alias in item.get("aliases") or []:
            name_tokens |= _tokens(alias)
        if not key_tokens or not name_tokens:
            continue
        score = len(key_tokens & name_tokens) / len(key_tokens)
        if score < FUZZY_THRESHOLD:
            continue
        rank = (-score, len(item["name"]), item["name"])
        if best_rank is None or rank < best_rank:
            best, best_rank = item, rank
    return best


def _require(key: str, items: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    """解析节点;未命中时抛 :class:`LookupError` 并列出可选项。"""
    item = resolve_key(key, items)
    if item is None:
        names = "、".join(item["name"] for item in items)
        raise LookupError(f"未找到{kind}「{key}」;当前可选:{names}")
    return item


def _session(driver: Driver, database: str | None) -> Session:
    """打开会话;database 缺省时取 ``NEO4J_DATABASE`` 配置。"""
    return driver.session(database=database or get_settings().neo4j_database)


#: 课程候选(名称解析 + 课程基本信息)
_COURSE_ITEMS = """
MATCH (c:Course)
RETURN c.course_id AS id, c.name AS name, c.uid AS uid,
       c.difficulty AS difficulty, c.duration_minutes AS duration_minutes,
       c.url AS url
ORDER BY name
"""


# ---------------------------------------------------------------------------
# 查询一:岗位技能要求
# ---------------------------------------------------------------------------

def position_required_skills(
    driver: Driver, position: str, *, database: str | None = None
) -> dict[str, Any]:
    """查询岗位的技能要求(大纲第四节:岗位需要什么能力?)。

    :param position: 岗位名称或 position_id(支持大小写 / 包含 / 词元模糊)。
    :return: ``{"position": {position_id, name}, "skills": [...]}``;
        技能按重要度降序,每项含 skill_id / name / category / description /
        importance / required_level / sources。
    :raises LookupError: 岗位不存在。
    """
    with _session(driver, database) as session:
        items = [
            {"id": record["id"], "name": record["name"]}
            for record in session.run(
                "MATCH (p:Position) "
                "RETURN p.position_id AS id, p.name AS name ORDER BY name"
            )
        ]
        item = _require(position, items, "岗位")
        skills = [
            dict(record)
            for record in session.run(
                """
                MATCH (:Position {position_id: $id})-[r:REQUIRES]->(s:Skill)
                RETURN s.skill_id AS skill_id, s.name AS name,
                       s.category AS category, s.description AS description,
                       r.importance AS importance,
                       r.required_level AS required_level, r.sources AS sources
                ORDER BY r.importance DESC, s.skill_id
                """,
                id=item["id"],
            )
        ]
    return {
        "position": {"position_id": item["id"], "name": item["name"]},
        "skills": skills,
    }


# ---------------------------------------------------------------------------
# 查询二:课程覆盖技能
# ---------------------------------------------------------------------------

def course_taught_skills(
    driver: Driver, course: str, *, database: str | None = None
) -> dict[str, Any]:
    """查询课程覆盖(教授)的技能(大纲第四节:课程能够培养什么能力?)。

    :param course: 课程名称或 course_id(支持模糊解析)。
    :return: ``{"course": {course_id, name, difficulty, duration_minutes, url},
        "skills": [{skill_id, name, category}, ...]}``。
    :raises LookupError: 课程不存在。
    """
    with _session(driver, database) as session:
        items = [dict(record) for record in session.run(_COURSE_ITEMS)]
        item = _require(course, items, "课程")
        skills = [
            dict(record)
            for record in session.run(
                """
                MATCH (:Course {course_id: $id})-[:TEACHES]->(s:Skill)
                RETURN s.skill_id AS skill_id, s.name AS name,
                       s.category AS category
                ORDER BY s.skill_id
                """,
                id=item["id"],
            )
        ]
    return {
        "course": {
            "course_id": item["id"],
            "name": item["name"],
            "difficulty": item["difficulty"],
            "duration_minutes": item["duration_minutes"],
            "url": item["url"],
        },
        "skills": skills,
    }


# ---------------------------------------------------------------------------
# 查询三:前置链路
# ---------------------------------------------------------------------------

def course_prerequisite_chain(
    driver: Driver, course: str, *, database: str | None = None
) -> dict[str, Any]:
    """查询课程的全部前置链路(大纲第四节:课程之间有什么前置关系?)。

    沿 PREREQUISITE 关系做传递闭包,直到根课程;结果按拓扑序排列
    (根在前,可直接按顺序学习)。每一步的 ``depth`` 为该课程距目标
    课程的最长链长度(保证其全部前置都已出现),``prerequisites``
    为链内的直接前置课程。

    :param course: 课程名称或 course_id(支持模糊解析)。
    :return: ``{"course": {...}, "prerequisites": [...],
        "total_duration_minutes": int}``;无前置时 ``prerequisites`` 为空。
    :raises LookupError: 课程不存在。
    """
    with _session(driver, database) as session:
        items = [dict(record) for record in session.run(_COURSE_ITEMS)]
        item = _require(course, items, "课程")
        rows = [
            dict(record)
            for record in session.run(
                """
                MATCH (start:Course {course_id: $id})
                      -[rels:PREREQUISITE*1..]->(pre:Course)
                WITH pre, max(size(rels)) AS depth
                OPTIONAL MATCH (pre)-[:PREREQUISITE]->(direct:Course)
                WITH pre, depth, collect(direct.course_id) AS direct_ids
                RETURN pre.course_id AS course_id, pre.name AS name,
                       pre.difficulty AS difficulty,
                       pre.duration_minutes AS duration_minutes,
                       depth, direct_ids
                ORDER BY depth DESC, pre.name
                """,
                id=item["id"],
            )
        ]

    chain_ids = {row["course_id"] for row in rows}
    prerequisites = [
        {
            "course_id": row["course_id"],
            "name": row["name"],
            "difficulty": row["difficulty"],
            "duration_minutes": row["duration_minutes"],
            "depth": row["depth"],
            "prerequisites": sorted(set(row["direct_ids"]) & chain_ids),
        }
        for row in rows
    ]
    return {
        "course": {
            "course_id": item["id"],
            "name": item["name"],
            "difficulty": item["difficulty"],
            "duration_minutes": item["duration_minutes"],
            "url": item["url"],
        },
        "prerequisites": prerequisites,
        "total_duration_minutes": sum(
            step["duration_minutes"] for step in prerequisites
        ),
    }


# ---------------------------------------------------------------------------
# 辅助查询:教授指定技能的课程(阶段 3A 候选生成的输入)
# ---------------------------------------------------------------------------

def courses_teaching_skill(
    driver: Driver, skill: str, *, database: str | None = None
) -> dict[str, Any]:
    """查询教授指定技能的课程(大纲第七节 Candidate Generation)。

    :param skill: 技能名称、别名或 skill_id(如「AI Agent」「智能体」)。
    :return: ``{"skill": {skill_id, name}, "courses": [...]}``;
        课程按 course_id 升序,每项含 course_id / name / difficulty /
        duration_minutes / url。
    :raises LookupError: 技能不存在。
    """
    with _session(driver, database) as session:
        items = [
            dict(record)
            for record in session.run(
                """
                MATCH (s:Skill)
                RETURN s.skill_id AS id, s.name AS name, s.aliases AS aliases
                ORDER BY name
                """
            )
        ]
        item = _require(skill, items, "技能")
        courses = [
            dict(record)
            for record in session.run(
                """
                MATCH (c:Course)-[:TEACHES]->(:Skill {skill_id: $id})
                RETURN c.course_id AS course_id, c.name AS name,
                       c.difficulty AS difficulty,
                       c.duration_minutes AS duration_minutes, c.url AS url
                ORDER BY c.course_id
                """,
                id=item["id"],
            )
        ]
    return {
        "skill": {"skill_id": item["id"], "name": item["name"]},
        "courses": courses,
    }
