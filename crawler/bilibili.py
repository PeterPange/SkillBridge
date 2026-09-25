"""B 站视频课程源:搜索 AI 课程视频,元数据入知识库。

反爬要点:搜索接口校验出口 IP 与 Cookie——必须**直连**(勿走代理,
海外出口直接触发风控页),并先访问首页拿 buvid3 Cookie,再带
浏览器 UA 与 Referer 调搜索接口。

产出为「视频课程」文档:标题 / UP 主 / 时长 / 播放量 / 简介 / 链接,
作为知识库中的视频学习资源(大纲第九节:课程材料)。
"""

from __future__ import annotations

import html as html_module
import json
import logging
import re
import time
import urllib.parse
from http.cookiejar import CookieJar
from typing import Any

logger = logging.getLogger(__name__)

HOME_URL = "https://www.bilibili.com/"
SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/type"
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

#: 默认搜索词(覆盖大纲核心技能域)
DEFAULT_KEYWORDS = (
    "生成式AI 教程",
    "大语言模型 课程",
    "RAG 实战",
    "AI Agent 开发",
    "机器学习 入门",
    "深度学习 教程",
)

#: 过滤阈值:真实课程视频(非切片/营销号)
MIN_MINUTES = 10
MIN_PLAYS = 1000

_TAG = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return html_module.unescape(_TAG.sub("", text or "")).strip()


def _duration_to_minutes(duration: str) -> int:
    """`HH:MM:SS` / `MM:SS` → 分钟数。"""
    parts = [int(p) for p in duration.split(":") if p.strip().isdigit()]
    if not parts:
        return 0
    if len(parts) == 3:
        return parts[0] * 60 + parts[1] + (1 if parts[2] else 0)
    if len(parts) == 2:
        return parts[0] + (1 if parts[1] else 0)
    return parts[0]


class BilibiliSearcher:
    """直连 + 首页 Cookie 的 B 站视频搜索客户端(零第三方依赖)。"""

    def __init__(self, *, delay_seconds: float = 3.0, timeout_seconds: int = 20) -> None:
        import urllib.request

        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        # 直连 opener:显式空代理,绕开 HTTP_PROXY 环境变量
        self._jar = CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(self._jar)
        )
        self._last_request_at = 0.0
        self._warmed = False

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def _warm(self) -> None:
        """访问首页换取 buvid3 Cookie(仅一次)。"""
        if self._warmed:
            return
        request = urllib.request.Request(HOME_URL, headers={"User-Agent": BROWSER_UA})
        try:
            self._opener.open(request, timeout=self.timeout_seconds).close()
        except OSError as exc:
            logger.warning("B 站首页预热失败(继续尝试搜索):%s", exc)
        self._warmed = True

    def search(self, keyword: str, *, page: int = 1) -> list[dict[str, Any]]:
        """搜索一页视频,返回原始结果条目(失败返回空列表)。"""
        self._warm()
        self._throttle()
        params = urllib.parse.urlencode(
            {"search_type": "video", "keyword": keyword, "page": page}
        )
        request = urllib.request.Request(
            f"{SEARCH_URL}?{params}",
            headers={"User-Agent": BROWSER_UA, "Referer": HOME_URL},
        )
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("B 站搜索失败(%s):%s", keyword, exc)
            return []
        if payload.get("code") != 0:
            logger.warning("B 站搜索被拒(%s):code=%s", keyword, payload.get("code"))
            return []
        return payload.get("data", {}).get("result", [])


def parse_search_results(
    results: list[dict[str, Any]], *, keyword: str
) -> list[dict[str, Any]]:
    """原始条目 → 过滤后的视频元数据列表。

    过滤:时长 ≥ 10 分钟且播放 ≥ 1000(保留真实课程,剔除切片/营销号)。
    """
    videos: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in results:
        bvid = item.get("bvid", "")
        title = _clean(item.get("title", ""))
        if not bvid or not title or bvid in seen:
            continue
        minutes = _duration_to_minutes(item.get("duration", ""))
        plays = int(item.get("play", 0) or 0)
        if minutes < MIN_MINUTES or plays < MIN_PLAYS:
            continue
        seen.add(bvid)
        videos.append(
            {
                "bvid": bvid,
                "title": title,
                "author": _clean(item.get("author", "")),
                "duration": item.get("duration", ""),
                "minutes": minutes,
                "plays": plays,
                "description": _clean(item.get("description", ""))[:300],
                "url": f"https://www.bilibili.com/video/{bvid}",
                "keyword": keyword,
            }
        )
    return videos


def videos_to_docs(videos: list[dict[str, Any]]) -> list:
    """视频元数据 → CrawledDoc(视频课程文档)。"""
    from crawler.models import CrawledDoc

    docs = []
    for v in videos:
        sections = [
            (
                "视频信息",
                "\n".join(
                    [
                        f"UP主:{v['author']}",
                        f"时长:{v['duration']}({v['minutes']} 分钟)",
                        f"播放量:{v['plays']}",
                        f"匹配关键词:{v['keyword']}",
                    ]
                ),
            )
        ]
        if v["description"]:
            sections.append(("简介", v["description"]))
        docs.append(
            CrawledDoc(
                source="bilibili",
                url=v["url"],
                title=f"视频课程:{v['title']}",
                description=f"B 站 AI 学习视频,UP 主 {v['author']},时长 {v['duration']}。",
                sections=sections,
            )
        )
    return docs
