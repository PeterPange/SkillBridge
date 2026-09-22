"""O*NET 岗位数据采集(大纲第二节「岗位数据」)。

官方 API:O*NET Web Services(https://services.onetcenter.org),
``GET /ws/v25/occupations/{code}/details?display=full``,HTTP Basic 认证,
需在 https://www.onetcenter.org/ 注册获取凭据。

- 配置 ``ONET_API_USERNAME`` / ``ONET_API_PASSWORD``(或 .env)后自动走真实 API;
- 未配置或网络不可用时回退本地缓存 / 内置 fixture。
  fixture 基于 O*NET OnLine 公开发布的职业数据(SOCP 编码、技能重要度、
  技术技能示例、任务陈述)整理,响应结构与 Web Services v25 保持一致。

O*NET 提供两类与技能相关的数据:
- ``skills``:基础技能及重要度(1-5,如 Programming 4.5);
- ``technology_skills``:技术技能示例(如 Python、Docker、Kubernetes)。
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from data import skilllib
from data.httpclient import NetworkError, fetch_json, fixture_dir, load_with_cache

logger = logging.getLogger(__name__)

ONET_WS_BASE = "https://services.onetcenter.org/ws/v25"
RAW_FILE = "onet_occupations.json"

#: technology_skills 无重要度评分,统一按 3.5(重要)计
_TECH_IMPORTANCE = 3.5
#: 基础技能重要度 → 要求等级(0-4)的换算阈值
_LEVEL_THRESHOLDS = ((4.25, 4), (3.5, 3), (2.5, 2), (1.5, 1))


def importance_to_level(importance: float) -> int:
    """O*NET 重要度(1-5)→ 统一要求等级(0-4)。"""
    for threshold, level in _LEVEL_THRESHOLDS:
        if importance >= threshold:
            return level
    return 1


def fetch_onet_live(codes: list[str], username: str, password: str) -> dict[str, Any]:
    """在线拉取多个 SOCP 编码的岗位详情(Web Services v25, Basic 认证)。"""
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    raw: dict[str, Any] = {}
    import urllib.request

    for code in codes:
        url = f"{ONET_WS_BASE}/occupations/{code}/details?display=full"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Basic {token}",
                "Accept": "application/json",
                "User-Agent": "SkillBridge-DataCollector/0.1",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                import json

                raw[code] = json.loads(resp.read())
        except OSError as exc:
            raise NetworkError(f"O*NET 请求失败: {url}: {exc}") from exc
    return raw


def load_onet(
    codes: list[str],
    *,
    raw_dir: Path,
    credentials: tuple[str, str] | None = None,
    offline: bool = False,
    refresh: bool = False,
) -> tuple[dict[str, Any], str]:
    """获取 O*NET 原始数据(api → cache → fixture)。

    :param credentials: ``(username, password)``;``None`` 表示无凭据,直接用缓存/fixture。
    """

    def _live() -> dict[str, Any]:
        if credentials is None:
            # 无凭据:主动放弃在线途径,避免 401 噪音
            raise NetworkError("未配置 O*NET API 凭据(ONET_API_USERNAME/ONET_API_PASSWORD)")
        return fetch_onet_live(codes, credentials[0], credentials[1])

    return load_with_cache(
        RAW_FILE,
        _live,
        fixture_dir() / "onet_occupations.json",
        raw_dir,
        offline=offline,
        refresh=refresh,
    )


def _mapped_skills(detail: dict) -> list[dict]:
    """把 O*NET 的 skills + technology_skills 映射进统一技能库。"""
    out: dict[str, dict] = {}

    def _put(skill_id: str, importance: float) -> None:
        current = out.get(skill_id)
        if current is None or importance > current["importance"]:
            out[skill_id] = {
                "skill_id": skill_id,
                "importance": importance,
                "required_level": importance_to_level(importance),
                "source": "onet",
            }

    for entry in detail.get("skills", []) or []:
        skill_id = skilllib.match_skill(entry.get("element_name", ""))
        if skill_id:
            _put(skill_id, float(entry.get("data_value", 0)))

    for category in detail.get("technology_skills", []) or []:
        for example in category.get("example", []) or []:
            skill_id = skilllib.match_skill(example.get("element_name", ""))
            if skill_id:
                _put(skill_id, _TECH_IMPORTANCE)

    return sorted(out.values(), key=lambda s: s["skill_id"])


def parse_onet_positions(raw: dict[str, Any]) -> list[dict]:
    """解析 O*NET 原始响应为岗位中间记录(供 :mod:`data.positions` 合并)。"""
    positions = []
    for code, detail in raw.items():
        occupation = detail.get("occupation", {})
        tasks = [
            str(task.get("task", "")).strip()
            for task in detail.get("tasks", []) or []
            if task.get("task")
        ]
        positions.append(
            {
                "name": occupation.get("title", code),
                "description": str(occupation.get("description", "")).strip(),
                "external_id": {"onet_code": code},
                "source": "onet",
                "responsibilities": tasks,  # O*NET 任务陈述即「岗位职责」
                "skills": _mapped_skills(detail),
            }
        )
    return positions


def collect_skill_provenance(raw: dict[str, Any]) -> dict[str, set[str]]:
    """统计 O*NET 数据中命中统一技能库的技能(用于 skills.json 来源标注)。"""
    provenance: dict[str, set[str]] = {}
    for detail in raw.values():
        for skill in _mapped_skills(detail):
            provenance.setdefault(skill["skill_id"], set()).add("onet")
    return provenance
