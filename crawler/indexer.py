"""资源索引器:把爬取产物(视频 / 目录模块 / 文档)结构化为资源库。

输入:data/knowledge/*.md(爬虫产物,标题级结构稳定)
输出:data/resources.json —— 资源库的唯一数据源,带技能标签,
供资源中心按员工缺口智能匹配。

结构约定(与各爬虫源的 Markdown 模板一一对应):
- video-*.md:  # 视频课程:标题 / ## 视频信息(UP主/时长/播放量/关键词)/ 来源
- catalog-*.md: # 标题 / 描述 / ## 课程信息(难度/时长/角色)/ ## 单元目录 / 来源
- 其余:      # 标题 / 描述 / 来源(制度文档等)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from profile.__main__ import DEFAULT_DATA_DIR

KNOWLEDGE_DIR = Path(DEFAULT_DATA_DIR).parent / "knowledge"
RESOURCES_JSON = Path(DEFAULT_DATA_DIR) / "resources.json"


@dataclass
class Resource:
    """资源库条目。"""

    type: str  # video / module / document
    title: str
    url: str = ""
    meta: dict[str, str] = field(default_factory=dict)
    skills: list[str] = field(default_factory=list)  # 关联技能名

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "title": self.title, "url": self.url, "meta": self.meta, "skills": self.skills}


def _parse_markdown(path: Path) -> dict[str, Any]:
    """标题级 Markdown → {title, description, sections: {heading: body}}。"""
    text = path.read_text(encoding="utf-8")
    title = ""
    description = ""
    sections: dict[str, str] = {}
    current: str | None = None
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("# ") and not title:
            title = block[2:].strip()
        elif block.startswith("## "):
            current = block[3:].strip()
            sections[current] = ""
        elif current:
            sections[current] = (sections[current] + "\n" + block).strip()
        elif not description:
            description = block
    return {"title": title, "description": description, "sections": sections, "text": text}


def _extract_url(text: str) -> str:
    match = re.search(r"来源[:：]\s*(\S+)", text)
    return match.group(1).strip() if match else ""


def _parse_meta_lines(info: str) -> dict[str, str]:
    """「难度:xxx」风格的行 → 字典(无分隔符的行跳过)。"""
    meta: dict[str, str] = {}
    for line in info.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"[:：]", line, 1)
        if len(parts) == 2 and parts[0].strip():
            meta[parts[0].strip()] = parts[1].strip()
    return meta


def _parse_video(doc: dict[str, Any]) -> Resource | None:
    meta = _parse_meta_lines(doc["sections"].get("视频信息", ""))
    title = doc["title"].replace("视频课程:", "").strip()
    if not title:
        return None
    return Resource(
        type="video",
        title=title,
        url=_extract_url(doc["text"]),
        meta=meta,
    )


def _parse_module(doc: dict[str, Any]) -> Resource | None:
    meta = _parse_meta_lines(doc["sections"].get("课程信息", ""))
    units = doc["sections"].get("单元目录", "")
    unit_count = len([l for l in units.splitlines() if l.strip().startswith("-")])
    if unit_count:
        meta["单元数"] = str(unit_count)
    if not doc["title"]:
        return None
    return Resource(
        type="module",
        title=doc["title"],
        url=_extract_url(doc["text"]),
        meta=meta,
    )


def _parse_document(doc: dict[str, Any]) -> Resource | None:
    if not doc["title"]:
        return None
    return Resource(
        type="document",
        title=doc["title"],
        url=_extract_url(doc["text"]),
        meta={"摘要": doc["description"][:120]} if doc["description"] else {},
    )


def _skill_names() -> list[str]:
    data = json.loads((Path(DEFAULT_DATA_DIR) / "skills.json").read_text("utf-8"))
    items = data.get("skills", data) if isinstance(data, dict) else data
    return [s["name"] for s in items if s.get("name")]


def _tag_skills(resource: Resource, skill_names: list[str], aliases: dict[str, str]) -> None:
    """按技能名 / 常见别名给资源打技能标签(大小写不敏感)。"""
    haystack = f"{resource.title} {' '.join(resource.meta.values())}".lower()
    for skill in skill_names:
        if skill.lower() in haystack:
            resource.skills.append(skill)
    for alias, skill in aliases.items():
        if alias in haystack and skill not in resource.skills:
            resource.skills.append(skill)


#: 常见别名 → 统一技能名(与 skill_normalization 的别名表思路一致,轻量版)
ALIASES = {
    "llm": "Large Language Models",
    "large language model": "Large Language Models",
    "genai": "Generative AI",
    "generative ai": "Generative AI",
    "生成式": "Generative AI",
    "机器学习": "Machine Learning",
    "machine learning": "Machine Learning",
    "深度学习": "Machine Learning",
    "langchain": "AI Agent",
    "agent": "AI Agent",
    "智能体": "AI Agent",
    "rag": "RAG",
    "知识库": "RAG",
    "向量数据库": "RAG",
    "milvus": "RAG",
    "prompt": "Prompt Engineering",
    "提示词": "Prompt Engineering",
    "kubernetes": "Kubernetes",
    "docker": "Docker",
    "python": "Python",
    "sql": "SQL",
    "devops": "CI/CD",
    "监控": "Monitoring",
    "monitor": "Monitoring",
}


def build_index(knowledge_dir: Path = KNOWLEDGE_DIR) -> list[Resource]:
    """扫描爬取产物,产出带技能标签的资源列表。"""
    skills = _skill_names()
    resources: list[Resource] = []
    for path in sorted(knowledge_dir.glob("*.md")):
        doc = _parse_markdown(path)
        resource: Resource | None
        if path.name.startswith("video-"):
            resource = _parse_video(doc)
        elif path.name.startswith("catalog-"):
            resource = _parse_module(doc)
        else:
            # CRS_ 课程页已由课程中心承载;制度文档入资源库
            resource = _parse_document(doc)
        if resource is None:
            continue
        _tag_skills(resource, skills, ALIASES)
        resources.append(resource)
    return resources


def write_index(output: Path = RESOURCES_JSON) -> int:
    """构建并落盘资源索引,返回资源条数。"""
    resources = build_index()
    payload = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "resources": [r.to_dict() for r in resources],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(resources)
