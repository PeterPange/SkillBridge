"""命令行入口:企业知识库 RAG(大纲第九节验收命令)。

用法::

    python -m rag ingest data/fixtures/training_policy.md    # 入库(可多路径/目录)
    python -m rag ask "新员工入职培训期是多久?"               # 检索问答
    python -m rag ask "培训费怎么报销?" --top-k 3 --json     # 结构化结果
    python -m rag list                                        # 已入库文档

前置条件:``make up``(PostgreSQL + pgvector)。
Embedding 后端复用 skill_normalization:默认 sentence-transformers
本地模型,未安装/无网络自动降级词面匹配;
``--backend lexical`` 可强制离线词面后端(CI / 无网络环境)。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg
from psycopg import errors as pg_errors

from rag import RagPipeline
from rag.models import IngestResult, SearchResult
from rag.reader import SUPPORTED_SUFFIXES
from skillbridge.db import postgres_connect
from skill_normalization.matcher import ENV_BACKEND


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rag",
        description="企业知识库 RAG:文档解析 + 标题级分块 + pgvector 检索(大纲第九节)",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "lexical"],
        help="Embedding 后端(默认 auto:sentence-transformers,降级词面;"
        "lexical 强制离线词面匹配)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="解析并入库文档(PDF/Word/Markdown)")
    ingest.add_argument(
        "paths", nargs="+", type=Path,
        help=f"文档或目录(支持 {' / '.join(SUPPORTED_SUFFIXES)})",
    )
    ingest.add_argument(
        "--reset", action="store_true",
        help="入库前删除 RAG 表(换 Embedding 后端后重建;会清空已入库文档)",
    )

    ask = subparsers.add_parser("ask", help="自然语言提问,返回带来源引用的相关段落")
    ask.add_argument("question", help="问题(如:新员工入职培训期是多久?)")
    ask.add_argument("--top-k", type=int, default=4, help="返回引用块数(默认 4)")
    ask.add_argument("--json", dest="as_json", action="store_true", help="输出结构化 JSON")

    subparsers.add_parser("list", help="列出已入库文档")
    return parser


def _postgres_ready() -> bool:
    """PostgreSQL 可达性探测(失败时给出启动提示而不是堆栈)。"""
    try:
        conn = postgres_connect()
    except psycopg.OperationalError:
        return False
    conn.close()
    return True


def _make_pipeline(args: argparse.Namespace) -> RagPipeline:
    if args.backend:
        os.environ[ENV_BACKEND] = args.backend
    return RagPipeline()


def _cmd_ingest(pipeline: RagPipeline, paths: list[Path], *, reset: bool = False) -> int:
    if reset:
        pipeline.store.reset()
        print("已删除 RAG 表,将按当前 Embedding 后端重建。")
    results: list[IngestResult] = []
    for path in paths:
        if path.is_dir():
            results.extend(pipeline.ingest_dir(path))
        else:
            results.append(pipeline.ingest_file(path))
    for result in results:
        print(
            f"已入库《{result.title}》: {result.chunk_count} 块 "
            f"(维度 {result.dim},后端 {result.backend})"
        )
    print(f"共入库 {len(results)} 篇文档。")
    return 0


def _cmd_ask(pipeline: RagPipeline, question: str, *, top_k: int, as_json: bool) -> int:
    result: SearchResult = pipeline.query(question, top_k=top_k)
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"问题: {result.query}")
        print()
        print(result.context)
    return 0


def _cmd_list(pipeline: RagPipeline) -> int:
    try:
        documents = pipeline.store.list_documents()
    except pg_errors.UndefinedTable:
        documents = []  # 尚未入库过:表不存在视为空库
    if not documents:
        print("知识库为空,请先运行: python -m rag ingest <文档路径>")
        return 0
    for doc in documents:
        print(f"{doc.doc_id}  《{doc.title}》  {doc.chunk_count} 块  来源: {doc.source}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not _postgres_ready():
        print("无法连接 PostgreSQL,请先启动数据库:make up", file=sys.stderr)
        return 1
    pipeline = _make_pipeline(args)
    try:
        if args.command == "ingest":
            return _cmd_ingest(pipeline, args.paths, reset=args.reset)
        if args.command == "ask":
            return _cmd_ask(
                pipeline, args.question, top_k=args.top_k, as_json=args.as_json
            )
        return _cmd_list(pipeline)
    except (FileNotFoundError, ValueError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
