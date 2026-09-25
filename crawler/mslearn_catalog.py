"""Microsoft Learn 官方目录源:一次拉取全量课程目录(约 3000+ 模块)。

目录 API(https://learn.microsoft.com/api/catalog/)返回全量
modules / units / learningPaths 等结构化数据,是比逐页爬取更全、
更稳的官方接口。本模块按 AI 关键词过滤模块,把单元标题拼成
「教材目录」,产出适合 RAG 标题级分块的结构化文档。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from crawler.models import CrawledDoc

logger = logging.getLogger(__name__)

CATALOG_URL = "https://learn.microsoft.com/api/catalog/"

#: AI 相关关键词(小写匹配 title / summary)
AI_KEYWORDS = (
    "artificial intelligence",
    " ai ",
    "machine learning",
    "generative ai",
    "large language model",
    " llm",
    "copilot",
    " ai agent",
    "agent",
    "rag",
    "prompt",
    "neural network",
    "deep learning",
    "data scientist",
    "natural language",
    "computer vision",
    "openai",
)


def is_ai_module(module: dict[str, Any]) -> bool:
    """按标题与摘要判断模块是否与 AI 相关。"""
    title = f" {module.get('title', '').lower()} "
    summary = f" {module.get('summary', '').lower()} "
    return any(k in title or k in summary for k in AI_KEYWORDS)


def parse_catalog(
    catalog_json: str, *, limit: int | None = None
) -> list[CrawledDoc]:
    """解析目录 JSON → AI 相关模块的结构化文档列表。

    :param catalog_json: 目录 API 原始响应文本;
    :param limit: 最多产出文档数(冒烟/演示用)。
    """
    data = json.loads(catalog_json)
    modules = data.get("modules", [])
    units = {u["uid"]: u.get("title", "") for u in data.get("units", [])}

    docs: list[CrawledDoc] = []
    for module in modules:
        if not is_ai_module(module):
            continue
        title = module.get("title", "").strip()
        if not title:
            continue
        sections: list[tuple[str, str]] = []

        summary = module.get("summary", "").strip()
        meta_parts = []
        levels = ", ".join(module.get("levels", []))
        if levels:
            meta_parts.append(f"难度:{levels}")
        duration = module.get("duration_in_minutes")
        if duration:
            meta_parts.append(f"时长:{duration} 分钟")
        roles = ", ".join(module.get("roles", []))
        if roles:
            meta_parts.append(f"适用角色:{roles}")
        if meta_parts:
            sections.append(("课程信息", "\n".join(meta_parts)))

        unit_titles = [units.get(uid, "") for uid in module.get("units", [])]
        unit_titles = [t for t in unit_titles if t]
        if unit_titles:
            sections.append(("单元目录", "\n".join(f"- {t}" for t in unit_titles)))

        docs.append(
            CrawledDoc(
                source="mslearn-catalog",
                url=module.get("url", CATALOG_URL),
                title=title,
                description=summary,
                sections=sections,
            )
        )
        if limit is not None and len(docs) >= limit:
            break
    return docs


def fetch_catalog(fetcher) -> str:
    """拉取目录原始 JSON(约 14MB,直连即可,无需代理)。"""
    result = fetcher.fetch(CATALOG_URL)
    if not result.ok:
        raise RuntimeError(f"目录拉取失败:{result.error}")
    return result.body
