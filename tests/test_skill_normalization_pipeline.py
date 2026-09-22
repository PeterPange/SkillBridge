"""Skill Normalization 主流程(端到端)测试。

验收标准:GenAI / Generative AI / 生成式AI 等输入全部归一到同一 skill_id。
全部使用离线词面后端与 mock LLM,不依赖网络与真实模型。
"""

import json
import subprocess
import sys

import pytest

from skill_normalization.library import DEFAULT_SKILLS, SkillLibrary
from skill_normalization.llm import LLMVerifier
from skill_normalization.matcher import EmbeddingMatcher, LexicalEncoder
from skill_normalization.models import MatchMethod
from skill_normalization.normalizer import (
    SkillNormalizer,
    build_skill_id_map,
    save_skill_id_map,
)


class FakeEncoder:
    """测试桩:字符串 → 手工向量,未知文本 → 零向量。"""

    def __init__(self, vectors: dict[str, list[float]], dim: int = 8):
        self.vectors = vectors
        self.dim = dim

    def encode(self, texts):
        zero = [0.0] * self.dim
        return [self.vectors.get(t, list(zero)) for t in texts]


def offline_normalizer(**kwargs) -> SkillNormalizer:
    """词面后端 + 关闭 LLM 的归一化器(确定性,无网络)。"""
    return SkillNormalizer(
        encoder=LexicalEncoder(),
        llm_verifier=LLMVerifier(enabled=False),
        **kwargs,
    )


@pytest.fixture()
def normalizer() -> SkillNormalizer:
    return offline_normalizer()


# =====================================================================
# 验收:GenAI / Generative AI / 生成式AI … → 同一 skill_id
# =====================================================================

GENAI_VARIANTS = [
    "GenAI",
    "Gen AI",
    "genai",
    "GEN AI",
    "Generative AI",
    "generative ai",
    "Generative Artificial Intelligence",
    "ＧｅｎＡＩ",                      # 全角
    "生成式AI",
    "生成式 AI",
    "生成式人工智能",
    "Large Language Model Applications",   # 大纲第三节示例
    "LLM Applications",
    "AIGC",
    "  generative-a.i.  ",            # 标点 + 空白噪声
    "Generative AI 技能",              # 通用词后缀
]


@pytest.mark.parametrize("raw", GENAI_VARIANTS)
def test_generative_ai_variants_map_to_same_skill_id(normalizer, raw):
    mapping = normalizer.normalize(raw)
    assert mapping.skill_id == "SKILL_004", f"{raw!r} → {mapping}"
    assert mapping.skill_name == "Generative AI"
    assert mapping.matched


def test_generative_ai_variants_consistent_skill_id(normalizer):
    ids = {normalizer.normalize(raw).skill_id for raw in GENAI_VARIANTS}
    assert ids == {"SKILL_004"}


# =====================================================================
# 其他技能的中英文归一
# =====================================================================

@pytest.mark.parametrize(
    ("raw", "skill_id"),
    [
        ("Machine Learning", "SKILL_003"),
        ("ML", "SKILL_003"),
        ("machine-learning", "SKILL_003"),
        ("机器学习", "SKILL_003"),
        ("RAG", "SKILL_005"),
        ("Retrieval-Augmented Generation", "SKILL_005"),
        ("检索增强生成", "SKILL_005"),
        ("AI Agent", "SKILL_006"),
        ("智能体", "SKILL_006"),
        ("Agent Development", "SKILL_006"),
        ("Docker", "SKILL_007"),
        ("容器技术", "SKILL_007"),
        ("Python", "SKILL_001"),
        ("python3", "SKILL_001"),
        ("Python 编程", "SKILL_001"),
        ("JAVA", "SKILL_002"),
        ("RESTful API", "SKILL_008"),
        ("接口开发", "SKILL_008"),
        ("Structured Query Language", "SKILL_009"),
        ("ＳＱＬ查询", "SKILL_009"),
        ("Cloud Computing", "SKILL_010"),
        ("云计算", "SKILL_010"),
        ("可观测性", "SKILL_011"),
        ("AI Governance", "SKILL_012"),
        ("人工智能治理", "SKILL_012"),
    ],
)
def test_cross_language_variants(normalizer, raw, skill_id):
    assert normalizer.normalize(raw).skill_id == skill_id


# =====================================================================
# 未匹配
# =====================================================================

@pytest.mark.parametrize(
    "raw",
    ["Kubernetes", "Woodworking", "深度学习理论框架", "javascript", ""],
)
def test_unmatched_inputs(normalizer, raw):
    mapping = normalizer.normalize(raw)
    assert mapping.skill_id is None
    assert mapping.method is MatchMethod.NONE
    assert not mapping.matched


def test_javascript_must_not_map_to_java(normalizer):
    """javascript 与 Java 是不同技能,词面相似度不足以匹配。"""
    mapping = normalizer.normalize("javascript")
    assert mapping.skill_id != "SKILL_002"


# =====================================================================
# Embedding 路径(别名未覆盖,靠向量相似度定案)
# =====================================================================

def test_embedding_method_without_alias():
    vectors = {
        "generative ai": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "generative ai application development": [0.8, 0.6, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    }
    n = SkillNormalizer(encoder=FakeEncoder(vectors), llm_verifier=LLMVerifier(enabled=False))
    mapping = n.normalize("Generative AI Application Development")
    assert mapping.method is MatchMethod.EMBEDDING
    assert mapping.skill_id == "SKILL_004"
    assert mapping.score == pytest.approx(0.8, abs=1e-6)
    assert mapping.candidates  # 候选保留在结果中供审计


def test_embedding_no_candidates_unmatched():
    n = SkillNormalizer(encoder=FakeEncoder({}), llm_verifier=LLMVerifier(enabled=False))
    mapping = n.normalize("Some Unknown Skill")
    assert mapping.method is MatchMethod.NONE
    assert mapping.skill_id is None


# =====================================================================
# LLM 语义校验路径
# =====================================================================

def _llm_normalizer(monkeypatch, content_or_exc, calls=None) -> SkillNormalizer:
    from skill_normalization.llm import LLMVerifier as V

    def fake_chat(self, messages):
        if calls is not None:
            calls.append(messages)
        if isinstance(content_or_exc, Exception):
            raise content_or_exc
        return content_or_exc

    monkeypatch.setattr(V, "_chat", fake_chat)
    vectors = {
        "generative ai": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "machine learning": [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "generative ai application development": [0.8, 0.6, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    }
    return SkillNormalizer(
        encoder=FakeEncoder(vectors),
        llm_verifier=V(api_key="k", model="m"),
    )


def test_llm_confirms_candidate(monkeypatch):
    n = _llm_normalizer(
        monkeypatch,
        '{"skill_id": "SKILL_004", "confidence": 0.95, "reason": "生成式AI应用开发属于同一能力"}',
    )
    mapping = n.normalize("Generative AI Application Development")
    assert mapping.method is MatchMethod.LLM
    assert mapping.skill_id == "SKILL_004"
    assert mapping.llm_reason


def test_llm_rejects_all_candidates(monkeypatch):
    n = _llm_normalizer(
        monkeypatch,
        '{"skill_id": null, "confidence": 0.8, "reason": "输入与候选均非同一技能"}',
    )
    mapping = n.normalize("Generative AI Application Development")
    assert mapping.skill_id is None
    assert mapping.method is MatchMethod.NONE
    assert mapping.llm_reason


def test_llm_failure_falls_back_to_embedding(monkeypatch):
    n = _llm_normalizer(monkeypatch, RuntimeError("api down"))
    mapping = n.normalize("Generative AI Application Development")
    assert mapping.method is MatchMethod.EMBEDDING
    assert mapping.skill_id == "SKILL_004"


def test_llm_not_called_when_score_above_auto_accept(monkeypatch):
    calls = []
    vectors = {
        "generative ai": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "generative ai development": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    }
    from skill_normalization.llm import LLMVerifier as V

    def fail_chat(self, messages):
        calls.append(messages)
        raise AssertionError("高置信候选不应调用 LLM")

    monkeypatch.setattr(V, "_chat", fail_chat)
    n = SkillNormalizer(encoder=FakeEncoder(vectors), llm_verifier=V(api_key="k", model="m"))
    mapping = n.normalize("Generative AI Development")
    assert mapping.method is MatchMethod.EMBEDDING
    assert mapping.score == pytest.approx(1.0)
    assert calls == []


def test_llm_skipped_without_api_key(monkeypatch):
    """无 API key:LLM 校验自动跳过,Embedding 结果直接定案(验收要求)。"""
    from skill_normalization.llm import LLMVerifier as V

    def fail_chat(self, messages):
        raise AssertionError("无 key 时不应调用 LLM")

    monkeypatch.setattr(V, "_chat", fail_chat)
    vectors = {
        "generative ai": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "generative ai application development": [0.8, 0.6, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    }
    n = SkillNormalizer(encoder=FakeEncoder(vectors), llm_verifier=V(api_key="", model=""))
    mapping = n.normalize("Generative AI Application Development")
    assert mapping.method is MatchMethod.EMBEDDING
    assert mapping.skill_id == "SKILL_004"


# =====================================================================
# 统一 skill_id 映射表
# =====================================================================

def test_build_skill_id_map_structure(normalizer):
    raws = ["GenAI", "生成式AI", "ML", "机器学习", "Kubernetes"]
    table = build_skill_id_map(raws, normalizer)
    assert table["library_size"] == 12
    assert table["embedding_backend"] == "lexical"
    assert table["llm_verify_enabled"] is False
    assert len(table["mappings"]) == 5
    assert table["summary"]["total"] == 5
    assert table["summary"]["matched"] == 4
    assert table["summary"]["unmatched_inputs"] == ["Kubernetes"]
    assert table["summary"]["skill_counts"] == {"SKILL_003": 2, "SKILL_004": 2}
    # GenAI 与 生成式AI 归一到同一 skill_id
    by_raw = {m["raw"]: m for m in table["mappings"]}
    assert by_raw["GenAI"]["skill_id"] == by_raw["生成式AI"]["skill_id"] == "SKILL_004"


def test_save_skill_id_map_roundtrip(tmp_path, normalizer):
    table = build_skill_id_map(["GenAI", "生成式AI"], normalizer)
    path = save_skill_id_map(table, tmp_path / "nested" / "skill_id_map.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["summary"]["matched"] == 2
    assert {m["skill_id"] for m in data["mappings"]} == {"SKILL_004"}


def test_default_construction_with_env_backend(monkeypatch):
    """SKILL_NORMALIZATION_BACKEND=lexical 时默认构造即离线可用。"""
    monkeypatch.setenv("SKILL_NORMALIZATION_BACKEND", "lexical")
    n = SkillNormalizer(llm_verify=False)
    assert n.matcher.backend == "lexical"
    assert n.normalize("生成式AI").skill_id == "SKILL_004"


def test_normalize_many(normalizer):
    results = normalizer.normalize_many(["GenAI", "ML"])
    assert [r.skill_id for r in results] == ["SKILL_004", "SKILL_003"]


# =====================================================================
# CLI:python -m skill_normalization
# =====================================================================

def test_cli_produces_mapping_table(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    out = tmp_path / "skill_id_map.json"
    result = subprocess.run(
        [
            sys.executable, "-m", "skill_normalization",
            "GenAI", "Generative AI", "生成式AI", "Kubernetes",
            "--backend", "lexical", "--no-llm", "--output", str(out),
        ],
        capture_output=True, text=True, cwd=str(tmp_path), check=False,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    by_raw = {m["raw"]: m["skill_id"] for m in data["mappings"]}
    assert by_raw["GenAI"] == by_raw["Generative AI"] == by_raw["生成式AI"] == "SKILL_004"
    assert by_raw["Kubernetes"] is None
    assert data["summary"]["matched"] == 3
    assert "SKILL_004" in result.stdout


def test_cli_custom_library(tmp_path):
    lib = tmp_path / "lib.json"
    lib.write_text(
        json.dumps({"skills": [{"skill_id": "SKILL_901", "name": "Kubernetes",
                                "aliases": ["K8s"]}]}),
        encoding="utf-8",
    )
    out = tmp_path / "map.json"
    result = subprocess.run(
        [sys.executable, "-m", "skill_normalization", "K8s",
         "--library", str(lib), "--backend", "lexical", "--no-llm", "--output", str(out)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["mappings"][0]["skill_id"] == "SKILL_901"
