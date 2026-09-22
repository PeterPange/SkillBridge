"""ESCO 岗位数据采集(大纲第二节「岗位数据」)。

官方 API:https://ec.europa.eu/esco/api(ESCO Portal API,无需凭据)
- ``GET /search?text=...&type=occupation&language=en`` 搜索岗位
- ``GET /resource/occupation?uri=...&language=en`` 岗位详情
  (含 ``description``、``_links.hasEssentialSkill`` / ``hasOptionalSkill``)

在线模式逐岗位「搜索 → 详情」两步拉取,原始响应整体缓存到
``data/raw/esco_occupations.json``;断网时回退缓存 / 内置 fixture
(fixture 为真实 API 响应的裁剪版,仅保留英文与必要字段)。
"""

from __future__ import annotations

import logging
import urllib.parse
from pathlib import Path
from typing import Any

from data import skilllib
from data.httpclient import NetworkError, fetch_json, fixture_dir, load_with_cache

logger = logging.getLogger(__name__)

ESCO_API_BASE = "https://ec.europa.eu/esco/api"
RAW_FILE = "esco_occupations.json"

#: ESCO essential/optional 技能 → 统一重要程度与要求等级
_ESSENTIAL_IMPORTANCE = 5.0
_ESSENTIAL_LEVEL = 3
_OPTIONAL_IMPORTANCE = 3.0
_OPTIONAL_LEVEL = 2


def _search_url(text: str) -> str:
    params = urllib.parse.urlencode(
        {"text": text, "language": "en", "type": "occupation", "limit": "10"}
    )
    return f"{ESCO_API_BASE}/search?{params}"


def _occupation_url(uri: str) -> str:
    params = urllib.parse.urlencode({"uri": uri, "language": "en"})
    return f"{ESCO_API_BASE}/resource/occupation?{params}"


def _pick_result(search_response: dict, expected_title: str) -> dict:
    """从搜索结果中按标题精确匹配目标岗位;匹配不到时退回第一条。"""
    results = search_response.get("_embedded", {}).get("results", [])
    for result in results:
        if result.get("title", "").strip().lower() == expected_title.strip().lower():
            return result
    if results:
        logger.warning(
            "ESCO 搜索未精确命中 %r,使用第一条结果 %r",
            expected_title,
            results[0].get("title"),
        )
        return results[0]
    raise NetworkError(f"ESCO 搜索无结果: {expected_title}")


def fetch_esco_live(queries: list[dict[str, str]]) -> dict[str, Any]:
    """在线拉取多个岗位的搜索 + 详情原始响应。

    :param queries: ``[{"query": "software developer", "title": "software developer"}, ...]``
    """
    raw: dict[str, Any] = {}
    for item in queries:
        search = fetch_json(_search_url(item["query"]))
        hit = _pick_result(search, item["title"])
        detail = fetch_json(_occupation_url(hit["uri"]))
        raw[item["query"]] = {"search": search, "detail": detail}
    return raw


def load_esco(
    queries: list[dict[str, str]],
    *,
    raw_dir: Path,
    offline: bool = False,
    refresh: bool = False,
) -> tuple[dict[str, Any], str]:
    """获取 ESCO 原始数据(api → cache → fixture)。"""
    return load_with_cache(
        RAW_FILE,
        lambda: fetch_esco_live(queries),
        fixture_dir() / "esco_occupations.json",
        raw_dir,
        offline=offline,
        refresh=refresh,
    )


def _description_en(detail: dict) -> str:
    desc = detail.get("description", {}).get("en", {})
    if isinstance(desc, dict):
        return str(desc.get("literal", "")).strip()
    return str(desc).strip()


def _mapped_skills(detail: dict) -> list[dict]:
    """把 ESCO 岗位的 essential/optional 技能映射进统一技能库。

    未命中统一技能库的 ESCO 标签(如 "perform scientific research")被丢弃,
    保证输出全部落在统一技能体系上。
    """
    out: dict[str, dict] = {}
    links = detail.get("_links", {})
    for kind, importance, level in (
        ("hasEssentialSkill", _ESSENTIAL_IMPORTANCE, _ESSENTIAL_LEVEL),
        ("hasOptionalSkill", _OPTIONAL_IMPORTANCE, _OPTIONAL_LEVEL),
    ):
        for entry in links.get(kind, []) or []:
            skill_id = skilllib.match_skill(entry.get("title", ""))
            if skill_id is None:
                continue
            current = out.get(skill_id)
            if current is None or importance > current["importance"]:
                out[skill_id] = {
                    "skill_id": skill_id,
                    "importance": importance,
                    "required_level": level,
                    "source": "esco",
                }
    return sorted(out.values(), key=lambda s: s["skill_id"])


def parse_esco_positions(raw: dict[str, Any]) -> list[dict]:
    """解析 ESCO 原始响应为岗位中间记录(供 :mod:`data.positions` 合并)。"""
    positions = []
    for query, payload in raw.items():
        detail = payload["detail"]
        skills = _mapped_skills(detail)
        positions.append(
            {
                "name": detail.get("title", query),
                "description": _description_en(detail),
                "external_id": {"esco_uri": detail.get("uri", "")},
                "source": "esco",
                "skills": skills,
            }
        )
    return positions


def collect_skill_provenance(raw: dict[str, Any]) -> dict[str, set[str]]:
    """统计 ESCO 数据中命中统一技能库的技能(用于 skills.json 来源标注)。"""
    provenance: dict[str, set[str]] = {}
    for payload in raw.values():
        for skill in _mapped_skills(payload["detail"]):
            provenance.setdefault(skill["skill_id"], set()).add("esco")
    return provenance
