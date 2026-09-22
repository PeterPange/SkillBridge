"""命令行入口:批量归一化技能名称,输出统一 skill_id 映射表。

用法::

    python -m skill_normalization                          # 内置演示输入
    python -m skill_normalization \"GenAI\" \"生成式AI\"       # 指定输入
    cat skills.txt | python -m skill_normalization         # stdin,每行一个
    python -m skill_normalization --backend lexical --no-llm   # 离线模式

选项:
    --library PATH   自定义技能库 JSON(默认 data/processed/skill_library.json,
                     不存在时用内置默认库)
    --output PATH    映射表 JSON 输出路径(默认 data/processed/skill_id_map.json)
    --no-llm         关闭 LLM 语义校验
    --backend NAME   Embedding 后端:auto(默认,sentence-transformers 本地模型)/
                     lexical(离线词面匹配)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skill_normalization.library import SkillLibrary
from skill_normalization.llm import LLMVerifier
from skill_normalization.matcher import LexicalEncoder
from skill_normalization.normalizer import SkillNormalizer, build_skill_id_map, save_skill_id_map

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "skill_id_map.json"

# 演示输入:覆盖大纲第三节示例 + 各技能的中英文写法 + 未匹配样例
DEMO_INPUTS = [
    "Generative AI", "GenAI", "Gen AI", "Generative Artificial Intelligence",
    "生成式AI", "生成式 AI", "生成式人工智能", "Large Language Model Applications",
    "AIGC", "Machine Learning", "ML", "机器学习", "RAG",
    "Retrieval Augmented Generation", "检索增强生成", "AI Agent", "智能体",
    "Docker", "容器技术", "Python", "JAVA", "SQL", "Cloud Computing", "云计算",
    "Monitoring", "可观测性", "AI Governance", "Kubernetes",
]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="skill_normalization",
        description="技能名称归一化:文本标准化 + Alias + Embedding + LLM 校验 → 统一 skill_id",
    )
    parser.add_argument("inputs", nargs="*", help="待归一化的技能名称(省略时读 stdin 或使用演示输入)")
    parser.add_argument("--library", help="自定义技能库 JSON 路径")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="映射表 JSON 输出路径")
    parser.add_argument("--no-llm", action="store_true", help="关闭 LLM 语义校验")
    parser.add_argument(
        "--backend", choices=["auto", "lexical"], default="auto",
        help="Embedding 后端(默认 auto:sentence-transformers 本地模型)",
    )
    return parser.parse_args(argv)


def _read_inputs(args: argparse.Namespace) -> list[str]:
    if args.inputs:
        return args.inputs
    if not sys.stdin.isatty():
        lines = [line.strip() for line in sys.stdin if line.strip()]
        if lines:
            return lines
    return DEMO_INPUTS


def _print_table(table: dict) -> None:
    print(f"{'输入':<34}{'skill_id':<12}{'标准名称':<20}{'方法':<11}{'得分'}")
    print("-" * 88)
    for m in table["mappings"]:
        skill_id = m["skill_id"] or "-"
        name = m["skill_name"] or "(未匹配)"
        print(f"{m['raw'][:32]:<34}{skill_id:<12}{name[:18]:<20}{m['method']:<11}{m['score']:.3f}")
    summary = table["summary"]
    print("-" * 88)
    print(
        f"共 {summary['total']} 项,匹配 {summary['matched']} 项"
        f"({summary['match_rate']:.0%});"
        f"未匹配: {summary['unmatched_inputs'] or '无'}"
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    encoder = LexicalEncoder() if args.backend == "lexical" else None
    normalizer = SkillNormalizer(
        library=SkillLibrary.load(args.library),
        encoder=encoder,
        llm_verifier=LLMVerifier(enabled=not args.no_llm),
    )
    table = build_skill_id_map(_read_inputs(args), normalizer)
    output = save_skill_id_map(table, Path(args.output))
    _print_table(table)
    print(f"\nEmbedding 后端: {table['embedding_backend']}")
    print(f"LLM 语义校验: {'开启' if table['llm_verify_enabled'] else '关闭/未配置'}")
    print(f"映射表已写入: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
