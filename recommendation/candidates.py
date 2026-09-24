"""Candidate Generation(大纲第七节):按 Skill Gap 从图谱召回候选课程。

对差距报告中的每项缺口技能,沿 ``(:Course)-[:TEACHES]->(:Skill)``
关系召回教授该技能的课程(大纲示例:缺少 AI Agent → Develop AI Agents)。

一次召回共执行四条 Cypher(单会话):

1. 缺口技能 → 候选课程(TEACHES,按 course_id 去重排序);
2. 候选课程 → 全部所授技能(难度匹配因子的输入);
3. 候选课程 → 直接前置课程(前置满足因子的输入);
4. 仅作为前置出现的课程 → 名称 + 所授技能(非候选上下文)。

没有任何课程教授的缺口技能进入 ``uncovered``,推荐报告显式提示
「该缺口暂无课程覆盖」,而不是静默丢弃。
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from neo4j import Driver

from profile.models import SkillGap
from recommendation.models import CandidateCourse, CandidatePool, CourseContext
from skillbridge.config import get_settings

# 1) 缺口技能 → 候选课程(TEACHES 关系召回)
_QUERY_CANDIDATES = """
UNWIND $skill_ids AS sid
MATCH (c:Course)-[:TEACHES]->(s:Skill {skill_id: sid})
RETURN DISTINCT c.course_id AS course_id, c.name AS name,
       c.difficulty AS difficulty,
       c.duration_minutes AS duration_minutes, c.url AS url
ORDER BY c.course_id
"""

# 2) 候选课程 → 全部所授技能
_QUERY_TAUGHT_SKILLS = """
MATCH (c:Course)-[:TEACHES]->(s:Skill)
WHERE c.course_id IN $course_ids
RETURN c.course_id AS course_id, collect(s.skill_id) AS skills
"""

# 3) 候选课程 → 直接前置课程
_QUERY_PREREQUISITES = """
MATCH (c:Course)-[:PREREQUISITE]->(p:Course)
WHERE c.course_id IN $course_ids
RETURN c.course_id AS course_id, collect(p.course_id) AS prerequisite_ids
"""

# 4) 非候选前置课程 → 名称 + 所授技能(前置满足判定上下文)
_QUERY_PREREQUISITE_CONTEXT = """
MATCH (p:Course)
WHERE p.course_id IN $course_ids
OPTIONAL MATCH (p)-[:TEACHES]->(s:Skill)
RETURN p.course_id AS course_id, p.name AS name,
       collect(s.skill_id) AS skills
"""


def generate_candidates(
    driver: Driver,
    gaps: Iterable[SkillGap],
    *,
    database: str | None = None,
    exclude: Iterable[str] = (),
) -> CandidatePool:
    """按缺口技能从图谱召回候选课程。

    :param driver: Neo4j 驱动(见 :func:`skillbridge.db.neo4j_driver`)。
    :param gaps: 差距报告的缺失技能列表(:class:`profile.models.SkillGap`)。
    :param database: Neo4j 数据库(默认取 ``NEO4J_DATABASE`` 配置)。
    :param exclude: 排除的课程 course_id 集合(如员工已完成的课程,
        大纲第十一节闭环重算时不再重复推荐);被排除的课程若作为
        其他候选的前置,仍会进入前置上下文(前置满足判定需要)。
    :return: :class:`~recommendation.models.CandidatePool`,候选课程
        按 course_id 升序;缺口为空时返回空池。
    """
    gap_list = list(gaps)
    excluded = frozenset(exclude)
    skill_ids = sorted({gap.skill_id for gap in gap_list})
    if not skill_ids:
        return CandidatePool()

    with driver.session(
        database=database or get_settings().neo4j_database
    ) as session:
        candidate_rows = [
            dict(record)
            for record in session.run(_QUERY_CANDIDATES, skill_ids=skill_ids)
            if record["course_id"] not in excluded
        ]
        course_ids = [row["course_id"] for row in candidate_rows]

        taught: dict[str, frozenset[str]] = {}
        prereq: dict[str, frozenset[str]] = {}
        context: dict[str, CourseContext] = {}
        if course_ids:
            for record in session.run(
                _QUERY_TAUGHT_SKILLS, course_ids=course_ids
            ):
                taught[record["course_id"]] = frozenset(record["skills"])
            for record in session.run(
                _QUERY_PREREQUISITES, course_ids=course_ids
            ):
                prereq[record["course_id"]] = frozenset(
                    record["prerequisite_ids"]
                )

            # 仅作为前置出现、自身不是候选的课程:补充名称与所授技能
            context_ids = sorted(
                {pid for ids in prereq.values() for pid in ids}
                - set(course_ids)
            )
            if context_ids:
                for record in session.run(
                    _QUERY_PREREQUISITE_CONTEXT, course_ids=context_ids
                ):
                    context[record["course_id"]] = CourseContext(
                        name=record["name"],
                        skills=frozenset(record["skills"]),
                    )

    candidates = tuple(
        CandidateCourse(
            course_id=row["course_id"],
            name=row["name"],
            difficulty=row["difficulty"],
            duration_minutes=int(row["duration_minutes"]),
            url=row["url"] or "",
            taught_skills=taught.get(row["course_id"], frozenset()),
            prerequisites=prereq.get(row["course_id"], frozenset()),
        )
        for row in candidate_rows
    )

    covered_ids = {
        skill_id
        for course in candidates
        for skill_id in course.taught_skills
    }
    uncovered = tuple(
        gap for gap in gap_list if gap.skill_id not in covered_ids
    )
    return CandidatePool(
        candidates=candidates,
        prerequisite_context=context,
        uncovered=uncovered,
    )
