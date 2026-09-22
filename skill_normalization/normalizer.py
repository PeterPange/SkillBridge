"""Skill Normalization 主流程(大纲第三节)。

.. code-block:: text

    外部技能名称
        ↓ 文本标准化(normalize_text:大小写/全半角/标点/通用词/CJK 空白)
        ↓ Alias 精确匹配(别名表 + 同义词表 → 直接定案)
        ↓ Embedding 相似度(候选标准技能,阈值过滤)
        ↓ LLM 语义校验(可选;不可用或失败时回退 Embedding 结果)
        ↓ 统一 skill_id

批量入口 ``build_skill_id_map()`` 输出统一 skill_id 映射表,
``save_skill_id_map()`` 落盘 JSON;命令行 ``python -m skill_normalization``。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from skill_normalization.library import SkillLibrary
from skill_normalization.llm import LLMVerifier
from skill_normalization.matcher import EmbeddingMatcher, TextEncoder
from skill_normalization.models import MatchMethod, SkillMapping
from skill_normalization.text import normalize_text

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_THRESHOLD = 0.60  # 候选过滤阈值:低于此分不进入候选
DEFAULT_AUTO_ACCEPT_THRESHOLD = 0.90  # 高置信阈值:超过则无需 LLM 校验


class SkillNormalizer:
    """技能归一化器:外部技能名称 → 统一 skill_id。"""

    def __init__(
        self,
        library: SkillLibrary | None = None,
        encoder: TextEncoder | None = None,
        llm_verifier: LLMVerifier | None = None,
        *,
        llm_verify: bool = True,
        embedding_threshold: float = DEFAULT_EMBEDDING_THRESHOLD,
        auto_accept_threshold: float = DEFAULT_AUTO_ACCEPT_THRESHOLD,
        top_k: int = 3,
    ):
        self.library = library if library is not None else SkillLibrary.load()
        self.matcher = EmbeddingMatcher(encoder)
        self.llm = llm_verifier if llm_verifier is not None else LLMVerifier(enabled=llm_verify)
        self.embedding_threshold = embedding_threshold
        self.auto_accept_threshold = auto_accept_threshold
        self.top_k = top_k

    def normalize(self, raw: str) -> SkillMapping:
        """归一化单个外部技能名称。"""
        normalized = normalize_text(raw)
        mapping = SkillMapping(raw=raw, normalized=normalized)
        if not normalized:
            return mapping  # 空输入 / 纯通用词 → 未匹配

        # ① Alias 精确匹配(最强信号,直接定案)
        skill = self.library.match_alias(normalized)
        if skill is not None:
            return SkillMapping(
                raw=raw,
                normalized=normalized,
                skill_id=skill.skill_id,
                skill_name=skill.name,
                method=MatchMethod.ALIAS,
                score=1.0,
            )

        # ② Embedding 相似度 → 候选标准技能
        candidates = self.matcher.match(
            normalized,
            self.library,
            top_k=self.top_k,
            threshold=self.embedding_threshold,
        )
        mapping.candidates = candidates
        if not candidates:
            return mapping
        top = candidates[0]

        # ③ LLM 语义校验(可选;高置信或 LLM 不可用时跳过)
        if self.llm.available and top.score < self.auto_accept_threshold:
            verdict = self.llm.verify(raw, candidates)
            if verdict is not None:
                if verdict.skill_id is None:
                    # LLM 明确否定全部候选
                    mapping.llm_reason = verdict.reason
                    return mapping
                chosen = next(
                    (c for c in candidates if c.skill.skill_id == verdict.skill_id), top
                )
                return SkillMapping(
                    raw=raw,
                    normalized=normalized,
                    skill_id=chosen.skill.skill_id,
                    skill_name=chosen.skill.name,
                    method=MatchMethod.LLM,
                    score=chosen.score,
                    candidates=candidates,
                    llm_reason=verdict.reason,
                )

        # ④ Embedding 结果定案(高置信,或 LLM 不可用/失败时回退)
        return SkillMapping(
            raw=raw,
            normalized=normalized,
            skill_id=top.skill.skill_id,
            skill_name=top.skill.name,
            method=MatchMethod.EMBEDDING,
            score=top.score,
            candidates=candidates,
        )

    def normalize_many(self, raws: Iterable[str]) -> list[SkillMapping]:
        return [self.normalize(raw) for raw in raws]


def build_skill_id_map(
    raws: Iterable[str],
    normalizer: SkillNormalizer | None = None,
    *,
    include_candidates: bool = True,
) -> dict:
    """批量归一化,输出统一 skill_id 映射表(dict,可直接 JSON 序列化)。"""
    n = normalizer if normalizer is not None else SkillNormalizer()
    mappings = n.normalize_many(raws)
    matched = [m for m in mappings if m.matched]
    skill_counts: dict[str, int] = {}
    for m in matched:
        skill_counts[m.skill_id] = skill_counts.get(m.skill_id, 0) + 1
    total = len(mappings)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "embedding_backend": n.matcher.backend,
        "llm_verify_enabled": n.llm.available,
        "library_size": len(n.library),
        "mappings": [m.to_dict(include_candidates=include_candidates) for m in mappings],
        "summary": {
            "total": total,
            "matched": len(matched),
            "match_rate": round(len(matched) / total, 4) if total else 0.0,
            "unmatched_inputs": [m.raw for m in mappings if not m.matched],
            "skill_counts": dict(sorted(skill_counts.items())),
        },
    }


def save_skill_id_map(table: dict, path: str | Path) -> Path:
    """把映射表落盘为 JSON(UTF-8,含中文)。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(table, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path
