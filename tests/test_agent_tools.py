"""Agent 工具集测试(大纲第十节):需求理解 + 5 个工具的编排与降级。

- 需求理解:大纲第十节示例问题 → 李明 / AI Engineer / 每周 4 小时 / 8 周;
- 工具全部委托已有模块,验收真实数据:李明岗位准备度 29.6%、12 项缺口、
  Top-5 推荐、8 周截止课表;
- 后端不可用(Neo4j / pgvector)时工具返回失败 payload,不抛异常;
- RAG 离线降级:内存库 + 词面编码 + 内置培训制度文档。

推荐 / 路径工具需要 Neo4j(先 ``make up``,与 tests/test_recommendation.py
同一模式:模块级 fixture 离线采集数据并构建图谱)。
"""

from __future__ import annotations

import pytest

import agent.tools as agent_tools
from agent import (
    TOOL_NAMES,
    TOOL_SCHEMAS,
    get_employee_profile,
    get_skill_gap,
    LLMError,
    LLMResponse,
    parse_intent_llm,
    parse_intent_rules,
    rag_query,
    recommend_courses,
    generate_learning_path,
    reset_caches,
    ToolCall,
)
from agent.tools import _build_rag_pipeline, _pgvector_dim
from data.collect import collect_all
from knowledge_graph import builder
from neo4j.exceptions import ServiceUnavailable
from skillbridge.db import neo4j_driver

#: 大纲第十节验收示例问题
EXAMPLE_QUESTION = "我是Java后端,想转AI Engineer,每周4小时,帮我规划"


# ---------------------------------------------------------------------------
# 公共 fixture:离线数据 + 图谱(推荐 / 路径工具需要)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def graph(tmp_path_factory):
    """离线采集数据并构建知识图谱一次,供本模块全部测试复用。"""
    out_dir = tmp_path_factory.mktemp("processed")
    raw_dir = tmp_path_factory.mktemp("raw")
    collect_all(raw_dir=raw_dir, out_dir=out_dir, offline=True)
    driver = neo4j_driver()
    builder.build_graph(driver, out_dir)
    try:
        yield driver
    finally:
        driver.close()


@pytest.fixture(autouse=True)
def _isolate_rag_cache():
    """每个测试前后清空 RAG / 数据缓存,避免后端探测结果互相污染。"""
    reset_caches()
    yield
    reset_caches()


# ---------------------------------------------------------------------------
# 需求理解(规则模式)
# ---------------------------------------------------------------------------


def test_parse_intent_rules_example_question():
    """示例问题 → 李明 / AI Engineer / 每周 4 小时 / 8 周截止 / 要完整规划。"""
    intent = parse_intent_rules(EXAMPLE_QUESTION)
    assert intent.employee_id == "EMP_001"
    assert intent.employee_name == "李明"
    assert intent.target_position_id == "POS_005"
    assert intent.target_position_name == "AI Engineer"
    assert intent.hours_per_week == 4.0
    assert intent.deadline_weeks == 8
    assert intent.wants_plan is True
    assert intent.wants_recommendation is True  # 规划隐含推荐
    assert intent.wants_qa is False


def test_parse_intent_rules_by_name_and_custom_hours():
    """显式姓名 + 自定义时长 / 截止周数解析。"""
    intent = parse_intent_rules("张伟想转数据科学家,每周6小时,12周内完成")
    assert intent.employee_id == "EMP_003"
    assert intent.employee_name == "张伟"
    assert intent.target_position_name == "Data Scientist"
    assert intent.hours_per_week == 6.0
    assert intent.deadline_weeks == 12


def test_parse_intent_rules_defaults():
    """未指明员工 / 岗位 / 时间 → 默认李明 + 档案目标岗位 + 4 小时 / 8 周。"""
    intent = parse_intent_rules("帮我规划")
    assert intent.employee_id == "EMP_001"
    assert intent.target_position_name == "AI Engineer"
    assert intent.hours_per_week == 4.0
    assert intent.deadline_weeks == 8


def test_parse_intent_rules_qa_question():
    """制度 / 为什么类问题 → wants_qa,不强制课表。"""
    intent = parse_intent_rules("公司的培训费报销制度是怎么规定的?")
    assert intent.wants_qa is True
    assert intent.wants_plan is False


# ---------------------------------------------------------------------------
# 需求理解(LLM 模式,桩客户端)
# ---------------------------------------------------------------------------


class _StubLLMClient:
    """按脚本顺序返回预设响应的 LLM 桩(记录调用供断言)。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def chat(self, messages, *, tools=None, temperature=0.0):
        self.calls.append({"messages": list(messages), "tools": tools})
        if not self.script:
            raise LLMError("脚本用尽")
        return self.script.pop(0)


def test_parse_intent_llm_structured_output():
    """LLM 输出合法 JSON → 结构化意图;岗位名归一化匹配岗位库。"""
    client = _StubLLMClient(
        [
            LLMResponse(
                content=(
                    '{"employee_id": "EMP_001", "target_position": "AI Engineer",'
                    '"hours_per_week": 6, "deadline_weeks": 12,'
                    '"wants_plan": true, "wants_recommendation": true,'
                    '"wants_qa": false}'
                )
            )
        ]
    )
    intent = parse_intent_llm(EXAMPLE_QUESTION, client)
    assert intent.employee_id == "EMP_001"
    assert intent.employee_name == "李明"
    assert intent.target_position_id == "POS_005"
    assert intent.hours_per_week == 6.0
    assert intent.deadline_weeks == 12
    assert intent.wants_plan is True


def test_parse_intent_llm_invalid_fields_fall_back_to_rules():
    """LLM 幻觉出未知员工 / 非法时长 → 逐项回退规则解析结果。"""
    client = _StubLLMClient(
        [
            LLMResponse(
                content=(
                    '{"employee_id": "EMP_999", "target_position": "不存在岗位",'
                    '"hours_per_week": 999, "deadline_weeks": -1,'
                    '"wants_plan": false, "wants_recommendation": false,'
                    '"wants_qa": false}'
                )
            )
        ]
    )
    intent = parse_intent_llm(EXAMPLE_QUESTION, client)
    assert intent.employee_id == "EMP_001"  # 未知员工回退默认
    assert intent.target_position_id == "POS_005"  # 未知岗位回退档案目标
    assert intent.hours_per_week == 4.0  # 越界时长回退默认
    assert intent.deadline_weeks == 8


def test_parse_intent_llm_garbage_raises_for_degradation():
    """LLM 输出非 JSON → 抛 LLMError,由状态机捕获后降级规则模式。"""
    client = _StubLLMClient([LLMResponse(content="我认为你应该直接学 AI")])
    with pytest.raises(LLMError):
        parse_intent_llm(EXAMPLE_QUESTION, client)


# ---------------------------------------------------------------------------
# 工具 1 / 2:员工画像 + 能力差距(纯数据,不需要图谱)
# ---------------------------------------------------------------------------


def test_get_employee_profile_tool():
    """画像工具:李明真实数据(Java 后端 → AI Engineer,技能等级 + 证据)。"""
    result = get_employee_profile("EMP_001")
    assert result["ok"] is True
    employee = result["data"]["employee"]
    assert employee["name"] == "李明"
    assert employee["current_position_name"] == "Software Developer"
    assert employee["target_position_name"] == "AI Engineer"
    skills = {item["skill_name"]: item for item in result["data"]["skills"]}
    assert skills["Java"]["level"] >= 3  # Java 后端出身
    assert skills["Generative AI"]["level"] == 0  # 大纲第二节:GenAI = 0
    assert skills["AI Agent"]["level"] == 0  # 大纲第二节:AI Agent = 0
    evidence = skills["Python"]["evidence"]
    assert set(evidence) == {
        "assessment_score",
        "project_experience",
        "self_assessment",
        "training_records",
    }


def test_get_skill_gap_tool_real_numbers():
    """差距工具:验收数字——准备度 29.6%、12 项缺口(纯算法,不用 LLM)。"""
    result = get_skill_gap("EMP_001")
    assert result["ok"] is True
    summary = result["data"]["summary"]
    assert summary["readiness_percent"] == 29.6
    assert summary["missing_count"] == 12
    assert summary["total_gap"] == 24
    gaps = result["data"]["gaps"]
    assert len(gaps) == 12
    assert gaps[0]["skill_name"] == "Generative AI"
    assert gaps[0]["gap"] == 3
    assert "29.6" in result["summary"]


def test_tool_unknown_employee_fails_gracefully():
    """未知员工 → 失败 payload(不抛异常),错误信息可读。"""
    result = get_skill_gap("EMP_999")
    assert result["ok"] is False
    assert "未知员工" in result["error"]


# ---------------------------------------------------------------------------
# 工具 3 / 4:课程推荐 + 学习路径(需要 Neo4j 图谱)
# ---------------------------------------------------------------------------


def test_recommend_courses_tool_top5(graph):
    """推荐工具:图谱候选召回 + 五因子排序 → Top-5(委托第七节模块)。"""
    result = recommend_courses("EMP_001", top_k=5)
    assert result["ok"] is True
    data = result["data"]
    assert data["top_k"] == 5
    assert len(data["recommendations"]) == 5
    assert data["candidate_count"] >= 5
    first = data["recommendations"][0]
    assert first["rank"] == 1
    assert 0.0 < first["score"] <= 1.0
    assert first["course"]["course_id"] == "CRS_001"
    assert first["covered_gaps"]  # 推荐必须覆盖缺口
    assert first["reasons"]  # 携带推荐理由(供 LLM 解释)


def test_generate_learning_path_tool_8week_schedule(graph):
    """路径工具:每周 4 小时 / 8 周截止 → 周计划满足截止(委托第八节模块)。"""
    result = generate_learning_path("EMP_001", hours_per_week=4.0, deadline_weeks=8)
    assert result["ok"] is True
    data = result["data"]
    assert data["constraints"]["deadline_weeks"] == 8
    assert data["summary"]["fits_deadline"] is True
    assert 1 <= data["summary"]["planned_weeks"] <= 8
    assert data["weeks"][0]["week"] == 1
    # 每周负载不超过预算(每周 4 小时 = 240 分钟)
    for week in data["weeks"]:
        assert week["minutes"] <= week["budget_minutes"]
    assert data["summary"]["pruned_count"] >= 1  # 已掌握课程被剪枝


def test_graph_tools_fail_gracefully_when_neo4j_down(monkeypatch):
    """Neo4j 不可用 → 失败 payload + 启动提示,不抛异常(降级关键路径)。"""
    def _boom():
        raise ServiceUnavailable("connection refused")

    monkeypatch.setattr(agent_tools, "neo4j_driver", _boom)
    for tool in (recommend_courses, generate_learning_path):
        result = tool("EMP_001")
        assert result["ok"] is False
        assert "Neo4j" in result["error"]
        assert "make up" in result["error"]


def test_learning_path_tool_rejects_invalid_time():
    """非法时间参数(每周 0 小时)→ 失败 payload。"""
    result = generate_learning_path("EMP_001", hours_per_week=0)
    assert result["ok"] is False
    assert "时间参数非法" in result["error"]


# ---------------------------------------------------------------------------
# 工具 5:知识库问答(pgvector 优先,离线自动降级)
# ---------------------------------------------------------------------------


def test_rag_query_tool_live_or_fallback():
    """RAG 工具有界返回:pgvector 可用走真实库,否则离线降级,均 ok。"""
    result = rag_query("公司的培训制度或岗位要求是什么?")
    assert result["ok"] is True
    backend = result["data"]["backend"]
    assert "pgvector" in backend or "离线降级" in backend


def test_rag_query_tool_offline_fallback(monkeypatch):
    """pgvector 不可达 → 内存库 + 词面编码 + 内置培训制度文档,检索可命中。"""
    monkeypatch.setattr(agent_tools, "_pgvector_dim", lambda: None)
    pipeline, backend = _build_rag_pipeline()
    assert "离线降级" in backend
    assert isinstance(pipeline.store, agent_tools.MemoryVectorStore)
    result = rag_query("新员工入职培训期是多久?")
    assert result["ok"] is True
    assert result["data"]["hits"], "离线降级后应命中内置培训制度文档"
    assert "企业员工培训管理制度" in result["data"]["hits"][0]["title"]
    assert result["data"]["context"]


def test_rag_query_tool_empty_question():
    """空问题 → 失败 payload(不检索)。"""
    result = rag_query("   ")
    assert result["ok"] is False
    assert "不能为空" in result["error"]


def test_pgvector_dim_probe_returns_dimension_or_none():
    """维度探测:可达时返回已入库维度(384),异常不抛出。"""
    dim = _pgvector_dim()
    assert dim is None or dim > 0


# ---------------------------------------------------------------------------
# 工具注册表
# ---------------------------------------------------------------------------


def test_tool_registry_complete():
    """注册表覆盖大纲第十节全部 5 个工具,schema 与实现一一对应。"""
    assert TOOL_NAMES == (
        "get_employee_profile",
        "get_skill_gap",
        "recommend_courses",
        "generate_learning_path",
        "rag_query",
    )
    schema_names = {schema["function"]["name"] for schema in TOOL_SCHEMAS}
    assert schema_names == set(TOOL_NAMES)
