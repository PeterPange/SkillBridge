"""外部数据源解析测试(ESCO / O*NET / Microsoft Learn)。

全部基于内置 fixture 与内联 HTML 样本,不依赖网络。
"""

import json
from pathlib import Path

import pytest

from data import skilllib
from data.httpclient import NetworkError, load_with_cache
from data.sources import esco, microsoft_learn, onet

FIXTURES = Path(__file__).resolve().parent.parent / "data" / "fixtures"


@pytest.fixture()
def esco_raw() -> dict:
    return json.loads((FIXTURES / "esco_occupations.json").read_text(encoding="utf-8"))


@pytest.fixture()
def onet_raw() -> dict:
    return json.loads((FIXTURES / "onet_occupations.json").read_text(encoding="utf-8"))


@pytest.fixture()
def learn_catalog() -> dict:
    return json.loads((FIXTURES / "microsoft_learn_catalog.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- ESCO


def test_esco_fixture_contains_three_occupations(esco_raw):
    assert set(esco_raw) == {"software developer", "data scientist", "database developer"}
    for payload in esco_raw.values():
        assert "search" in payload and "detail" in payload


def test_parse_esco_positions(esco_raw):
    positions = esco.parse_esco_positions(esco_raw)
    assert len(positions) == 3
    by_name = {p["name"]: p for p in positions}
    sw = by_name["software developer"]
    # 描述来自 ESCO API
    assert sw["description"].startswith("Software developers")
    assert sw["external_id"]["esco_uri"].startswith("http://data.europa.eu/esco/occupation/")
    # 技能全部映射进统一技能库
    assert sw["skills"], "software developer 至少应命中一个统一技能"
    for skill in sw["skills"]:
        assert skill["source"] == "esco"
        assert 1 <= skill["importance"] <= 5
        assert 0 <= skill["required_level"] <= 4


def test_esco_essential_overrides_optional_for_same_skill(esco_raw):
    """data scientist 的 SQL:essential(5.0) 应覆盖 optional(3.0)。"""
    positions = {p["name"]: p for p in esco.parse_esco_positions(esco_raw)}
    ds_skills = {s["skill_id"]: s for s in positions["data scientist"]["skills"]}
    sql = ds_skills["SKILL_003"]
    assert sql["importance"] == 5.0
    assert sql["required_level"] == 3


def test_esco_provenance(esco_raw):
    provenance = esco.collect_skill_provenance(esco_raw)
    assert "SKILL_003" in provenance  # query languages → SQL
    assert provenance["SKILL_003"] == {"esco"}


# ---------------------------------------------------------------- O*NET


def test_parse_onet_positions(onet_raw):
    positions = onet.parse_onet_positions(onet_raw)
    assert len(positions) == 3
    by_code = {p["external_id"]["onet_code"]: p for p in positions}
    sw = by_code["15-1252.00"]
    assert sw["name"] == "Software Developers"
    assert "Research, design, and develop" in sw["description"]
    # 岗位职责来自 O*NET 任务陈述
    assert any("Analyze user needs" in r for r in sw["responsibilities"])
    # 技能重要度 + 技术技能均参与映射
    skills = {s["skill_id"]: s for s in sw["skills"]}
    assert skills["SKILL_001"]["importance"] == 3.5  # technology skill 默认重要度
    assert "SKILL_011" in skills  # Docker
    assert "SKILL_012" in skills  # Kubernetes
    for skill in sw["skills"]:
        assert skill["source"] == "onet"


def test_onet_importance_to_level():
    assert onet.importance_to_level(4.5) == 4
    assert onet.importance_to_level(4.25) == 4
    assert onet.importance_to_level(3.9) == 3
    assert onet.importance_to_level(2.6) == 2
    assert onet.importance_to_level(1.0) == 1


def test_onet_monitoring_skill_mapped(onet_raw):
    """O*NET 基础技能 Monitoring(3.9)应映射进统一技能库。"""
    positions = onet.parse_onet_positions(onet_raw)
    devops = next(
        p for p in positions if p["external_id"]["onet_code"] == "15-1244.00"
    )
    skills = {s["skill_id"]: s for s in devops["skills"]}
    assert skills["SKILL_015"]["importance"] == 3.9


# ---------------------------------------------------------------- Microsoft Learn


def test_parse_courses_filters_curriculum(learn_catalog):
    objectives = json.loads(
        (FIXTURES / "microsoft_learn_objectives.json").read_text(encoding="utf-8")
    )
    courses = microsoft_learn.parse_courses(learn_catalog, objectives)
    # fixture 目录含干扰模块,只保留策展课程
    assert len(courses) == len(microsoft_learn.CURRICULUM)
    assert all(c["source"] == "microsoft_learn" for c in courses)
    for course in courses:
        assert course["name"]
        assert course["difficulty"] in ("beginner", "intermediate", "advanced")
        assert course["duration_minutes"] > 0
        assert course["learning_objectives"], f"{course['course_id']} 缺学习目标"
        assert course["url"].startswith("https://learn.microsoft.com/")
        assert "?WT.mc_id" not in course["url"]
        assert course["skills"]


def test_parse_courses_rejects_missing_module(learn_catalog):
    """策展配置引用了目录中不存在的模块时应显式报错。"""
    broken = {"modules": [m for m in learn_catalog["modules"][:1]]}
    with pytest.raises(ValueError, match="找不到模块"):
        microsoft_learn.parse_courses(broken, {})


def test_course_ids_follow_curriculum_order(learn_catalog):
    objectives = {}
    courses = microsoft_learn.parse_courses(learn_catalog, objectives)
    assert [c["course_id"] for c in courses] == [
        f"CRS_{i:03d}" for i in range(1, len(courses) + 1)
    ]
    # 前置课程引用的是 course_id 而非 uid
    rag = next(c for c in courses if "SKILL_008" in c["skills"])
    assert rag["prerequisites"] == ["CRS_004"]


_OBJECTIVES_HTML = """
<html><body>
<h1>Sample module</h1>
<p>Summary text.</p>
<h2 class="title is-6">Learning objectives</h2>
<div class="abstract"><p>In this module, you will:</p>
<ul>
<li>Explain <b>core</b> concepts.</li>
<li>Build a simple app.</li>
</ul></div>
<h2>Prerequisites</h2>
<ul><li>Should not be captured</li></ul>
<ul id="unit-list"><li>Unit 1 <span>min</span></li></ul>
</body></html>
"""

_PARAGRAPH_ONLY_HTML = """
<html><body>
<h2>Learning objectives</h2>
<div><p>In this module, you learn about AI solutions and responsible AI practices.</p></div>
<h2>Prerequisites</h2>
</body></html>
"""


def test_extract_objectives_from_list():
    objectives = microsoft_learn.extract_objectives(_OBJECTIVES_HTML)
    assert objectives == ["Explain core concepts.", "Build a simple app."]


def test_extract_objectives_paragraph_fallback():
    objectives = microsoft_learn.extract_objectives(_PARAGRAPH_ONLY_HTML)
    assert objectives == [
        "In this module, you learn about AI solutions and responsible AI practices."
    ]


def test_extract_objectives_missing_section():
    assert microsoft_learn.extract_objectives("<html><body>nothing</body></html>") == []


def test_difficulty_takes_highest_level():
    module = {"levels": ["beginner", "advanced"]}
    assert microsoft_learn._difficulty(module) == "advanced"
    assert microsoft_learn._difficulty({"levels": []}) == "beginner"


# ---------------------------------------------------------------- 离线回退


def test_load_with_cache_falls_back_to_fixture_on_network_error(tmp_path):
    """网络不可用且无缓存时,回退内置 fixture,不阻塞流程。"""

    def _boom():
        raise NetworkError("模拟断网")

    data, source = load_with_cache(
        "test.json", _boom, FIXTURES / "microsoft_learn_objectives.json", tmp_path
    )
    assert source == "fixture"
    assert "learn.wwl.build-extend-ai-agents" in data


def test_load_with_cache_uses_cache_when_offline(tmp_path):
    """离线模式优先使用已有缓存,而非 fixture。"""
    cached = {"hello": "cache"}
    (tmp_path / "cached.json").write_text(json.dumps(cached), encoding="utf-8")

    data, source = load_with_cache(
        "cached.json",
        lambda: {"hello": "api"},
        FIXTURES / "microsoft_learn_objectives.json",
        tmp_path,
        offline=True,
    )
    assert source == "cache"
    assert data == cached


def test_load_with_cache_records_manifest(tmp_path):
    def _live():
        return {"ok": 1}

    _, source = load_with_cache(
        "m.json", _live, FIXTURES / "microsoft_learn_objectives.json", tmp_path
    )
    assert source == "api"
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["m.json"]["source"] == "api"


def test_load_with_cache_no_live_fetcher(tmp_path):
    """无在线途径(如 O*NET 未配置凭据)时直接走缓存/fixture。"""
    data, source = load_with_cache(
        "x.json", None, FIXTURES / "microsoft_learn_objectives.json", tmp_path
    )
    assert source == "fixture"
    assert data
