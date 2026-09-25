"""Microsoft Learn 课程页解析:静态 HTML → 结构化文档。

learn.microsoft.com 的训练模块页为服务端渲染,静态 HTML 即含:
``<h1>`` 标题、``meta description``、``Learning objectives`` 与
``Prerequisites`` 两个 ``<h2>`` 区块。解析不依赖第三方库。
"""

from __future__ import annotations

import html as html_module
import re
from typing import Any

from crawler.models import CrawledDoc

_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
_META_DESCRIPTION = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"', re.S)
_H2 = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
_TAG = re.compile(r"<[^>]+>")


def _strip_tags(fragment: str) -> str:
    """去标签、反转义、压缩空白。"""
    text = _TAG.sub(" ", fragment)
    text = html_module.unescape(text)
    return " ".join(text.split())


def _block_after(heading_match: re.Match[str], html: str) -> str:
    """取某 ``<h2>`` 之后到下一标题前的正文(段落拼接)。"""
    start = heading_match.end()
    next_h2 = _H2.search(html, start)
    end = next_h2.start() if next_h2 else len(html)
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html[start:end], re.S)
    if not paragraphs:
        return ""
    return "\n\n".join(_strip_tags(p) for p in paragraphs if _strip_tags(p))


def parse_mslearn_module(html: str, *, url: str, course_id: str = "") -> CrawledDoc:
    """解析 Microsoft Learn 模块页为 :class:`CrawledDoc`。

    解析失败(页面改版 / 反爬页)抛 :class:`ValueError`。
    """
    h1 = _H1.search(html)
    if not h1 or not _strip_tags(h1.group(1)):
        raise ValueError(f"页面缺少标题,可能已改版或被拦截:{url}")
    title = _strip_tags(h1.group(1))

    description = ""
    meta = _META_DESCRIPTION.search(html)
    if meta:
        description = html_module.unescape(meta.group(1)).strip()

    sections: list[tuple[str, str]] = []
    for heading_match in _H2.finditer(html):
        heading = _strip_tags(heading_match.group(1))
        if not heading:
            continue
        body = _block_after(heading_match, html)
        if body:
            sections.append((heading, body))

    return CrawledDoc(
        source="mslearn",
        url=url,
        title=title,
        course_id=course_id,
        description=description,
        sections=sections,
    )


def parse_mslearn_module_safe(
    html: str, *, url: str, course_id: str = ""
) -> dict[str, Any]:
    """解析失败时返回错误字典而非抛异常(批量抓取用)。"""
    try:
        doc = parse_mslearn_module(html, url=url, course_id=course_id)
        return {"ok": True, "doc": doc}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
