"""标准技能库(Skill Library):统一 skill_id、标准名称与别名/同义词索引。

优先从 ``data/processed/skill_library.json`` 加载(阶段 1A 数据采集的产出),
文件不存在时使用内置默认库(大纲第二节列出的 12 项技能)。

技能库 JSON 格式::

    {
      "skills": [
        {"skill_id": "SKILL_001", "name": "Python",
         "aliases": ["Python 3"], "synonyms": ["Python 编程"]}
      ]
    }

构建时会为每个技能的全部称谓(标准名 + 别名 + 同义词)建立
「规范形 → skill_id」精确索引;同一规范形被两个技能声明时抛出
ValueError(技能库数据完整性约束)。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, Iterator

from skill_normalization.models import Skill
from skill_normalization.text import normalize_text

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LIBRARY_PATH = PROJECT_ROOT / "data" / "processed" / "skill_library.json"

# 内置默认技能库:大纲第二节 Skill Library 列出的 12 项技能。
# aliases = 英文变体/缩写;synonyms = 跨语言(中文)同义词。
DEFAULT_SKILLS: tuple[Skill, ...] = (
    Skill(
        skill_id="SKILL_001", name="Python",
        aliases=("Python 3", "Python Programming"),
        synonyms=("Python 编程", "Python 语言", "Python 开发"),
    ),
    Skill(
        skill_id="SKILL_002", name="Java",
        aliases=("Java SE", "Core Java", "Java Programming"),
        synonyms=("Java 语言", "Java 开发"),
    ),
    Skill(
        skill_id="SKILL_003", name="Machine Learning",
        aliases=("ML",),
        synonyms=("机器学习", "机器学习算法"),
    ),
    Skill(
        skill_id="SKILL_004", name="Generative AI",
        aliases=(
            "GenAI", "Gen AI", "Generative Artificial Intelligence",
            "LLM", "Large Language Model", "Large Language Model Applications",
            "LLM Applications", "AIGC",
        ),
        synonyms=("生成式AI", "生成式人工智能"),
    ),
    Skill(
        skill_id="SKILL_005", name="RAG",
        aliases=("Retrieval Augmented Generation", "Retrieval-Augmented Generation"),
        synonyms=("检索增强生成", "RAG 技术"),
    ),
    Skill(
        skill_id="SKILL_006", name="AI Agent",
        aliases=(
            "AI Agents", "Agent", "LLM Agent", "Intelligent Agent",
            "Agent Development", "Agent Engineering",
        ),
        synonyms=("智能体", "AI 智能体", "智能体开发"),
    ),
    Skill(
        skill_id="SKILL_007", name="Docker",
        aliases=("Docker Containers", "Containerization"),
        synonyms=("容器技术", "Docker 容器", "容器化"),
    ),
    Skill(
        skill_id="SKILL_008", name="API",
        aliases=("REST API", "RESTful API", "Web API", "API Development", "API Design"),
        synonyms=("接口开发", "API 接口", "接口设计"),
    ),
    Skill(
        skill_id="SKILL_009", name="SQL",
        aliases=("Structured Query Language",),
        synonyms=("SQL 查询", "数据库查询"),
    ),
    Skill(
        skill_id="SKILL_010", name="Cloud",
        aliases=("Cloud Computing", "Cloud Services", "Cloud Platforms"),
        synonyms=("云计算", "云平台"),
    ),
    Skill(
        skill_id="SKILL_011", name="Monitoring",
        aliases=("Observability", "System Monitoring"),
        synonyms=("监控", "可观测性", "系统监控"),
    ),
    Skill(
        skill_id="SKILL_012", name="AI Governance",
        aliases=("Responsible AI", "AI Ethics"),
        synonyms=("AI 治理", "人工智能治理", "AI 伦理"),
    ),
)


class SkillLibrary:
    """标准技能库:统一 skill_id + 别名/同义词精确索引。"""

    def __init__(self, skills: Iterable[Skill]):
        self._skills: list[Skill] = list(skills)
        self._by_id: dict[str, Skill] = {}
        self._alias_index: dict[str, Skill] = {}
        claimed: dict[str, str] = {}  # 规范形 → skill_id(用于冲突检测)
        for skill in self._skills:
            if skill.skill_id in self._by_id:
                raise ValueError(f"技能库中存在重复的 skill_id: {skill.skill_id}")
            self._by_id[skill.skill_id] = skill
            for label in skill.labels:
                normalized = normalize_text(label)
                if not normalized:
                    continue
                owner = claimed.get(normalized)
                if owner is not None and owner != skill.skill_id:
                    raise ValueError(
                        f"别名冲突:「{label}」的规范形「{normalized}」"
                        f"同时属于 {owner} 与 {skill.skill_id}"
                    )
                claimed[normalized] = skill.skill_id
                self._alias_index[normalized] = skill

    # --- 容器协议 ---
    def __len__(self) -> int:
        return len(self._skills)

    def __iter__(self) -> Iterator[Skill]:
        return iter(self._skills)

    def __contains__(self, skill_id: object) -> bool:
        return skill_id in self._by_id

    # --- 查询 ---
    @property
    def skills(self) -> tuple[Skill, ...]:
        return tuple(self._skills)

    def get(self, skill_id: str) -> Skill | None:
        return self._by_id.get(skill_id)

    def match_alias(self, text: str) -> Skill | None:
        """按规范形精确匹配别名/同义词(输入为原始文本亦可,幂等)。"""
        return self._alias_index.get(normalize_text(text))

    # --- 加载 ---
    @classmethod
    def load(cls, path: str | Path | None = None) -> "SkillLibrary":
        """加载技能库。

        优先级:显式 path > data/processed/skill_library.json > 内置默认库。
        显式指定的路径不存在时抛出 FileNotFoundError;默认路径不存在时
        静默回退到内置库(阶段 1A 数据尚未产出时不阻塞本模块)。
        """
        if path is not None:
            p = Path(path)
            if not p.exists():
                raise FileNotFoundError(f"技能库文件不存在: {p}")
            return cls(_load_json(p))
        if DEFAULT_LIBRARY_PATH.exists():
            logger.info("从 %s 加载技能库", DEFAULT_LIBRARY_PATH)
            return cls(_load_json(DEFAULT_LIBRARY_PATH))
        logger.info("未找到 %s,使用内置默认技能库(%d 项)", DEFAULT_LIBRARY_PATH, len(DEFAULT_SKILLS))
        return cls(DEFAULT_SKILLS)

    def to_dict(self) -> dict:
        return {"skills": [s.to_dict() for s in self._skills]}


def _load_json(path: Path) -> list[Skill]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("skills"), list):
        raise ValueError(f"技能库 JSON 格式错误(应为 {{\"skills\": [...]}}): {path}")
    return [Skill.from_dict(item) for item in data["skills"]]
