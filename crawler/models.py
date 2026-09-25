"""爬虫数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CrawledDoc:
    """一次抓取产出的结构化文档(序列化为 Markdown 供 RAG 入库)。

    :param source: 来源标识(如 ``mslearn``);
    :param url: 原始页面 URL(引用溯源用);
    :param title: 文档标题(对应课程名);
    :param course_id: 关联的课程 ID(``courses.json`` 中的 CRS_xxx);
    :param description: 页面描述(meta description);
    :param sections: 有序内容段(标题 → 正文),保持标题级结构,
        与 rag 分块器的标题级策略对齐。
    """

    source: str
    url: str
    title: str
    course_id: str = ""
    description: str = ""
    sections: list[tuple[str, str]] = field(default_factory=list)

    def to_markdown(self) -> str:
        """序列化为标题级 Markdown(RAG 分块按 ``#``/``##`` 切分)。"""
        parts = [f"# {self.title}"]
        if self.description:
            parts.append(self.description.strip())
        for heading, body in self.sections:
            if not body.strip():
                continue
            parts.append(f"## {heading}")
            parts.append(body.strip())
        footer = f"来源:{self.url}"
        if self.course_id:
            footer = f"课程编号:{self.course_id}\n{footer}"
        parts.append(footer)
        return "\n\n".join(parts) + "\n"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "url": self.url,
            "title": self.title,
            "course_id": self.course_id,
            "description": self.description,
            "sections": [{"heading": h, "body": b} for h, b in self.sections],
        }
