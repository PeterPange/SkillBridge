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
_UNIT_LINK = re.compile(
    r'<a class="unit-title[^"]*"[^>]*href="([\w-]+)"[^>]*>([^<]+)</a>'
)
_MAIN = re.compile(r"<main[^>]*>")


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


def parse_unit_links(html: str) -> list[dict[str, str]]:
    """从模块页提取单元链接(相对路径)与标题。

    模块页的单元导航为服务端渲染,链接是相对路径
    (如 ``3-computer-vision``),需拼在模块 URL 后。
    """
    return [
        {"href": href, "title": _strip_tags(title).strip()}
        for href, title in _UNIT_LINK.findall(html)
    ]


def parse_unit_content(html: str) -> dict[str, Any]:
    """解析单元页正文:主区域标题 + 有效段落。

    页面家具(Was this page helpful 等)通过长度与位置过滤;
    解析失败抛 :class:`ValueError`。
    """
    main_match = _MAIN.search(html)
    if not main_match:
        raise ValueError("单元页缺少主内容区")
    main_html = html[main_match.start() :]
    h1 = _H1.search(main_html)
    if not h1 or not _strip_tags(h1.group(1)):
        raise ValueError("单元页缺少标题")
    title = _strip_tags(h1.group(1))
    paragraphs = [
        _strip_tags(p)
        for p in re.findall(r"<p[^>]*>(.*?)</p>", main_html, re.S)
    ]
    paragraphs = [p for p in paragraphs if len(p) >= 40][:12]
    if not paragraphs:
        raise ValueError("单元页没有有效正文段落")
    return {"title": title, "paragraphs": paragraphs}
