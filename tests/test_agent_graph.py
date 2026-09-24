"""HR Training Agent 状态机测试(大纲第十节验收)。

- **全链路验收**:示例问题「我是Java后端,想转AI Engineer,每周4小时,
  帮我规划」走通 understand → plan → execute → generate,规则模式回答
  引用李明的真实数据(29.6% 准备度、12 项缺口、Top-5 推荐、8 周课表);
- **LLM 模式**:桩客户端验证结构化意图提取 → function calling 规划 →
  引用工具数据生成回答;
- **降级**:LLM 调用失败就地降级规则模式,主流程不中断;
- **CLI**:`python -m agent` 文本与 JSON 输出。

推荐 / 路径工具需要 Neo4j(先 ``make up``),与 tests/test_recommendation.py
同一 fixture 模式。
"""

from __future__ import annotations

import json

import pytest

import agent.tools as agent_tools
from agent import (
    HRTrainingAgent,
    LLMClient,
    LLMError,
    LLMResponse,
    TOOL_SCHEMAS,
    ToolCall,
    run_agent,
)
from agent.answer import render_rule_answer
from agent.graph import MODE_LLM, MODE_RULE
from agent.intent import Intent, parse_intent_rules
from data.collect import collect_all
from knowledge_graph import builder
from skillbridge.db import neo4j_driver

#: 大纲第十节验收示例问题
EXAMPLE_QUESTION = "我是Java后端,想转AI Engineer,每周4小时,帮我规划"

#: 规则模式标准工具链(大纲第十节执行序列)
RULE_PLAN = [
    "get_employee_profile",
    "get_skill_gap",
    "recommend_courses",
    "generate_learning_path",
]


# ---------------------------------------------------------------------------
# 公共 fixture:离线数据 + 图谱
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


@pytest.fixture(scope="module")
def agent(graph):
    """规则模式 Agent(LLM 未配置,自动降级)。"""
    return HRTrainingAgent(client=LLMClient(), mode="auto")


# ---------------------------------------------------------------------------
# LLM 桩客户端
# ---------------------------------------------------------------------------


class StubLLMClient(LLMClient):
    """按脚本顺序返回预设响应的 LLM 桩(记录调用供断言)。"""

    def __init__(self, script):
        super().__init__(api_key="stub-key", model="stub-model", enabled=True)
        self.script = list(script)
        self.calls: list[dict] = []

    def chat(self, messages, *, tools=None, temperature=0.0):
        self.calls.append({"messages": list(messages), "tools": tools})
        if not self.script:
            raise LLMError("脚本用尽")
        return self.script.pop(0)


class BrokenLLMClient(LLMClient):
    """始终失败的 LLM 客户端(模拟网络 / 服务不可用)。"""

    def __init__(self):
        super().__init__(api_key="broken-key", model="broken-model", enabled=True)

    def chat(self, messages, *, tools=None, temperature=0.0):
        raise LLMError("模拟 LLM 服务不可用")


# ---------------------------------------------------------------------------
# 全链路验收:示例问题(规则模式)
# ---------------------------------------------------------------------------


def test_full_chain_example_question_references_real_data(agent):
    """示例问题走通全链路,回答引用李明的真实数据(大纲第十节验收)。"""
    result = agent.run(EXAMPLE_QUESTION)

    # 需求理解:李明 → AI Engineer,每周 4 小时,截止 8 周
    intent = result["intent"]
    assert intent["employee_id"] == "EMP_001"
    assert intent["employee_name"] == "李明"
    assert intent["target_position_name"] == "AI Engineer"
    assert intent["hours_per_week"] == 4.0
    assert intent["deadline_weeks"] == 8

    # 规划:标准工具链(理解需求 → 规划工具调用)
    assert [item["tool"] for item in result["plan"]] == RULE_PLAN

    # 执行:全部工具成功,结果来自真实数据
    tool_results = result["tool_results"]
    assert all(payload["ok"] for payload in tool_results.values())
    assert tool_results["get_skill_gap"]["data"]["summary"]["readiness_percent"] == 29.6
    assert tool_results["get_skill_gap"]["data"]["summary"]["missing_count"] == 12
    assert len(tool_results["recommend_courses"]["data"]["recommendations"]) == 5
    assert (
        tool_results["generate_learning_path"]["data"]["summary"]["fits_deadline"]
        is True
    )

    # 生成:回答引用真实数据(29.6% 准备度、12 项缺口、Top-5、8 周课表)
    answer = result["answer"]
    assert "李明" in answer
    assert "29.6" in answer
    assert "12 项" in answer
    assert "Top-5" in answer
    assert "8 周" in answer
    assert "Introduction to AI concepts" in answer  # 真实推荐课程
    assert result["errors"] == []


def test_full_chain_mode_is_rule_without_llm(agent):
    """LLM 未配置 → 自动降级规则模式(直接串联工具输出)。"""
    result = agent.run(EXAMPLE_QUESTION)
    assert result["mode"] == MODE_RULE


def test_qa_question_appends_rag_tool(agent):
    """制度类问题在标准链路上追加 RAG 工具(大纲第九节联动)。"""
    result = agent.run("为什么给我推荐 AI Agent 课程?公司培训制度有什么规定?")
    tools = [item["tool"] for item in result["plan"]]
    assert tools == [
        "get_employee_profile",
        "get_skill_gap",
        "recommend_courses",
        "rag_query",
    ]
    assert result["tool_results"]["rag_query"]["ok"] is True
    assert "知识库参考" in result["answer"]


def test_recommendation_only_question_skips_path(agent):
    """只要推荐、不要课表的问题不排学习路径。"""
    result = agent.run("李明转 AI Engineer 推荐什么课程?")
    tools = [item["tool"] for item in result["plan"]]
    assert "recommend_courses" in tools
    assert "generate_learning_path" not in tools


# ---------------------------------------------------------------------------
# LLM 模式(桩客户端):理解 → function calling 规划 → 生成
# ---------------------------------------------------------------------------


def _llm_script() -> list[LLMResponse]:
    """LLM 模式三步脚本:意图 JSON → 工具调用 → 最终回答。"""
    return [
        # 1) understand:结构化意图
        LLMResponse(
            content=(
                '{"employee_id": "EMP_001", "target_position": "AI Engineer",'
                '"hours_per_week": 4, "deadline_weeks": 8,'
                '"wants_plan": true, "wants_recommendation": true,'
                '"wants_qa": false}'
            )
        ),
        # 2) plan:function calling(含一个幻觉参数,execute 应按签名过滤)
        LLMResponse(
            tool_calls=(
                ToolCall(id="c1", name="get_employee_profile", args={}),
                ToolCall(id="c2", name="get_skill_gap", args={}),
                ToolCall(
                    id="c3",
                    name="recommend_courses",
                    args={"top_k": 5, "bogus": "幻觉参数"},
                ),
                ToolCall(
                    id="c4",
                    name="generate_learning_path",
                    args={"hours_per_week": 4, "deadline_weeks": 8},
                ),
            )
        ),
        # 3) generate:引用工具数据的最终回答
        LLMResponse(
            content=(
                "李明当前岗位准备度 29.6%,存在 12 项能力缺口;"
                "已为其推荐 Top-5 课程并生成 8 周学习计划。"
            )
        ),
    ]


def test_llm_mode_orchestration(graph):
    """LLM 模式:意图提取 → 工具规划(过滤幻觉参数)→ 引用数据生成。"""
    client = StubLLMClient(_llm_script())
    agent = HRTrainingAgent(client=client, mode="auto")
    result = agent.run(EXAMPLE_QUESTION)

    assert result["mode"] == MODE_LLM
    # 规划来自 LLM 的 function calling(顺序保留;幻觉参数在 execute 按签名过滤)
    assert [item["tool"] for item in result["plan"]] == [
        "get_employee_profile",
        "get_skill_gap",
        "recommend_courses",
        "generate_learning_path",
    ]
    # 幻觉参数不影响执行:工具照常成功
    assert result["tool_results"]["recommend_courses"]["ok"] is True
    # 工具真实执行成功
    assert all(payload["ok"] for payload in result["tool_results"].values())
    # 回答来自 LLM 生成
    assert result["answer"].startswith("李明当前岗位准备度 29.6%")
    # 三次 LLM 调用:意图(无 tools)/ 规划(带 tools)/ 生成(无 tools)
    assert len(client.calls) == 3
    assert client.calls[0]["tools"] is None
    assert client.calls[1]["tools"] == TOOL_SCHEMAS
    assert client.calls[2]["tools"] is None
    # 生成上下文注入了工具真实数据
    generate_prompt = json.dumps(
        client.calls[2]["messages"], ensure_ascii=False, default=str
    )
    assert "29.6" in generate_prompt


def test_llm_failure_degrades_to_rule_mode(graph):
    """LLM 全程失败 → 就地降级规则模式,回答仍引用真实数据。"""
    agent = HRTrainingAgent(client=BrokenLLMClient(), mode="llm")
    result = agent.run(EXAMPLE_QUESTION)

    assert result["mode"] == MODE_RULE
    assert result["errors"], "降级原因应记录在 errors"
    assert any("降级" in error for error in result["errors"])
    # 规则链路照常执行,回答引用真实数据
    assert [item["tool"] for item in result["plan"]] == RULE_PLAN
    assert all(payload["ok"] for payload in result["tool_results"].values())
    assert "29.6" in result["answer"]
    assert "李明" in result["answer"]


def test_llm_plans_unknown_tool_falls_back_to_rules(graph):
    """LLM 只规划未知工具 → 规划失败,降级规则链路。"""
    client = StubLLMClient(
        [
            LLMResponse(
                content=(
                    '{"employee_id": "EMP_001", "target_position": "AI Engineer",'
                    '"hours_per_week": 4, "deadline_weeks": 8,'
                    '"wants_plan": true, "wants_recommendation": true,'
                    '"wants_qa": false}'
                )
            ),
            LLMResponse(
                tool_calls=(ToolCall(id="c1", name="not_a_tool", args={}),)
            ),
        ]
    )
    agent = HRTrainingAgent(client=client, mode="auto")
    result = agent.run(EXAMPLE_QUESTION)
    # 意图来自 LLM,规划降级规则链路
    assert [item["tool"] for item in result["plan"]] == RULE_PLAN
    assert any("规划" in error for error in result["errors"])


def test_forced_rule_mode_never_calls_llm(graph):
    """--mode rule:即使 LLM 可用也不调用(确定性输出)。"""
    client = StubLLMClient(_llm_script())
    agent = HRTrainingAgent(client=client, mode="rule")
    result = agent.run(EXAMPLE_QUESTION)
    assert result["mode"] == MODE_RULE
    assert client.calls == []
    assert [item["tool"] for item in result["plan"]] == RULE_PLAN


# ---------------------------------------------------------------------------
# 回答渲染(规则模式)
# ---------------------------------------------------------------------------


def test_render_rule_answer_flags_tool_failures():
    """工具失败时回答显式提示数据缺失,不静默、不编造。"""
    intent = parse_intent_rules(EXAMPLE_QUESTION)
    tool_results = {
        "get_employee_profile": {
            "tool": "get_employee_profile",
            "ok": False,
            "data": None,
            "error": "Neo4j 不可用:...",
            "summary": "",
        }
    }
    answer = render_rule_answer(intent, tool_results)
    assert "暂不可用" in answer
    assert "Neo4j 不可用" in answer


def test_render_rule_answer_without_tools():
    """无工具结果 → 只输出需求理解(不崩溃)。"""
    intent = Intent(
        employee_id="EMP_001",
        employee_name="李明",
        current_position_id="POS_001",
        current_position_name="Software Developer",
        target_position_id="POS_005",
        target_position_name="AI Engineer",
        question="你好",
    )
    answer = render_rule_answer(intent, {})
    assert "李明" in answer
    assert "AI Engineer" in answer


# ---------------------------------------------------------------------------
# 便捷入口 + CLI
# ---------------------------------------------------------------------------


def test_run_agent_helper(graph):
    """:func:`run_agent` 一次性运行,返回回答文本。"""
    answer = run_agent(EXAMPLE_QUESTION, mode="rule")
    assert isinstance(answer, str)
    assert "29.6" in answer
    assert "李明" in answer


def test_cli_text_output(capsys, graph):
    """`python -m agent "示例问题"`:过程追踪 + 最终回答。"""
    from agent.__main__ import main

    code = main([EXAMPLE_QUESTION, "--quiet"])
    assert code == 0
    out = capsys.readouterr().out
    assert "李明" in out
    assert "29.6" in out
    assert "12 项" in out
    assert "Top-5" in out
    assert "8 周" in out


def test_cli_trace_shows_tool_chain(capsys, graph):
    """默认输出包含执行模式与逐工具调用追踪。"""
    from agent.__main__ import main

    code = main([EXAMPLE_QUESTION])
    assert code == 0
    out = capsys.readouterr().out
    assert "[Agent] 执行模式:规则模式" in out
    for tool in RULE_PLAN:
        assert f"[Agent] 工具调用:{tool}" in out


def test_cli_json_output(capsys, graph):
    """--json:结构化输出(模式 / 意图 / 工具链 / 工具结果 / 回答)。"""
    from agent.__main__ import main

    code = main([EXAMPLE_QUESTION, "--json"])
    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == MODE_RULE
    assert result["intent"]["employee_id"] == "EMP_001"
    assert [item["tool"] for item in result["plan"]] == RULE_PLAN
    assert result["tool_results"]["get_skill_gap"]["data"]["summary"][
        "readiness_percent"
    ] == 29.6
    assert "29.6" in result["answer"]
