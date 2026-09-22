"""LLM 语义校验器单元测试(全部 mock,不访问真实 API)。"""

import pytest

from skill_normalization.llm import LLMVerifier
from skill_normalization.matcher import EmbeddingMatcher, LexicalEncoder
from skill_normalization.models import Candidate, Skill

SKILL_GENAI = Skill("SKILL_004", "Generative AI", aliases=("GenAI",))
SKILL_ML = Skill("SKILL_003", "Machine Learning", aliases=("ML",))

CANDIDATES = [Candidate(skill=SKILL_GENAI, score=0.78), Candidate(skill=SKILL_ML, score=0.71)]


def make_verifier(**kwargs) -> LLMVerifier:
    return LLMVerifier(api_key="test-key", base_url="http://llm.test/v1",
                       model="test-model", **kwargs)


def patch_chat(monkeypatch, content_or_exc, calls=None):
    def fake_chat(self, messages):
        if calls is not None:
            calls.append(messages)
        if isinstance(content_or_exc, Exception):
            raise content_or_exc
        return content_or_exc

    monkeypatch.setattr(LLMVerifier, "_chat", fake_chat)


# ---------- 开关与可用性 ----------

def test_unavailable_without_api_key():
    assert not LLMVerifier(api_key="", model="m").available
    assert not LLMVerifier(api_key="k", model="").available


def test_unavailable_when_disabled():
    assert not make_verifier(enabled=False).available


def test_available_with_key_and_model():
    assert make_verifier().available


def test_settings_provide_defaults():
    from skillbridge.config import Settings

    v = LLMVerifier(settings=Settings(openai_api_key="k", llm_model="gpt-test",
                                       openai_base_url="http://x/v1"))
    assert v.available
    assert v.model == "gpt-test"
    assert v.base_url == "http://x/v1"


def test_verify_skips_when_unavailable():
    v = LLMVerifier(api_key="", model="m")
    assert v.verify("GenAI", CANDIDATES) is None


# ---------- 结果解析 ----------

def test_verify_parses_json(monkeypatch):
    patch_chat(monkeypatch, '{"skill_id": "SKILL_004", "confidence": 0.9, "reason": "同义"}')
    verdict = make_verifier().verify("生成式AI应用", CANDIDATES)
    assert verdict.skill_id == "SKILL_004"
    assert verdict.skill_name == "Generative AI"
    assert verdict.confidence == 0.9
    assert verdict.reason == "同义"


def test_verify_parses_json_in_code_block(monkeypatch):
    patch_chat(monkeypatch, '```json\n{"skill_id": "SKILL_003", "confidence": 0.8, "reason": "r"}\n```')
    assert make_verifier().verify("deep learning", CANDIDATES).skill_id == "SKILL_003"


def test_verify_null_skill_id_means_reject(monkeypatch):
    patch_chat(monkeypatch, '{"skill_id": null, "confidence": 0.7, "reason": "不是同一技能"}')
    verdict = make_verifier().verify("Deep Learning", CANDIDATES)
    assert verdict.skill_id is None
    assert verdict.reason == "不是同一技能"


def test_verify_string_null_rejected(monkeypatch):
    patch_chat(monkeypatch, '{"skill_id": "null", "confidence": 0.7, "reason": "r"}')
    assert make_verifier().verify("Deep Learning", CANDIDATES).skill_id is None


def test_verify_hallucinated_id_treated_as_reject(monkeypatch):
    patch_chat(monkeypatch, '{"skill_id": "SKILL_999", "confidence": 0.9, "reason": "r"}')
    assert make_verifier().verify("X", CANDIDATES).skill_id is None


def test_verify_malformed_content_returns_none(monkeypatch):
    patch_chat(monkeypatch, "抱歉,我无法回答这个问题。")
    assert make_verifier().verify("X", CANDIDATES) is None


def test_verify_chat_error_returns_none(monkeypatch):
    patch_chat(monkeypatch, RuntimeError("network down"))
    assert make_verifier().verify("X", CANDIDATES) is None


def test_verify_confidence_clamped(monkeypatch):
    patch_chat(monkeypatch, '{"skill_id": "SKILL_004", "confidence": 5, "reason": "r"}')
    assert make_verifier().verify("X", CANDIDATES).confidence == 1.0


# ---------- prompt 构造 ----------

def test_build_messages_contains_candidates_and_rules():
    messages = make_verifier()._build_messages("深度学习", CANDIDATES)
    user_text = messages[1]["content"]
    assert "深度学习" in user_text
    assert "SKILL_004" in user_text and "SKILL_003" in user_text
    assert "Generative AI" in user_text
    assert "JSON" in user_text


def test_verify_passes_raw_text_to_llm(monkeypatch):
    calls = []
    patch_chat(monkeypatch, '{"skill_id": "SKILL_004", "confidence": 0.9, "reason": "r"}', calls)
    make_verifier().verify("  ＧｅｎＡＩ  ", CANDIDATES)
    assert "ＧｅｎＡＩ" in calls[0][1]["content"]  # 原始文本进入 prompt


# ---------- 与 matcher 的协作(候选构造) ----------

def test_candidates_from_matcher_usable_by_verifier():
    from skill_normalization.library import SkillLibrary, DEFAULT_SKILLS

    matcher = EmbeddingMatcher(LexicalEncoder())
    cands = matcher.match("机器学习", SkillLibrary(DEFAULT_SKILLS), threshold=0.5)
    assert cands
    assert all(isinstance(c, Candidate) for c in cands)
