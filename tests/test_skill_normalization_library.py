"""标准技能库(SkillLibrary)单元测试。"""

import json

import pytest

from skill_normalization.library import DEFAULT_SKILLS, DEFAULT_LIBRARY_PATH, SkillLibrary
from skill_normalization.models import Skill
from skill_normalization.text import normalize_text


@pytest.fixture()
def library() -> SkillLibrary:
    return SkillLibrary(DEFAULT_SKILLS)


def test_default_library_matches_outline_skill_list(library):
    """内置默认库 = 大纲第二节的 12 项技能。"""
    names = [s.name for s in library]
    assert names == [
        "Python", "Java", "Machine Learning", "Generative AI", "RAG", "AI Agent",
        "Docker", "API", "SQL", "Cloud", "Monitoring", "AI Governance",
    ]
    assert [s.skill_id for s in library] == [f"SKILL_{i:03d}" for i in range(1, 13)]


def test_alias_index_covers_all_labels(library):
    for skill in library:
        for label in skill.labels:
            hit = library.match_alias(label)
            assert hit is not None and hit.skill_id == skill.skill_id, label


@pytest.mark.parametrize(
    ("query", "skill_id"),
    [
        ("genai", "SKILL_004"),
        ("ＧｅｎＡＩ", "SKILL_004"),
        ("生成式 AI", "SKILL_004"),
        ("ml", "SKILL_003"),
        ("机器学习", "SKILL_003"),
        ("kubernetes", None),      # 不在库中
        ("javascript", None),      # 与 Java 是不同技能
    ],
)
def test_match_alias(library, query, skill_id):
    hit = library.match_alias(query)
    assert (hit.skill_id if hit else None) == skill_id


def test_duplicate_skill_id_rejected():
    with pytest.raises(ValueError, match="重复的 skill_id"):
        SkillLibrary([
            Skill("SKILL_001", "Python"),
            Skill("SKILL_001", "Java"),
        ])


def test_alias_collision_rejected():
    with pytest.raises(ValueError, match="别名冲突"):
        SkillLibrary([
            Skill("SKILL_001", "Python", aliases=("ML",)),
            Skill("SKILL_002", "Machine Learning", aliases=("ml",)),
        ])


def test_get_and_contains(library):
    assert library.get("SKILL_004").name == "Generative AI"
    assert library.get("SKILL_999") is None
    assert "SKILL_001" in library
    assert "SKILL_999" not in library
    assert len(library) == 12


def test_load_from_json(tmp_path):
    data = {
        "skills": [
            {"skill_id": "SKILL_101", "name": "Kubernetes",
             "aliases": ["K8s"], "synonyms": ["容器编排"]},
        ]
    }
    path = tmp_path / "skill_library.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    lib = SkillLibrary.load(path)
    assert len(lib) == 1
    assert lib.match_alias("k8s").skill_id == "SKILL_101"
    assert lib.match_alias("容器编排").skill_id == "SKILL_101"


def test_load_explicit_missing_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        SkillLibrary.load(tmp_path / "nope.json")


def test_load_default_path_falls_back_to_builtin(monkeypatch, tmp_path):
    """默认路径不存在时回退内置库(阶段 1A 数据未产出时不阻塞)。"""
    import skill_normalization.library as lib_module

    monkeypatch.setattr(lib_module, "DEFAULT_LIBRARY_PATH", tmp_path / "missing.json")
    lib = SkillLibrary.load()
    assert len(lib) == len(DEFAULT_SKILLS)
    assert lib.match_alias("genai").skill_id == "SKILL_004"


def test_load_default_path_uses_file_when_present(monkeypatch, tmp_path):
    import skill_normalization.library as lib_module

    custom = tmp_path / "skill_library.json"
    custom.write_text(
        json.dumps({"skills": [{"skill_id": "SKILL_X", "name": "Custom Skill"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(lib_module, "DEFAULT_LIBRARY_PATH", custom)
    assert SkillLibrary.load().match_alias("custom skill").skill_id == "SKILL_X"


def test_invalid_json_schema_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"items": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="格式错误"):
        SkillLibrary.load(bad)


def test_skill_from_dict_requires_id_and_name():
    with pytest.raises(ValueError, match="skill_id 或 name"):
        Skill.from_dict({"name": "NoId"})
    skill = Skill.from_dict({"skill_id": "SKILL_1", "name": "X", "aliases": ["y"]})
    assert skill.aliases == ("y",) and skill.synonyms == ()
