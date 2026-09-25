"""爬虫 CLI:多源抓取 → 落盘 Markdown → 可选直接喂给 RAG 知识库。

用法:
    python -m crawler run [--limit N] [--delay 秒]        抓取 courses.json 课程页
    python -m crawler run-catalog [--limit N]           MS Learn 官方目录(AI 模块)
    python -m crawler run-video [--keywords "a,b"]     B 站视频课程(直连)
    python -m crawler ingest [--dir 路径]              把已抓文档入库 RAG
    python -m crawler list [--dir 路径]                列出已抓文档
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from profile.__main__ import DEFAULT_DATA_DIR

from crawler.fetcher import Fetcher, load_course_urls
from crawler.mslearn import parse_mslearn_module_safe
from crawler.mslearn_catalog import fetch_catalog, parse_catalog
from crawler.bilibili import DEFAULT_KEYWORDS, BilibiliSearcher, parse_search_results, videos_to_docs

logger = logging.getLogger("crawler")

KNOWLEDGE_DIR = Path(DEFAULT_DATA_DIR).parent / "knowledge"


def _slugify(text: str) -> str:
    keep = "".join(c if c.isalnum() or c in "-_" else "-" for c in text.lower())
    return "-".join(p for p in keep.split("-") if p) or "doc"


def run_crawl(*, limit: int | None, delay: float, out_dir: Path) -> int:
    """抓取 courses.json 中全部(或前 N 门)课程页并落盘。"""
    courses = load_course_urls(Path(DEFAULT_DATA_DIR), limit=limit)
    if not courses:
        print("没有可抓取的课程(courses.json 为空或无 URL)")
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    fetcher = Fetcher(delay_seconds=delay)

    ok = fail = skip = 0
    for course in courses:
        result = fetcher.fetch(course["url"])
        if not result.ok:
            print(f"[失败] {course['course_id']} {result.error}")
            fail += 1
            continue
        parsed = parse_mslearn_module_safe(
            result.body, url=course["url"], course_id=course["course_id"]
        )
        if not parsed["ok"]:
            print(f"[解析失败] {course['course_id']} {parsed['error']}")
            fail += 1
            continue
        doc = parsed["doc"]
        target = out_dir / f"{course['course_id']}-{_slugify(doc.title)}.md"
        if target.exists():
            skip += 1
            continue
        target.write_text(doc.to_markdown(), encoding="utf-8")
        ok += 1
        print(f"[完成] {course['course_id']} {doc.title} → {target.name}")
    print(f"抓取结束:成功 {ok},跳过 {skip},失败 {fail}")
    return 0 if fail == 0 else 2


def run_catalog(*, limit: int | None, out_dir: Path) -> int:
    """拉取 MS Learn 官方目录,过滤 AI 模块并落盘。"""
    fetcher = Fetcher(respect_robots=False, timeout_seconds=60)  # 官方公开 API
    try:
        catalog_json = fetch_catalog(fetcher)
    except RuntimeError as exc:
        print(f"[失败] {exc}")
        return 1
    docs = parse_catalog(catalog_json, limit=limit)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = skip = 0
    for doc in docs:
        target = out_dir / f"catalog-{_slugify(doc.title)}.md"
        if target.exists():
            skip += 1
            continue
        target.write_text(doc.to_markdown(), encoding="utf-8")
        saved += 1
    print(f"MS Learn 目录:AI 相关 {len(docs)} 个模块,新存 {saved},跳过 {skip} → {out_dir}")
    return 0


def run_video(*, keywords: list[str], pages: int, out_dir: Path) -> int:
    """B 站搜索 AI 课程视频,元数据落盘(直连,勿走代理)。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    searcher = BilibiliSearcher()
    saved = skip = 0
    for keyword in keywords:
        for page in range(1, pages + 1):
            results = searcher.search(keyword, page=page)
            videos = parse_search_results(results, keyword=keyword)
            for doc in videos_to_docs(videos):
                target = out_dir / f"video-{_slugify(doc.title)}.md"
                if target.exists():
                    skip += 1
                    continue
                target.write_text(doc.to_markdown(), encoding="utf-8")
                saved += 1
            print(f"[{keyword}] 第 {page} 页:{len(videos)} 条有效视频")
    print(f"B 站视频:新存 {saved},跳过 {skip} → {out_dir}")
    return 0


def run_ingest(*, doc_dir: Path) -> int:
    """把爬取产物喂给 RAG 知识库。"""
    from rag.pipeline import RagPipeline

    if not doc_dir.exists() or not any(doc_dir.glob("*.md")):
        print(f"目录没有可入库的 Markdown:{doc_dir}")
        return 1
    pipeline = RagPipeline()
    results = pipeline.ingest_dir(doc_dir, doc_id_prefix="crawled")
    for r in results:
        print(f"[入库] {r.title}({r.chunk_count} 块,维度 {r.dim},{r.backend})")
    return 0


def run_list(*, doc_dir: Path) -> int:
    if not doc_dir.exists():
        print(f"目录不存在:{doc_dir}")
        return 1
    files = sorted(doc_dir.glob("*.md"))
    if not files:
        print("暂无已抓取文档")
        return 0
    for f in files:
        first_line = f.read_text(encoding="utf-8").splitlines()[0].lstrip("# ")
        print(f"{f.name}  {first_line}")
    print(f"共 {len(files)} 篇")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="python -m crawler", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="抓取 courses.json 课程页并保存为 Markdown")
    p_run.add_argument("--limit", type=int, default=None, help="只抓前 N 门(冒烟/演示)")
    p_run.add_argument("--delay", type=float, default=1.5, help="请求间隔秒数(默认 1.5)")
    p_run.add_argument("--out", type=Path, default=KNOWLEDGE_DIR, help="输出目录")

    p_cat = sub.add_parser("run-catalog", help="拉取 MS Learn 官方目录(AI 模块,含教材式单元目录)")
    p_cat.add_argument("--limit", type=int, default=None, help="最多产出 N 个模块文档")
    p_cat.add_argument("--out", type=Path, default=KNOWLEDGE_DIR, help="输出目录")

    p_vid = sub.add_parser("run-video", help="B 站搜索 AI 课程视频(直连,勿走代理)")
    p_vid.add_argument("--keywords", type=str, default=None, help="逗号分隔搜索词(缺省内置 6 组)")
    p_vid.add_argument("--pages", type=int, default=1, help="每个关键词抓几页(默认 1)")
    p_vid.add_argument("--out", type=Path, default=KNOWLEDGE_DIR, help="输出目录")

    p_ing = sub.add_parser("ingest", help="将已抓文档入库 RAG 知识库")
    p_ing.add_argument("--dir", type=Path, default=KNOWLEDGE_DIR, help="文档目录")

    p_list = sub.add_parser("list", help="列出已抓取文档")
    p_list.add_argument("--dir", type=Path, default=KNOWLEDGE_DIR, help="文档目录")

    args = parser.parse_args(argv)
    if args.command == "run":
        return run_crawl(limit=args.limit, delay=args.delay, out_dir=args.out)
    if args.command == "run-catalog":
        return run_catalog(limit=args.limit, out_dir=args.out)
    if args.command == "run-video":
        keywords = (
            [k.strip() for k in args.keywords.split(",") if k.strip()]
            if args.keywords
            else list(DEFAULT_KEYWORDS)
        )
        return run_video(keywords=keywords, pages=args.pages, out_dir=args.out)
    if args.command == "ingest":
        return run_ingest(doc_dir=args.dir)
    return run_list(doc_dir=args.dir)


if __name__ == "__main__":
    sys.exit(main())
