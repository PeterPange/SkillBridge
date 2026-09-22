"""技能归一化模块(大纲第三节,阶段 1B)。

外部技能名称 → 文本标准化 → Alias 匹配 → Embedding 相似度 → LLM 语义校验
→ 统一 skill_id。

主要入口:
- ``SkillNormalizer.normalize(raw)`` → ``SkillMapping``
- ``build_skill_id_map(raws)`` → 统一 skill_id 映射表(dict)
- ``python -m skill_normalization`` → 生成映射表 JSON(data/processed/)

降级策略:无 sentence-transformers / 无网络时自动退化为词面匹配;
无 LLM API key 时自动跳过语义校验,均不影响主流程。
"""

from skill_normalization.library import DEFAULT_SKILLS, SkillLibrary
from skill_normalization.llm import LLMVerifier, LLMVerdict
from skill_normalization.matcher import (
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingMatcher,
    LexicalEncoder,
    SentenceTransformerEncoder,
    TextEncoder,
    cosine_similarity,
    default_encoder,
)
from skill_normalization.models import Candidate, MatchMethod, Skill, SkillMapping
from skill_normalization.normalizer import (
    DEFAULT_AUTO_ACCEPT_THRESHOLD,
    DEFAULT_EMBEDDING_THRESHOLD,
    SkillNormalizer,
    build_skill_id_map,
    save_skill_id_map,
)
from skill_normalization.text import normalize_text

__all__ = [
    "DEFAULT_AUTO_ACCEPT_THRESHOLD",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_EMBEDDING_THRESHOLD",
    "DEFAULT_SKILLS",
    "Candidate",
    "EmbeddingMatcher",
    "LLMVerifier",
    "LLMVerdict",
    "LexicalEncoder",
    "MatchMethod",
    "SentenceTransformerEncoder",
    "Skill",
    "SkillLibrary",
    "SkillMapping",
    "SkillNormalizer",
    "TextEncoder",
    "build_skill_id_map",
    "cosine_similarity",
    "default_encoder",
    "normalize_text",
    "save_skill_id_map",
]
