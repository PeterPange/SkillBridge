"""HTTP 客户端与离线缓存策略(阶段 1A)。

设计目标:网络可用时拉取真实 API 并缓存到 ``data/raw/``;
网络不可用时依次回退到「本地缓存 → 内置 fixture」,保证采集流程永不因断网而中断。

- ``fetch_json`` / ``fetch_html``:基于标准库 urllib 的轻量 GET,
  统一超时与 User-Agent,失败抛 :class:`NetworkError`。
- ``load_with_cache``:三级数据源(api → cache → fixture)的统一调度。
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 20.0
USER_AGENT = "SkillBridge-DataCollector/0.1 (+https://github.com/skillbridge)"
#: 缓存视为「新鲜」的时长;超过后优先重新拉取 API
DEFAULT_CACHE_TTL_DAYS = 7.0

MANIFEST_NAME = "manifest.json"


class NetworkError(RuntimeError):
    """网络请求失败(超时 / DNS / HTTP 错误 / 响应解析失败)。"""


def _request(url: str, *, timeout: float, accept: str) -> Any:
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            # 避免依赖 gzip 解压;绝大多数 API 支持 identity
            "Accept-Encoding": "identity",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise NetworkError(f"请求失败: {url}: {exc}") from exc


def fetch_json(url: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Any:
    """GET 一个 JSON 接口并解析;失败抛 :class:`NetworkError`。"""
    raw = _request(url, timeout=timeout, accept="application/json")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NetworkError(f"响应不是合法 JSON: {url}: {exc}") from exc


def fetch_html(url: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    """GET 一个 HTML 页面并解码为文本;失败抛 :class:`NetworkError`。"""
    raw = _request(url, timeout=timeout, accept="text/html")
    return raw.decode("utf-8", errors="replace")


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _read_manifest(raw_dir: Path) -> dict[str, Any]:
    manifest_path = raw_dir / MANIFEST_NAME
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("manifest.json 解析失败,将重建")
    return {}


def _write_manifest(raw_dir: Path, manifest: dict[str, Any]) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _cache_is_fresh(manifest: dict[str, Any], name: str, ttl_days: float) -> bool:
    """缓存是否为 API 拉取且仍在 TTL 内。"""
    entry = manifest.get(name, {})
    if entry.get("source") != "api":
        return False
    fetched_at = entry.get("fetched_at")
    if not fetched_at:
        return False
    try:
        ts = _dt.datetime.fromisoformat(fetched_at)
    except ValueError:
        return False
    age = _dt.datetime.now(_dt.timezone.utc) - ts
    return age <= _dt.timedelta(days=ttl_days)


def load_with_cache(
    name: str,
    fetch_live: Callable[[], Any] | None,
    fixture_path: Path,
    raw_dir: Path,
    *,
    offline: bool = False,
    refresh: bool = False,
    ttl_days: float = DEFAULT_CACHE_TTL_DAYS,
) -> tuple[Any, str]:
    """按「在线 API → 本地缓存 → 内置 fixture」的顺序获取一份数据。

    :param name: 数据文件名(如 ``esco_occupations.json``),同时是缓存键。
    :param fetch_live: 在线拉取函数;``None`` 表示该数据源无在线途径(仅 fixture)。
    :param fixture_path: 内置离线 fixture 的路径。
    :param raw_dir: 离线缓存目录(``data/raw/``)。
    :param offline: 强制离线模式,不发起任何网络请求。
    :param refresh: 忽略缓存新鲜度,强制重新拉取 API。
    :return: ``(data, source)``,source ∈ ``{"api", "cache", "fixture"}``。
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    cache_path = raw_dir / name
    manifest = _read_manifest(raw_dir)

    # 1) 在线拉取(除非强制离线)
    if fetch_live is not None and not offline:
        if refresh or not _cache_is_fresh(manifest, name, ttl_days):
            try:
                data = fetch_live()
            except NetworkError as exc:
                logger.warning("[%s] 在线拉取失败,回退本地数据: %s", name, exc)
            else:
                cache_path.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                manifest[name] = {"source": "api", "fetched_at": _utcnow_iso()}
                _write_manifest(raw_dir, manifest)
                return data, "api"

    # 2) 本地缓存(无论新鲜与否,断网时可用)
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("[%s] 本地缓存损坏,改用 fixture: %s", name, exc)
        else:
            if manifest.get(name, {}).get("source") != "cache":
                manifest[name] = {
                    "source": "cache",
                    "fetched_at": manifest.get(name, {}).get("fetched_at", _utcnow_iso()),
                }
                _write_manifest(raw_dir, manifest)
            return data, "cache"

    # 3) 内置 fixture(同时写入 raw 缓存,保证 data/raw/ 始终有当前原始快照)
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    cache_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest[name] = {"source": "fixture", "fetched_at": _utcnow_iso()}
    _write_manifest(raw_dir, manifest)
    logger.info("[%s] 使用内置 fixture: %s", name, fixture_path)
    return data, "fixture"


def fixture_dir() -> Path:
    """返回内置 fixture 目录(``data/fixtures/``)。"""
    return Path(__file__).resolve().parent / "fixtures"
