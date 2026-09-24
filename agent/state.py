"""HR Training Agent 状态定义(大纲第十节)。

LangGraph 状态机的共享状态:每个节点读取所需字段、返回局部更新
(``total=False``,未写的键保持不变)::

    START
      ↓
    understand   理解需求 → intent(员工 / 目标岗位 / 每周时长 / 意图)
      ↓
    plan         规划工具调用 → plan(有序工具名 + 参数)
      ↓(plan 为空 → 直接 generate)
    execute      依次执行工具 → tool_results(工具名 → 结构化结果)
      ↓
    generate     生成回答 → answer(LLM 解释 / 规则模式串联工具输出)
      ↓
     END

``mode`` 记录**实际生效**的执行模式:初始化时按 LLM 可用性决定
(``auto`` → llm / rule),运行中 LLM 调用失败会在节点内降级为
``rule`` 并追加 ``errors``,保证「LLM 不可用时降级为规则模式」。
"""

from __future__ import annotations

from typing import Any, TypedDict

#: LLM 模式(理解 / 规划 / 生成均由 LLM 驱动)
MODE_LLM = "llm"
#: 规则模式(直接串联工具输出,LLM 不可用时的降级方案)
MODE_RULE = "rule"


class AgentState(TypedDict, total=False):
    """LangGraph 状态机的共享状态。"""

    #: 用户原始问题(示例:我是Java后端,想转AI Engineer,每周4小时,帮我规划)
    question: str

    #: 实际执行模式:``llm`` / ``rule``(运行中可降级)
    mode: str

    #: 需求理解结果:员工 / 目标岗位 / 每周时长 / 截止周数 / 意图开关
    intent: dict[str, Any]

    #: 规划出的有序工具调用:[{"tool": 名称, "args": {...}}, ...]
    plan: list[dict[str, Any]]

    #: 工具执行结果:工具名 → 结构化 payload(含 ok / data / error)
    tool_results: dict[str, Any]

    #: 运行期降级 / 工具失败等提示(不中断主流程)
    errors: list[str]

    #: 最终回答(引用工具返回的真实数据)
    answer: str
