"""统一技能库测试(大纲第三节:统一 Skill ID)。"""

import pytest

from data import skilllib


def test_registry_ids_are_unique_and_well_formed():
    ids = skilllib.all_skill_ids()
    assert len(ids) == len(set(ids))
    assert all(pid.startswith("SKILL_") and len(pid) == 9 for pid in ids)


def test_registry_fields_complete():
    for skill in skilllib.SKILL_REGISTRY:
        assert skill["skill_id"]
        assert skill["name"]
        assert skill["category"] in skilllib.CATEGORIES
        assert skill["description"]
        assert isinstance(skill["aliases"], list) and skill["aliases"]


def test_genai_variants_map_to_same_skill_id():
    """大纲第三节示例:GenAI / Generative AI / 生成式AI 归一到同一 skill_id。"""
    variants = ["Generative AI", "genai", "Generative Artificial Intelligence", "生成式AI"]
    mapped = {skilllib.match_skill(v) for v in variants}
    assert mapped == {"SKILL_006"}


def test_match_skill_is_case_and_whitespace_insensitive():
    assert skilllib.match_skill("  MACHINE   learning ") == "SKILL_004"
    assert skilllib.match_skill("Python (Computer Programming)") == "SKILL_001"
    assert skilllib.match_skill("utilise machine learning") == "SKILL_004"


def test_match_skill_unknown_returns_none():
    assert skilllib.match_skill("perform scientific research") is None
    assert skilllib.match_skill("") is None


def test_get_skill_raises_on_unknown():
    with pytest.raises(KeyError):
        skilllib.get_skill("SKILL_999")


def test_build_skill_library_marks_provenance():
    records = skilllib.build_skill_library({"SKILL_001": {"esco", "onet"}})
    by_id = {r["skill_id"]: r for r in records}
    assert by_id["SKILL_001"]["sources"] == ["curated", "esco", "onet"]
    # 无外部来源的技能默认 curated
    assert by_id["SKILL_005"]["sources"] == ["curated"]
