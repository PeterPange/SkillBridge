"""HR Training Agent:LangGraph 状态机(大纲第十节)。

Agent 是「整个系统的智能入口和任务编排层」,状态机四个节点::

    START → understand(理解需求)
          → plan(规划工具调用)
          → execute(执行工具,plan 为空时跳过)
          → generate(生成回答) → END

两种执行模式,同一张图:

- **LLM 模式**:理解 / 规划 / 生成由 LLM 驱动
  (结构化意图提取 → function calling 选工具 → 引用工具数据作答);
- **规则模式**:LLM 不可用(未配置 ``OPENAI_API_KEY`` / ``LLM_MODEL``,
  或调用失败)时的降级方案——规则解析意图、按意图确定工具链、
  直接串联工具输出渲染回答。

任一节点内 LLM 调用失败都会**就地降级**为规则实现并记录 ``errors``,
主流程不中断,保证「LLM 不可用时降级为规则模式」。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from agent.answer import build_llm_context, render_rule_answer
from agent.intent import Intent, parse_intent_llm, parse_intent_rules
from agent.llm import LLMClient, LLMError
from agent.state import MODE_LLM, MODE_RULE, AgentState
from agent.tools import TOOL_IMPLEMENTATIONS, TOOL_SCHEMAS, run_tool

logger = logging.getLogger(__name__)

#: 需求理解节点的系统提示词(规划工具调用的前置约束)
_UNDERSTAND_SYSTEM = (
    "你是企业 HR 培训系统的需求理解模块,只输出 JSON。"
)

#: 规划节点的系统提示词:基于需求选择工具(大纲第十节工具集)
_PLAN_SYSTEM = (
    "你是企业 HR 培训系统的任务规划模块。根据已理解的需求,从可用工具中"
    "选择需要调用的工具并给出参数。只输出工具调用,不要直接回答用户问题。"
    "规划转岗培训类问题时,标准链路是:员工画像 → 能力差距 → 课程推荐"
    "→ 学习路径(时间参数用需求理解的结果);涉及公司制度 / 岗位说明时"
    "追加知识库问答工具。"
)


class HRTrainingAgent:
    """HR 培训 Agent(LangGraph 状态机)。

    :param client: LLM 客户端;``None`` 时自动构建,未配置则规则模式。
    :param mode: ``auto``(默认,按 LLM 可用性选择)/ ``llm`` / ``rule``。

    用法::

        agent = HRTrainingAgent()
        result = agent.run("我是Java后端,想转AI Engineer,每周4小时,帮我规划")
        print(result["answer"])
    """

    def __init__(self, client: LLMClient | None = None, *, mode: str = "auto"):
        self.client = client if client is not None else LLMClient()
        self.mode = mode
        self._graph = self._build_graph()

    # ------------------------------------------------------------------
    # 图构建
    # ------------------------------------------------------------------

    def _build_graph(self):
        """构建并编译状态机:understand → plan →(execute)→ generate。"""
        graph = StateGraph(AgentState)
        graph.add_node("understand", self._understand)
        graph.add_node("plan", self._plan)
        graph.add_node("execute", self._execute)
        graph.add_node("generate", self._generate)
        graph.add_edge(START, "understand")
        graph.add_edge("understand", "plan")
        # plan 为空(无需工具,如纯寒暄)时直接生成回答
        graph.add_conditional_edges(
            "plan",
            lambda state: "execute" if state.get("plan") else "generate",
            {"execute": "execute", "generate": "generate"},
        )
        graph.add_edge("execute", "generate")
        graph.add_edge("generate", END)
        return graph.compile()

    # ------------------------------------------------------------------
    # 节点 1:理解需求
    # ------------------------------------------------------------------

    def _understand(self, state: AgentState) -> dict[str, Any]:
        """理解需求:自然语言 → 结构化意图(员工 / 岗位 / 时间 / 意图)。"""
        question = state["question"]
        errors: list[str] = list(state.get("errors", []))
        intent: Intent | None = None
        mode = MODE_RULE

        if self._wants_llm():
            try:
                intent = parse_intent_llm(question, self.client)
                mode = MODE_LLM
            except LLMError as exc:
                errors.append(f"LLM 需求理解失败,降级规则模式:{exc}")
                logger.warning("LLM 意图解析失败,降级规则模式", exc_info=True)
        if intent is None:
            intent = parse_intent_rules(question)

        return {"mode": mode, "intent": intent.to_dict(), "errors": errors}

    # ------------------------------------------------------------------
    # 节点 2:规划工具调用
    # ------------------------------------------------------------------

    def _plan(self, state: AgentState) -> dict[str, Any]:
        """规划工具调用:LLM function calling 或规则链路。"""
        intent = Intent(**state["intent"])
        errors: list[str] = list(state.get("errors", []))
        plan: list[dict[str, Any]] | None = None

        if state.get("mode") == MODE_LLM:
            try:
                plan = self._plan_with_llm(intent)
            except LLMError as exc:
                errors.append(f"LLM 工具规划失败,降级规则链路:{exc}")
                logger.warning("LLM 规划失败,降级规则链路", exc_info=True)
        if plan is None:
            plan = self._plan_with_rules(intent)

        return {"plan": plan, "errors": errors}

    def _plan_with_llm(self, intent: Intent) -> list[dict[str, Any]]:
        """LLM function calling 规划:模型从工具 schema 中选择工具与参数。"""
        user = (
            f"用户问题:{intent.question}\n\n"
            f"需求理解结果:{json.dumps(intent.to_dict(), ensure_ascii=False)}\n\n"
            "请规划需要调用的工具。"
        )
        response = self.client.chat(
            [
                {"role": "system", "content": _PLAN_SYSTEM},
                {"role": "user", "content": user},
            ],
            tools=TOOL_SCHEMAS,
        )
        if not response.tool_calls:
            raise LLMError("LLM 未返回任何工具调用")
        plan: list[dict[str, Any]] = []
        for call in response.tool_calls:
            if call.name not in TOOL_IMPLEMENTATIONS:
                logger.warning("LLM 规划了未知工具 %s,已忽略", call.name)
                continue
            plan.append({"tool": call.name, "args": dict(call.args)})
        if not plan:
            raise LLMError("LLM 规划的工具全部无效")
        return plan

    @staticmethod
    def _plan_with_rules(intent: Intent) -> list[dict[str, Any]]:
        """规则链路规划(大纲第十节执行序列,确定性):

        员工画像 → 能力差距 →(推荐 →)学习路径(→ 知识库问答)
        """
        plan = [
            {"tool": "get_employee_profile", "args": {"employee_id": intent.employee_id}},
            {"tool": "get_skill_gap", "args": {"employee_id": intent.employee_id}},
        ]
        if intent.wants_recommendation or intent.wants_plan:
            plan.append(
                {
                    "tool": "recommend_courses",
                    "args": {"employee_id": intent.employee_id, "top_k": 5},
                }
            )
        if intent.wants_plan:
            plan.append(
                {
                    "tool": "generate_learning_path",
                    "args": {
                        "employee_id": intent.employee_id,
                        "hours_per_week": intent.hours_per_week,
                        "deadline_weeks": intent.deadline_weeks,
                    },
                }
            )
        if intent.wants_qa:
            plan.append(
                {"tool": "rag_query", "args": {"question": intent.question, "top_k": 4}}
            )
        return plan

    # ------------------------------------------------------------------
    # 节点 3:执行工具
    # ------------------------------------------------------------------

    @staticmethod
    def _execute(state: AgentState) -> dict[str, Any]:
        """依次执行规划的工具,汇总结构化结果(失败不中断)。"""
        import inspect

        intent = state.get("intent", {})
        results: dict[str, Any] = {}
        errors: list[str] = list(state.get("errors", []))
        for item in state.get("plan", []):
            name = item["tool"]
            args = dict(item.get("args", {}))
            # 兜底:LLM 规划的参数缺失时用需求理解结果补齐
            args.setdefault("employee_id", intent.get("employee_id"))
            if name == "rag_query":
                args.setdefault("question", intent.get("question", ""))
            # 只保留目标工具签名内声明的参数(防御 LLM 幻觉出的多余参数)
            try:
                parameters = set(inspect.signature(TOOL_IMPLEMENTATIONS[name]).parameters)
                args = {key: value for key, value in args.items() if key in parameters}
            except (KeyError, ValueError):  # pragma: no cover - 注册表已过滤
                pass
            try:
                payload = run_tool(name, **args)
            except Exception as exc:  # 未预期的异常也转为失败 payload
                logger.exception("工具 %s 执行异常", name)
                payload = {
                    "tool": name,
                    "ok": False,
                    "data": None,
                    "error": f"{exc.__class__.__name__}: {exc}",
                    "summary": "",
                }
            results[name] = payload
            if not payload.get("ok"):
                errors.append(f"工具 {name} 失败:{payload.get('error')}")
        return {"tool_results": results, "errors": errors}

    # ------------------------------------------------------------------
    # 节点 4:生成回答
    # ------------------------------------------------------------------

    def _generate(self, state: AgentState) -> dict[str, Any]:
        """生成最终回答:LLM 引用工具数据,或规则模式串联工具输出。"""
        intent = Intent(**state["intent"])
        tool_results = state.get("tool_results", {})
        errors: list[str] = list(state.get("errors", []))
        answer: str | None = None

        if state.get("mode") == MODE_LLM:
            try:
                response = self.client.chat(build_llm_context(intent, tool_results))
                answer = response.content.strip()
            except LLMError as exc:
                errors.append(f"LLM 回答生成失败,降级规则模式:{exc}")
                logger.warning("LLM 生成失败,降级规则模式", exc_info=True)
        if not answer:
            answer = render_rule_answer(intent, tool_results)
        return {"answer": answer, "errors": errors}

    # ------------------------------------------------------------------
    # 运行入口
    # ------------------------------------------------------------------

    def _wants_llm(self) -> bool:
        """是否尝试 LLM 模式:显式 rule 关闭;auto/llm 且客户端可用。"""
        if self.mode == MODE_RULE:
            return False
        return self.client.available

    def run(self, question: str) -> dict[str, Any]:
        """运行完整状态机,返回最终状态(含 ``answer``)。

        :param question: 用户问题(如大纲第十节示例)。
        """
        final: dict[str, Any] = dict(
            self._graph.invoke({"question": question, "errors": []})
        )
        # 便于调用方直接访问的派生字段
        final.setdefault("answer", "")
        return final


def build_agent(client: LLMClient | None = None, *, mode: str = "auto") -> HRTrainingAgent:
    """构建 Agent(便捷入口)。"""
    return HRTrainingAgent(client=client, mode=mode)


def run_agent(question: str, client: LLMClient | None = None, *, mode: str = "auto") -> str:
    """一次性运行 Agent,返回最终回答文本。"""
    return build_agent(client=client, mode=mode).run(question)["answer"]
