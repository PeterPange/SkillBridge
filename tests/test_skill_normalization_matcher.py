"""Embedding 匹配器单元测试(词面后端 + 测试桩编码器,不依赖真实模型)。"""

import pytest

from skill_normalization.library import DEFAULT_SKILLS, SkillLibrary
from skill_normalization.matcher import (
    EmbeddingMatcher,
    LexicalEncoder,
    SentenceTransformerEncoder,
    cosine_similarity,
    default_encoder,
)
from skill_normalization.models import Skill


@pytest.fixture()
def library() -> SkillLibrary:
    return SkillLibrary(DEFAULT_SKILLS)


class FakeEncoder:
    """测试桩:按字符串查表返回手工构造的向量,未知文本 → 零向量。"""

    def __init__(self, vectors: dict[str, list[float]], dim: int = 8):
        self.vectors = vectors
        self.dim = dim

    def encode(self, texts):
        zero = [0.0] * self.dim
        return [self.vectors.get(t, list(zero)) for t in texts]


# ---------- cosine_similarity ----------

def test_cosine_similarity_identical_and_orthogonal():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0, 2.0], [2.0, 4.0]) == pytest.approx(1.0)


def test_cosine_similarity_zero_vector_and_mismatch():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
    with pytest.raises(ValueError, match="维度不一致"):
        cosine_similarity([1.0], [1.0, 2.0])


# ---------- LexicalEncoder ----------

def test_lexical_encoder_deterministic_and_unit_norm():
    enc = LexicalEncoder(dim=64)
    v1, v2 = enc.encode(["machine learning", "machine learning"])
    assert v1 == v2
    assert sum(x * x for x in v1) == pytest.approx(1.0, abs=1e-9)


def test_lexical_encoder_empty_text_gives_zero_vector():
    vec = LexicalEncoder().encode([""])[0]
    assert all(x == 0.0 for x in vec)


# ---------- EmbeddingMatcher ----------

def test_match_identical_label_scores_one(library):
    matcher = EmbeddingMatcher(LexicalEncoder())
    cands = matcher.match("机器学习", library, top_k=3, threshold=0.5)
    assert cands[0].skill.skill_id == "SKILL_003"
    assert cands[0].score == pytest.approx(1.0)


def test_match_ranks_by_similarity_with_fake_encoder(library):
    vectors = {
        "generative ai": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "machine learning": [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "generative ai app dev": [0.8, 0.6, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    }
    matcher = EmbeddingMatcher(FakeEncoder(vectors))
    cands = matcher.match("generative ai app dev", library, top_k=3, threshold=0.5)
    assert cands[0].skill.skill_id == "SKILL_004"  # cos = 0.8
    assert cands[0].score == pytest.approx(0.8, abs=1e-6)
    assert cands[1].skill.skill_id == "SKILL_003"  # cos = 0.6


def test_match_threshold_filters_and_top_k(library):
    vectors = {"docker": [1.0, 0.0, 0.0], "ai agent": [0.0, 1.0, 0.0]}
    matcher = EmbeddingMatcher(FakeEncoder(vectors, dim=3))
    # 与所有技能正交 → 无候选
    assert matcher.match("cooking recipes", library, top_k=3, threshold=0.5) == []
    # top_k=1 只保留最高分
    cands = matcher.match("docker", library, top_k=1, threshold=0.5)
    assert len(cands) == 1 and cands[0].skill.skill_id == "SKILL_007"


def test_match_empty_text_returns_empty(library):
    assert EmbeddingMatcher(LexicalEncoder()).match("", library) == []


def test_matcher_downgrades_to_lexical_on_model_failure(library):
    """sentence-transformers 编码失败时自动降级为词面匹配。"""
    broken = SentenceTransformerEncoder("broken-model")

    def boom(texts):
        raise RuntimeError("model load failed")

    broken.encode = boom
    matcher = EmbeddingMatcher(broken)
    cands = matcher.match("机器学习", library, threshold=0.5)
    assert cands[0].skill.skill_id == "SKILL_003"
    assert matcher.backend == "lexical"


def test_matcher_reraises_custom_encoder_failure(library):
    class ExplodingEncoder:
        def encode(self, texts):
            raise RuntimeError("boom")

    matcher = EmbeddingMatcher(ExplodingEncoder())
    with pytest.raises(RuntimeError, match="boom"):
        matcher.match("python", library)


# ---------- default_encoder ----------

def test_default_encoder_env_forces_lexical(monkeypatch):
    monkeypatch.setenv("SKILL_NORMALIZATION_BACKEND", "lexical")
    assert isinstance(default_encoder(), LexicalEncoder)


def test_default_encoder_env_invalid_backend_raises(monkeypatch):
    monkeypatch.setenv("SKILL_NORMALIZATION_BACKEND", "bogus")
    with pytest.raises(ValueError, match="SKILL_NORMALIZATION_BACKEND"):
        default_encoder()


def test_default_encoder_auto_prefers_sentence_transformers(monkeypatch):
    pytest.importorskip("sentence_transformers")
    monkeypatch.delenv("SKILL_NORMALIZATION_BACKEND", raising=False)
    enc = default_encoder()
    assert isinstance(enc, SentenceTransformerEncoder)
    assert enc.model_name  # 有默认模型名
