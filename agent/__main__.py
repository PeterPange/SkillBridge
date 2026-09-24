"""命令行入口:HR Training Agent(大纲第十节验收命令)。

用法::

    # 大纲第十节示例问题(LLM 未配置时自动降级规则模式)
    python -m agent "我是Java后端,想转AI Engineer,每周4小时,帮我规划"

    # 强制规则模式(直接串联工具输出,不依赖 LLM)
    python -m agent "我是Java后端,想转AI Engineer,每周4小时,帮我规划" --rule

    # 知识库问答类问题(追加 RAG 工具)
    python -m agent "公司培训制度里新员工入职培训期是多久?"

    # 结构化输出(模式 / 意图 / 工具链 / 工具结果 / 回答)
    python -m agent "帮我规划" --json

前置条件:``make up``(Neo4j + PostgreSQL)与 ``make graph``(图谱导入)
后全链路可用;后端缺失时对应工具显式报告不可用,回答基于其余真实数据。
LLM 需配置 ``OPENAI_API_KEY`` / ``LLM_MODEL``(可选),未配置自动走
规则模式,功能完整可用。
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from agent.graph import HRTrainingAgent
from agent.llm import LLMClient

#: 大纲第十节示例问题(缺省演示用)
DEFAULT_QUESTION = "我是Java后端,想转AI Engineer,每周4小时,帮我规划"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m agent",
        description=(
            "HR Training Agent:LangGraph 状态机编排画像 / 差距 / 推荐 / "
            "路径 / RAG 工具(大纲第十节)"
        ),
    )
    parser.add_argument(
        "question", nargs="?", default=DEFAULT_QUESTION,
        help=f"用户问题(默认示例:{DEFAULT_QUESTION})",
    )
    parser.add_argument(
        "--mode", choices=["auto", "llm", "rule"], default="auto",
        help="执行模式:auto 按 LLM 可用性选择(默认);rule 强制规则模式",
    )
    parser.add_argument(
        "--json", dest="as_json", action="store_true",
        help="输出结构化 JSON(模式 / 意图 / 工具链 / 工具结果 / 回答)",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="只输出最终回答(默认会先打印执行过程)",
    )
    return parser


def _print_trace(result: dict[str, Any]) -> None:
    """打印执行过程(模式 / 意图 / 工具链与结果摘要)。"""
    mode = result.get("mode", "rule")
    label = "LLM 模式" if mode == "llm" else "规则模式"
    if mode != "llm":
        label += "(LLM 不可用或调用失败,已降级:直接串联工具输出)"
    print(f"[Agent] 执行模式:{label}")
    intent = result.get("intent", {})
    print(
        f"[Agent] 需求理解:{intent.get('employee_name')}({intent.get('employee_id')})"
        f" → {intent.get('target_position_name')},"
        f"每周 {intent.get('hours_per_week')} 小时,截止 {intent.get('deadline_weeks')} 周"
    )
    for item in result.get("plan", []):
        name = item["tool"]
        payload = result.get("tool_results", {}).get(name)
        if payload is None:
            print(f"[Agent] 工具调用:{name}({item.get('args', {})})")
            continue
        status = payload.get("summary") or payload.get("error") or "完成"
        ok = "✓" if payload.get("ok") else "✗"
        print(f"[Agent] 工具调用:{name} {ok} {status}")
    for error in result.get("errors", []):
        print(f"[Agent] 降级:{error}")
    print()


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    agent = HRTrainingAgent(client=LLMClient(), mode=args.mode)
    try:
        result = agent.run(args.question)
    except LookupError as exc:
        print(f"错误:{exc}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    if not args.quiet:
        _print_trace(result)
    print(result.get("answer", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
