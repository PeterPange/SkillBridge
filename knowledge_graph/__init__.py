"""HR 培训知识图谱(大纲第四节,阶段 2A)。

基于 Neo4j 构建「员工—岗位—技能—课程」图谱:

    (:Employee)-[:HAS_SKILL {level, ...evidence}]->(:Skill)
    (:Employee)-[:CURRENT_POSITION / TARGET_POSITION]->(:Position)
    (:Position)-[:REQUIRES {importance, required_level}]->(:Skill)
    (:Course)-[:TEACHES]->(:Skill)
    (:Course)-[:PREREQUISITE]->(:Course)

HAS_SKILL / REQUIRES / TEACHES / PREREQUISITE 为大纲规定的四类核心关系;
CURRENT_POSITION / TARGET_POSITION 补全「员工 → 当前岗位 → 目标岗位」链路
(大纲第四节示例),供阶段 2B Skill Gap 分析使用。

结构::

    knowledge_graph/
    ├── loader.py       # data/processed/ 读取与校验
    ├── builder.py      # 图谱构建(约束 + 清库 + UNWIND 批量导入)
    ├── queries.py      # 查询接口与名称解析
    └── __main__.py     # CLI:python -m knowledge_graph build|position|course|skill

用法::

    make collect && make graph                    # 采集数据并导入 Neo4j
    python -m knowledge_graph position "AI Engineer"     # 岗位技能要求
    python -m knowledge_graph course "Develop AI Agents" # 课程技能 + 前置链路
"""

from knowledge_graph.builder import build_graph
from knowledge_graph.loader import DEFAULT_DATA_DIR, ProcessedData, load_processed
from knowledge_graph.queries import (
    course_prerequisite_chain,
    course_taught_skills,
    courses_teaching_skill,
    position_required_skills,
    resolve_key,
)

__all__ = [
    "DEFAULT_DATA_DIR",
    "ProcessedData",
    "build_graph",
    "course_prerequisite_chain",
    "course_taught_skills",
    "courses_teaching_skill",
    "load_processed",
    "position_required_skills",
    "resolve_key",
]
