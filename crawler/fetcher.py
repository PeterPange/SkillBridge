"""礼貌 HTTP 抓取器:限速、超时、重试、robots.txt 检查。

零第三方依赖(标准库 urllib),代理沿用 HTTP_PROXY / HTTPS_PROXY
环境变量。默认每请求间隔 1.5 秒,失败退避重试 2 次。
"""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_DELAY_SECONDS = 1.5
DEFAULT_RETRIES = 2
USER_AGENT = "SkillBridgeKnowledgeCrawler/0.1 (+research; contact: admin@example.com)"


@dataclass
class FetchResult:
    """一次抓取的结果:成功携带正文,失败携带原因。"""

    url: str
    status: int = 0
    body: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300 and bool(self.body)


class Fetcher:
    """限速 + 重试 + robots.txt 感知的页面抓取器。

    :param delay_seconds: 相邻请求最小间隔(礼貌限速);
    :param retries: 单页失败重试次数(指数退避);
    :param timeout_seconds: 单请求超时;
    :param respect_robots: 是否检查目标站 robots.txt(默认开);
    :param direct: 直连模式(绕过 HTTP_PROXY 等环境代理)。
        国内站点(B 站等)走代理反而触发风控,置 True 强制直连。
    """

    def __init__(
        self,
        *,
        delay_seconds: float = DEFAULT_DELAY_SECONDS,
        retries: int = DEFAULT_RETRIES,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        respect_robots: bool = True,
        direct: bool = False,
    ) -> None:
        self.delay_seconds = max(0.0, delay_seconds)
        self.retries = max(0, retries)
        self.timeout_seconds = timeout_seconds
        self.respect_robots = respect_robots
        self.direct = direct
        self._last_request_at = 0.0
        self._robots: dict[str, RobotFileParser | None] = {}
        self._opener = (
            urllib.request.build_opener(urllib.request.ProxyHandler({}))
            if direct
            else None
        )

    def fetch(self, url: str, *, headers: dict[str, str] | None = None) -> FetchResult:
        """抓取单个 URL,自动遵守限速与 robots.txt。

        :param headers: 附加请求头(如浏览器 UA / Referer / Cookie)。
        """
        if self.respect_robots and not self._robots_allows(url):
            return FetchResult(url=url, error="disallowed by robots.txt")

        self._throttle()
        merged_headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
        if headers:
            merged_headers.update(headers)
        last_error = ""
        for attempt in range(self.retries + 1):
            try:
                request = urllib.request.Request(url, headers=merged_headers)
                if self._opener is not None:
                    response = self._opener.open(request, timeout=self.timeout_seconds)
                else:
                    response = urllib.request.urlopen(request, timeout=self.timeout_seconds)
                with response:
                    body = response.read().decode("utf-8", errors="replace")
                    return FetchResult(url=url, status=response.status, body=body)
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}"
                if 400 <= exc.code < 500 and exc.code != 429:
                    break  # 客户端错误(除限流)重试无意义
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = str(exc) or exc.__class__.__name__
            if attempt < self.retries:
                backoff = self.delay_seconds * (2**attempt)
                logger.info("抓取失败(%s),%.1fs 后重试 %s", last_error, backoff, url)
                time.sleep(backoff)
        return FetchResult(url=url, error=last_error)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def _robots_allows(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        parser = self._robots.get(origin)
        if parser is None:
            parser = RobotFileParser()
            robots_url = f"{origin}/robots.txt"
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT}),
                    timeout=self.timeout_seconds,
                ) as response:
                    parser.parse(response.read().decode("utf-8", errors="replace").splitlines())
            except (urllib.error.URLError, TimeoutError, OSError):
                parser = None  # robots 不可达:按允许处理,但保留限速
            self._robots[origin] = parser
        return True if parser is None else parser.can_fetch(USER_AGENT, url)


def load_course_urls(data_dir: Path, *, limit: int | None = None) -> list[dict]:
    """从 courses.json 读取待抓课程(URL + 名称 + 编号)。

    :param data_dir: ``data/processed`` 目录;
    :param limit: 限制抓取条数(演示 / 冒烟用)。
    """
    import json

    path = Path(data_dir) / "courses.json"
    if not path.exists():
        raise FileNotFoundError(f"课程数据不存在:{path},请先运行 python -m data.collect")
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("courses", data) if isinstance(data, dict) else data
    courses = [
        {"course_id": c["course_id"], "name": c["name"], "url": c["url"]}
        for c in items
        if c.get("url")
    ]
    if limit is not None:
        courses = courses[:limit]
    return courses
