"""爬虫 v2 测试:MS Learn 目录源与 B 站视频源(全部离线 fixture)。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawler.bilibili import (
    _duration_to_minutes,
    parse_search_results,
    videos_to_docs,
)
from crawler.mslearn_catalog import is_ai_module, parse_catalog

FIXTURES = Path(__file__).parent / "fixtures"


def _catalog_fixture() -> str:
    """构造最小目录 fixture(2 个模块 + 3 个单元)。"""
    return json.dumps(
        {
            "modules": [
                {
                    "title": "Introduction to Generative AI",
                    "summary": "Learn what generative AI can do.",
                    "levels": ["beginner"],
                    "duration_in_minutes": 40,
                    "roles": ["ai-engineer"],
                    "units": ["u1", "u2"],
                    "url": "https://learn.microsoft.com/x",
                },
                {
                    "title": "Manage SQL Server Permissions",
                    "summary": "Database security basics.",
                    "levels": ["intermediate"],
                    "duration_in_minutes": 30,
                    "units": ["u3"],
                    "url": "https://learn.microsoft.com/y",
                },
            ],
            "units": [
                {"uid": "u1", "title": "What is generative AI"},
                {"uid": "u2", "title": "Responsible AI"},
                {"uid": "u3", "title": "Logins and users"},
            ],
        }
    )


class TestMslearnCatalog:
    def test_filters_ai_modules(self) -> None:
        docs = parse_catalog(_catalog_fixture())
        titles = [d.title for d in docs]
        assert "Introduction to Generative AI" in titles
        assert "Manage SQL Server Permissions" not in titles

    def test_unit_toc_joined(self) -> None:
        docs = parse_catalog(_catalog_fixture())
        sections = dict(docs[0].sections)
        assert "What is generative AI" in sections["单元目录"]
        assert "Responsible AI" in sections["单元目录"]

    def test_course_info_section(self) -> None:
        docs = parse_catalog(_catalog_fixture())
        sections = dict(docs[0].sections)
        assert "beginner" in sections["课程信息"]
        assert "40 分钟" in sections["课程信息"]

    def test_limit(self) -> None:
        docs = parse_catalog(_catalog_fixture(), limit=1)
        assert len(docs) == 1

    def test_is_ai_module_keyword_match(self) -> None:
        assert is_ai_module({"title": "Build AI agents", "summary": ""})
        assert is_ai_module({"title": "", "summary": "uses large language models"})
        assert not is_ai_module({"title": "Kubernetes basics", "summary": "containers"})


class TestBilibili:
    def test_duration_parsing(self) -> None:
        assert _duration_to_minutes("12:30") == 13
        assert _duration_to_minutes("1:02:59") == 63
        assert _duration_to_minutes("") == 0

    def test_parse_filters_noise(self) -> None:
        results = [
            {
                "bvid": "BV1",
                "title": "<em class=\"keyword\">生成式AI</em>入门课程",
                "author": "UP1",
                "duration": "45:00",
                "play": 50000,
                "description": "系统讲解",
            },
            {  # 时长不足:切片
                "bvid": "BV2",
                "title": "AI 小技巧",
                "author": "UP2",
                "duration": "3:20",
                "play": 90000,
                "description": "x",
            },
            {  # 播放不足:营销号
                "bvid": "BV3",
                "title": "AI 大课",
                "author": "UP3",
                "duration": "60:00",
                "play": 100,
                "description": "y",
            },
        ]
        videos = parse_search_results(results, keyword="生成式AI")
        assert len(videos) == 1
        assert videos[0]["bvid"] == "BV1"
        assert videos[0]["title"] == "生成式AI入门课程"  # em 标签已剥离
        assert videos[0]["minutes"] == 45

    def test_dedup_by_bvid(self) -> None:
        item = {
            "bvid": "BV1",
            "title": "课程",
            "author": "a",
            "duration": "20:00",
            "play": 5000,
            "description": "",
        }
        videos = parse_search_results([item, dict(item)], keyword="k")
        assert len(videos) == 1

    def test_videos_to_docs(self) -> None:
        videos = parse_search_results(
            [
                {
                    "bvid": "BV1",
                    "title": "RAG 实战",
                    "author": "讲师",
                    "duration": "90:00",
                    "play": 20000,
                    "description": "从零构建 RAG",
                }
            ],
            keyword="RAG 实战",
        )
        docs = videos_to_docs(videos)
        assert len(docs) == 1
        md = docs[0].to_markdown()
        assert docs[0].title.startswith("视频课程:")
        assert "UP主:讲师" in md
        assert "https://www.bilibili.com/video/BV1" in md
