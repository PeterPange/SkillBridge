"""skill_normalization 数据模型:标准技能、候选与归一化结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MatchMethod(str, Enum):
    """归一化命中方式。"""

    ALIAS = "alias"          # 文本标准化后命中别名/同义词表(最强信号,直接定案)
    EMBEDDING = "embedding"  # Embedding 相似度定案(高置信,或 LLM 不可用时)
    LLM = "llm"              # LLM 语义校验后确认
    NONE = "none"            # 未匹配到标准技能


@dataclass(frozen=True)
class Skill:
    """标准技能:统一技能库中的一条。

    aliases 为英文变体/缩写(如 GenAI、ML),
    synonyms 为跨语言同义词(如 生成式AI、机器学习)。
    """

    skill_id: str
    name: str
    aliases: tuple[str, ...] = ()
    synonyms: tuple[str, ...] = ()

    @property
    def labels(self) -> tuple[str, ...]:
        """参与匹配的全部称谓:标准名 + 别名 + 同义词。"""
        return (self.name, *self.aliases, *self.synonyms)

    @classmethod
    def from_dict(cls, data: dict) -> "Skill":
        skill_id = str(data.get("skill_id") or "").strip()
        name = str(data.get("name") or "").strip()
        if not skill_id or not name:
            raise ValueError(f"技能条目缺少 skill_id 或 name: {data!r}")
        return cls(
            skill_id=skill_id,
            name=name,
            aliases=tuple(str(a) for a in (data.get("aliases") or ())),
            synonyms=tuple(str(s) for s in (data.get("synonyms") or ())),
        )

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "aliases": list(self.aliases),
            "synonyms": list(self.synonyms),
        }


@dataclass(frozen=True)
class Candidate:
    """Embedding 相似度产生的候选标准技能。"""

    skill: Skill
    score: float


@dataclass
class SkillMapping:
    """单条外部技能名称的归一化结果。"""

    raw: str                      # 原始输入
    normalized: str               # normalize_text 之后的规范形
    skill_id: str | None = None   # 统一技能 ID(未匹配为 None)
    skill_name: str | None = None
    method: MatchMethod = MatchMethod.NONE
    score: float = 0.0
    candidates: list[Candidate] = field(default_factory=list)
    llm_reason: str | None = None

    @property
    def matched(self) -> bool:
        return self.skill_id is not None

    def to_dict(self, *, include_candidates: bool = True) -> dict:
        data = {
            "raw": self.raw,
            "normalized": self.normalized,
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "method": self.method.value,
            "score": round(self.score, 4),
        }
        if include_candidates:
            data["candidates"] = [
                {"skill_id": c.skill.skill_id, "skill_name": c.skill.name, "score": round(c.score, 4)}
                for c in self.candidates
            ]
        if self.llm_reason:
            data["llm_reason"] = self.llm_reason
        return data
