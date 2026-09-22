"""知识图谱模块测试(阶段 2A)。

- 单元测试(不依赖数据库):数据读取校验、名称解析规则;
- 集成测试(需要 Neo4j,先 ``make up``):构建图谱后验证验收查询——
  「AI Engineer 需要什么技能」与「Develop AI Agents 的前置课程」。
"""

from __future__ import annotations

import json

import pytest

from data.collect import collect_all
from knowledge_graph import builder, loader, queries
from skillbridge.db import neo4j_driver


# ---------------------------------------------------------------------------
# 公共 fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def processed_dir(tmp_path_factory):
    """离线采集一份标准化数据(与 data/processed/ 同构,测试隔离)。"""
    out_dir = tmp_path_factory.mktemp("processed")
    raw_dir = tmp_path_factory.mktemp("raw")
    collect_all(raw_dir=raw_dir, out_dir=out_dir, offline=True)
    return out_dir


@pytest.fixture(scope="module")
def graph(processed_dir):
    """构建知识图谱一次,供本模块全部集成测试复用。"""
    driver = neo4j_driver()
    counts = builder.build_graph(driver, processed_dir)
    try:
        yield driver, counts
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# 单元测试:数据读取
# ---------------------------------------------------------------------------

def test_loader_missing_files_hint(tmp_path):
    """数据缺失时报错并提示先运行采集,而不是抛晦涩的 JSON 错误。"""
    with pytest.raises(FileNotFoundError, match="collect"):
        loader.load_processed(tmp_path)


def test_loader_rejects_invalid_data(tmp_path):
    """未通过 Schema / 引用校验的数据拒绝进入图谱。"""
    for name in loader.DATA_FILES:
        (tmp_path / f"{name}.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="校验失败"):
        loader.load_processed(tmp_path)


def test_loader_reads_valid_data(processed_dir):
    data = loader.load_processed(processed_dir)
    assert len(data.skills["skills"]) == 18
    assert len(data.positions["positions"]) == 5
    assert len(data.courses["courses"]) == 17
    assert len(data.employees["employees"]) == 10


# ---------------------------------------------------------------------------
# 单元测试:名称解析(纯函数,不依赖数据库)
# ---------------------------------------------------------------------------

_COURSES = [
    {"id": "CRS_001", "name": "Introduction to AI concepts"},
    {"id": "CRS_004", "name": "Introduction to large language models"},
    {"id": "CRS_006", "name": "Build and extend AI agents with Microsoft Foundry"},
    {
        "id": "CRS_007",
        "name": "Implement generative AI agents with Azure Database for PostgreSQL",
    },
]


def test_resolve_by_id():
    assert queries.resolve_key("CRS_006", _COURSES)["id"] == "CRS_006"


def test_resolve_by_name_case_insensitive():
    key = "build and extend ai agents with microsoft foundry"
    assert queries.resolve_key(key, _COURSES)["id"] == "CRS_006"


def test_resolve_by_containment():
    assert queries.resolve_key("AI concepts", _COURSES)["id"] == "CRS_001"


def test_resolve_fuzzy_prefers_shorter_name():
    """「Develop AI Agents」词元模糊命中两门 Agent 课程,取更短名称。"""
    assert queries.resolve_key("Develop AI Agents", _COURSES)["id"] == "CRS_006"


def test_resolve_by_alias():
    items = [
        {"id": "SKILL_009", "name": "AI Agent", "aliases": ["智能体", "agentic ai"]},
    ]
    assert queries.resolve_key("智能体", items)["id"] == "SKILL_009"


def test_resolve_no_match_returns_none():
    assert queries.resolve_key("Cooking", _COURSES) is None
    assert queries.resolve_key("", _COURSES) is None


# ---------------------------------------------------------------------------
# 集成测试:构建
# ---------------------------------------------------------------------------

def _load_json(processed_dir, name):
    return json.loads((processed_dir / f"{name}.json").read_text(encoding="utf-8"))


def test_build_counts_match_source_data(graph, processed_dir):
    """图谱中的节点 / 关系计数与源数据逐项对齐。"""
    _, counts = graph
    skills = _load_json(processed_dir, "skills")
    positions = _load_json(processed_dir, "positions")
    courses = _load_json(processed_dir, "courses")
    employees = _load_json(processed_dir, "employees")

    assert counts["Skill"] == len(skills["skills"])
    assert counts["Position"] == len(positions["positions"])
    assert counts["Course"] == len(courses["courses"])
    assert counts["Employee"] == len(employees["employees"])

    assert counts["REQUIRES"] == sum(len(p["skills"]) for p in positions["positions"])
    assert counts["TEACHES"] == sum(len(c["skills"]) for c in courses["courses"])
    assert counts["PREREQUISITE"] == sum(
        len(c["prerequisites"]) for c in courses["courses"]
    )
    assert counts["HAS_SKILL"] == sum(len(e["skills"]) for e in employees["employees"])
    assert counts["CURRENT_POSITION"] == len(employees["employees"])
    assert counts["TARGET_POSITION"] == len(employees["employees"])


def test_rebuild_is_idempotent(graph, processed_dir):
    """整库重建与 MERGE 增量导入结果一致(可重复执行)。"""
    driver, counts = graph
    assert builder.build_graph(driver, processed_dir) == counts
    assert builder.build_graph(driver, processed_dir, wipe=False) == counts


def test_employee_has_skill_with_evidence(graph):
    """HAS_SKILL 关系携带技能等级与四类 Evidence(大纲第五节)。"""
    driver, _ = graph
    with driver.session() as session:
        record = session.run(
            """
            MATCH (e:Employee {name: $name})-[r:HAS_SKILL]->(s:Skill {name: $skill})
            RETURN r.level AS level, r.assessment_score AS score,
                   r.project_experience AS project, r.self_assessment AS self_level,
                   r.training_records AS records
            """,
            name="李明",
            skill="Java",
        ).single()
    assert record is not None
    assert 0 <= record["level"] <= 4
    assert 0 <= record["score"] <= 100
    assert record["project"]
    assert 0 <= record["self_level"] <= 4
    assert isinstance(record["records"], list)


# ---------------------------------------------------------------------------
# 集成测试:验收查询一 —— AI Engineer 需要什么技能
# ---------------------------------------------------------------------------

def test_ai_engineer_required_skills(graph):
    driver, _ = graph
    result = queries.position_required_skills(driver, "AI Engineer")

    assert result["position"] == {"position_id": "POS_005", "name": "AI Engineer"}
    skills = result["skills"]
    assert len(skills) == 14

    # 按重要度降序
    importances = [s["importance"] for s in skills]
    assert importances == sorted(importances, reverse=True)

    by_id = {s["skill_id"]: s for s in skills}
    ai_agent = by_id["SKILL_009"]
    assert ai_agent["name"] == "AI Agent"
    assert ai_agent["importance"] == 5.0
    assert ai_agent["required_level"] == 3
    assert "SKILL_006" in by_id  # Generative AI
    assert "SKILL_008" in by_id  # RAG


def test_position_lookup_variants(graph):
    """名称忽略大小写、position_id 均可查询。"""
    driver, _ = graph
    lower = queries.position_required_skills(driver, "ai engineer")
    assert lower["position"]["position_id"] == "POS_005"
    by_id = queries.position_required_skills(driver, "POS_005")
    assert len(by_id["skills"]) == 14


def test_unknown_position_raises(graph):
    driver, _ = graph
    with pytest.raises(LookupError, match="可选"):
        queries.position_required_skills(driver, "Quantum Therapist")


# ---------------------------------------------------------------------------
# 集成测试:验收查询二 —— Develop AI Agents 的前置课程
# ---------------------------------------------------------------------------

def test_develop_ai_agents_taught_skills(graph):
    """「Develop AI Agents」模糊解析到 CRS_006,覆盖 AI Agent 技能。"""
    driver, _ = graph
    result = queries.course_taught_skills(driver, "Develop AI Agents")

    assert result["course"]["course_id"] == "CRS_006"
    assert result["course"]["name"] == "Build and extend AI agents with Microsoft Foundry"
    assert {s["name"] for s in result["skills"]} == {"AI Agent", "API Development"}


def test_develop_ai_agents_prerequisite_chain(graph):
    """前置链路为传递闭包,根在前(拓扑序),含深度与直接前置。"""
    driver, _ = graph
    chain = queries.course_prerequisite_chain(driver, "Develop AI Agents")

    assert chain["course"]["course_id"] == "CRS_006"
    steps = chain["prerequisites"]
    # 根在前:AI concepts → Explore Generative AI → LLM intro
    assert [s["course_id"] for s in steps] == ["CRS_001", "CRS_003", "CRS_004"]
    assert [s["depth"] for s in steps] == [3, 2, 1]

    by_id = {s["course_id"]: s for s in steps}
    assert by_id["CRS_004"]["prerequisites"] == ["CRS_003"]
    assert by_id["CRS_003"]["prerequisites"] == ["CRS_001"]
    assert by_id["CRS_001"]["prerequisites"] == []
    assert chain["total_duration_minutes"] == 40 + 37 + 25


def test_course_without_prerequisites(graph):
    driver, _ = graph
    chain = queries.course_prerequisite_chain(driver, "Introduction to AI concepts")
    assert chain["prerequisites"] == []
    assert chain["total_duration_minutes"] == 0


# ---------------------------------------------------------------------------
# 集成测试:辅助查询 —— 哪些课程教授指定技能
# ---------------------------------------------------------------------------

def test_courses_teaching_skill(graph):
    driver, _ = graph
    result = queries.courses_teaching_skill(driver, "AI Agent")
    assert result["skill"] == {"skill_id": "SKILL_009", "name": "AI Agent"}
    assert {c["course_id"] for c in result["courses"]} == {"CRS_006", "CRS_007"}


def test_courses_teaching_skill_by_chinese_alias(graph):
    """中文别名「智能体」解析到同一技能。"""
    driver, _ = graph
    result = queries.courses_teaching_skill(driver, "智能体")
    assert result["skill"]["skill_id"] == "SKILL_009"
    assert {c["course_id"] for c in result["courses"]} == {"CRS_006", "CRS_007"}


# ---------------------------------------------------------------------------
# 集成测试:CLI
# ---------------------------------------------------------------------------

def test_cli_position_query(graph, capsys):
    from knowledge_graph.__main__ import main

    assert main(["position", "AI Engineer"]) == 0
    output = capsys.readouterr().out
    assert "AI Engineer" in output
    assert "AI Agent" in output
    assert "POS_005" in output


def test_cli_course_query(graph, capsys):
    from knowledge_graph.__main__ import main

    assert main(["course", "Develop AI Agents"]) == 0
    output = capsys.readouterr().out
    assert "Build and extend AI agents with Microsoft Foundry" in output
    assert "Introduction to AI concepts" in output  # 前置链路根节点


def test_cli_unknown_target_returns_error(graph, capsys):
    from knowledge_graph.__main__ import main

    assert main(["position", "Quantum Therapist"]) == 1
    assert capsys.readouterr().err
