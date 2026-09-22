"""Microsoft Learn 课程元数据采集(大纲第二节「课程数据」)。

官方 API:Learn Catalog API(无需凭据)
- ``GET https://learn.microsoft.com/api/catalog/?locale=en-us&type=modules``
  返回全部 Training Module(标题/摘要/难度/时长/URL);
- 课程页(如 ``/training/modules/<uid>/``)的 "Learning objectives" 区块
  提供学习目标,在线模式逐模块抓取页面并解析。

课程字段:课程名称 / 课程介绍 / 难度 / 学习时间 / 学习目标 / 涉及技能 /
前置课程 / 课程 URL。其中「涉及技能」与「前置课程」为面向 SkillBridge
场景的策展标注(curated),与大纲第七、八节的推荐与路径规划衔接。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from data import skilllib
from data.httpclient import fetch_html, fetch_json, fixture_dir, load_with_cache

logger = logging.getLogger(__name__)

CATALOG_URL = "https://learn.microsoft.com/api/catalog/?locale=en-us&type=modules"
CATALOG_RAW_FILE = "microsoft_learn_catalog.json"
OBJECTIVES_RAW_FILE = "microsoft_learn_objectives.json"

_DIFFICULTY_RANK = {"beginner": 0, "intermediate": 1, "advanced": 2}

#: 课程策展配置:uid → {skills: 统一技能, prerequisites: 其他课程 uid}
#: 前置关系构成学习 DAG(大纲第八节 Learning Path 的输入)。
CURRICULUM: list[dict[str, Any]] = [
    {
        "uid": "learn.wwl.get-started-ai-fundamentals",
        "skills": ["SKILL_004", "SKILL_006"],
        "prerequisites": [],
    },
    {
        "uid": "learn.wwl.fundamentals-machine-learning",
        "skills": ["SKILL_004"],
        "prerequisites": ["learn.wwl.get-started-ai-fundamentals"],
    },
    {
        "uid": "learn.philanthropies.explore-generative-ai",
        "skills": ["SKILL_006"],
        "prerequisites": ["learn.wwl.get-started-ai-fundamentals"],
    },
    {
        "uid": "learn.introduction-large-language-models",
        "skills": ["SKILL_006", "SKILL_007", "SKILL_010"],
        "prerequisites": ["learn.philanthropies.explore-generative-ai"],
    },
    {
        "uid": "learn.wwl.build-rag-applications-azure-database-postgresql",
        "skills": ["SKILL_008", "SKILL_003", "SKILL_001"],
        "prerequisites": ["learn.introduction-large-language-models"],
    },
    {
        "uid": "learn.wwl.build-extend-ai-agents",
        "skills": ["SKILL_009", "SKILL_013"],
        "prerequisites": ["learn.introduction-large-language-models"],
    },
    {
        "uid": "learn.wwl.implement-generative-ai-agents-azure-postgresql",
        "skills": ["SKILL_009", "SKILL_003"],
        "prerequisites": [
            "learn.wwl.build-rag-applications-azure-database-postgresql",
            "learn.wwl.build-extend-ai-agents",
        ],
    },
    {
        "uid": "learn.measure-mitigate-risks-azure-ai-studio",
        "skills": ["SKILL_018"],
        "prerequisites": ["learn.philanthropies.explore-generative-ai"],
    },
    {
        "uid": "learn.wwl.write-first-python-code",
        "skills": ["SKILL_001"],
        "prerequisites": [],
    },
    {
        "uid": "learn.wwl.explore-analyze-data-with-python",
        "skills": ["SKILL_001", "SKILL_004"],
        "prerequisites": ["learn.wwl.write-first-python-code"],
    },
    {
        "uid": "learn.wwl.intro-to-transact-sql",
        "skills": ["SKILL_003"],
        "prerequisites": [],
    },
    {
        "uid": "learn.intro-to-containers",
        "skills": ["SKILL_011"],
        "prerequisites": [],
    },
    {
        "uid": "learn.wwl.introduction-to-devops",
        "skills": ["SKILL_016"],
        "prerequisites": [],
    },
    {
        "uid": "learn.wwl.introduction-development-operations-principles-for-machine-learn",
        "skills": ["SKILL_016", "SKILL_015"],
        "prerequisites": [
            "learn.wwl.fundamentals-machine-learning",
            "learn.wwl.introduction-to-devops",
        ],
    },
    {
        "uid": "learn.wwl.deploy-your-ai-copilot-azure-kubernetes",
        "skills": ["SKILL_012", "SKILL_011"],
        "prerequisites": [
            "learn.wwl.build-extend-ai-agents",
            "learn.intro-to-containers",
        ],
    },
    {
        "uid": "learn.wwl.monitor-generative-ai-app",
        "skills": ["SKILL_015"],
        "prerequisites": ["learn.introduction-large-language-models"],
    },
    {
        "uid": "learn.wwl.describe-core-architectural-components-of-azure",
        "skills": ["SKILL_014"],
        "prerequisites": [],
    },
]


def _strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", text).strip()


def extract_objectives(html: str) -> list[str]:
    """从 Microsoft Learn 课程页 HTML 提取 "Learning objectives" 列表。

    页面结构:``<h2>Learning objectives</h2>`` 之后紧跟一个 ``<ul>``
    (个别课程为一段 ``<p>``,做兜底),再往后是单元目录与页脚,必须截断。
    """
    match = re.search(r"<h2[^>]*>\s*(?:<[^>]+>\s*)*Learning objectives", html, re.I)
    if not match:
        return []
    segment = html[match.end():]
    next_h2 = re.search(r"<h2", segment)
    if next_h2:
        segment = segment[: next_h2.start()]

    ul = re.search(r"<ul[^>]*>(.*?)</ul>", segment, re.S)
    if ul:
        items = [
            _strip_tags(li) for li in re.findall(r"<li[^>]*>(.*?)</li>", ul.group(1), re.S)
        ]
        items = [item for item in items if len(item) > 5]
        if items:
            return items

    paragraph = re.search(r"<p[^>]*>(.*?)</p>", segment, re.S)
    if paragraph:
        text = _strip_tags(paragraph.group(1))
        if len(text) > 10:
            return [text]
    return []


def _module_url(module: dict) -> str:
    """课程页 URL(去掉 Catalog API 附带的 WT.mc_id 追踪参数)。"""
    url = module.get("url") or ""
    return url.split("?")[0]


def fetch_catalog_live() -> dict[str, Any]:
    """在线拉取 Learn Catalog(全部模块)。"""
    return fetch_json(CATALOG_URL)


def fetch_objectives_live(modules: list[dict]) -> dict[str, list[str]]:
    """在线逐模块抓取课程页并解析学习目标。"""
    objectives: dict[str, list[str]] = {}
    for module in modules:
        uid = module["uid"]
        try:
            html = fetch_html(_module_url(module))
        except Exception as exc:  # noqa: BLE001 - 单页失败不应中断整体采集
            logger.warning("[microsoft-learn] 课程页抓取失败 %s: %s", uid, exc)
            objectives[uid] = []
            continue
        objectives[uid] = extract_objectives(html)
    return objectives


def load_catalog(
    *,
    raw_dir: Path,
    offline: bool = False,
    refresh: bool = False,
) -> tuple[dict[str, Any], str]:
    """获取课程目录(api → cache → fixture)。"""
    return load_with_cache(
        CATALOG_RAW_FILE,
        fetch_catalog_live,
        fixture_dir() / "microsoft_learn_catalog.json",
        raw_dir,
        offline=offline,
        refresh=refresh,
    )


def load_objectives(
    modules: list[dict],
    *,
    raw_dir: Path,
    offline: bool = False,
    refresh: bool = False,
) -> tuple[dict[str, list[str]], str]:
    """获取课程学习目标(在线抓取课程页 → cache → fixture)。"""
    return load_with_cache(
        OBJECTIVES_RAW_FILE,
        lambda: fetch_objectives_live(modules),
        fixture_dir() / "microsoft_learn_objectives.json",
        raw_dir,
        offline=offline,
        refresh=refresh,
    )


def _difficulty(module: dict) -> str:
    """取模块难度(levels 可能为空,兜底 beginner)。"""
    levels = module.get("levels") or []
    worst = "beginner"
    for level in levels:
        if _DIFFICULTY_RANK.get(level, 0) >= _DIFFICULTY_RANK[worst]:
            worst = level
    return worst if worst in _DIFFICULTY_RANK else "beginner"


def _summary_objectives(module: dict) -> list[str]:
    """学习目标缺失时,从课程摘要兜底生成一条。"""
    summary = (module.get("summary") or "").strip()
    return [f"课程概要:{summary}"] if summary else ["(未提供学习目标)"]


def parse_courses(
    catalog: dict[str, Any],
    objectives: dict[str, list[str]],
) -> list[dict]:
    """解析目录 + 学习目标为统一课程记录(按 CURRICULUM 顺序输出)。

    目录中不在 CURRICULUM 内的模块被过滤;CURRICULUM 中配置了
    但目录缺失的模块会显式报错(数据不一致)。
    """
    modules_by_uid = {m.get("uid"): m for m in catalog.get("modules", [])}
    course_id_by_uid: dict[str, str] = {}
    for index, entry in enumerate(CURRICULUM, start=1):
        course_id_by_uid[entry["uid"]] = f"CRS_{index:03d}"

    courses = []
    for entry in CURRICULUM:
        uid = entry["uid"]
        module = modules_by_uid.get(uid)
        if module is None:
            raise ValueError(f"课程目录中找不到模块 {uid}(策展配置与目录不一致)")

        learning_objectives = objectives.get(uid) or []
        if not learning_objectives:
            logger.warning("[microsoft-learn] %s 无学习目标,使用摘要兜底", uid)
            learning_objectives = _summary_objectives(module)

        courses.append(
            {
                "course_id": course_id_by_uid[uid],
                "uid": uid,
                "name": module.get("title", uid),
                "description": (module.get("summary") or "").strip(),
                "difficulty": _difficulty(module),
                "duration_minutes": int(module.get("duration_in_minutes") or 0),
                "learning_objectives": learning_objectives,
                "skills": list(entry["skills"]),
                "prerequisites": [
                    course_id_by_uid[pre] for pre in entry["prerequisites"]
                ],
                "url": _module_url(module),
                "source": "microsoft_learn",
            }
        )
    return courses
