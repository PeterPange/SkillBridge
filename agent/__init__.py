"""HR Training Agent(大纲第十节,阶段 4):LangGraph + Tool Calling。

Agent 不是整个系统,而是**整个系统的智能入口和任务编排层**——
理解需求 → 规划工具调用 → 生成回答,业务逻辑全部由已有模块承担::

    用户:我是Java后端,想转AI Engineer,每周4小时,帮我规划
                        ↓ understand(理解需求)
    李明(EMP_001)→ AI Engineer,每周 4 小时,截止 8 周
                        ↓ plan(规划工具调用)
    get_employee_profile → get_skill_gap → recommend_courses
    → generate_learning_path(→ rag_query)
                        ↓ execute(执行工具,全部委托已有模块)
    画像(第五节)/ 差距(第六节)/ 推荐(第七节)/ 路径(第八节)/ RAG(第九节)
                        ↓ generate(生成回答)
    引用真实数据的培训规划(准备度 29.6%、12 项缺口、Top-5、周课表)

LLM 配置(``OPENAI_API_KEY`` / ``LLM_MODEL``)可用时走 LLM 模式
(结构化意图提取 + function calling 规划 + 引用工具数据作答);
不可用时**自动降级规则模式**:规则解析意图、确定性工具链、
直接串联工具输出渲染回答,功能完整、结果可复现。

入口::

    python -m agent "我是Java后端,想转AI Engineer,每周4小时,帮我规划"
    python -m agent "帮我规划" --rule --quiet     # 强制规则模式
    python -m agent "帮我规划" --json             # 结构化输出

结构::

    agent/
    ├── state.py     LangGraph 共享状态(AgentState)
    ├── llm.py       LLM 客户端(OpenAI 兼容,urllib,支持 tool calling)
    ├── intent.py    需求理解(LLM / 规则两套实现)
    ├── tools.py     工具集(5 个工具,全部调用已有模块)
    ├── answer.py    回答生成(规则模式串联渲染 + LLM 上下文构建)
    ├── graph.py     LangGraph 状态机(understand → plan → execute → generate)
    └── __main__.py  CLI 入口
"""

from agent.answer import build_llm_context, render_rule_answer
from agent.graph import HRTrainingAgent, build_agent, run_agent
from agent.intent import Intent, parse_intent_llm, parse_intent_rules
from agent.llm import LLMClient, LLMError, LLMResponse, ToolCall
from agent.state import MODE_LLM, MODE_RULE, AgentState
from agent.tools import (
    RAG_FALLBACK_DOCUMENT,
    TOOL_IMPLEMENTATIONS,
    TOOL_NAMES,
    TOOL_SCHEMAS,
    generate_learning_path,
    get_employee_profile,
    get_skill_gap,
    load_business_data,
    rag_query,
    recommend_courses,
    reset_caches,
    resolve_employee,
    run_tool,
)

__all__ = [
    # 状态机与运行入口
    "HRTrainingAgent",
    "build_agent",
    "run_agent",
    "AgentState",
    "MODE_LLM",
    "MODE_RULE",
    # LLM 客户端
    "LLMClient",
    "LLMError",
    "LLMResponse",
    "ToolCall",
    # 需求理解
    "Intent",
    "parse_intent_llm",
    "parse_intent_rules",
    # 工具集(全部委托已有业务模块)
    "TOOL_NAMES",
    "TOOL_SCHEMAS",
    "TOOL_IMPLEMENTATIONS",
    "run_tool",
    "get_employee_profile",
    "get_skill_gap",
    "recommend_courses",
    "generate_learning_path",
    "rag_query",
    "load_business_data",
    "resolve_employee",
    "reset_caches",
    "RAG_FALLBACK_DOCUMENT",
    # 回答生成
    "render_rule_answer",
    "build_llm_context",
]
