"""爬虫测试:解析、序列化、限速与课程清单加载(全部离线 fixture)。"""

from __future__ import annotations

from pathlib import Path

import pytest

from crawler.fetcher import FetchResult, Fetcher, load_course_urls
from crawler.models import CrawledDoc
from crawler.mslearn import parse_mslearn_module, parse_mslearn_module_safe
from profile.__main__ import DEFAULT_DATA_DIR

FIXTURE = Path(__file__).parent / "fixtures" / "mslearn_module.html"


class TestMslearnParser:
    def test_parse_real_page_fixture(self) -> None:
        doc = parse_mslearn_module(
            FIXTURE.read_text(encoding="utf-8"),
            url="https://learn.microsoft.com/en-us/training/modules/get-started-ai-fundamentals/",
            course_id="CRS_001",
        )
        assert doc.title == "Introduction to AI concepts"
        assert doc.source == "mslearn"
        assert doc.course_id == "CRS_001"
        assert doc.description  # meta description 非空
        headings = [h for h, _ in doc.sections]
        assert "Learning objectives" in headings
        assert "Prerequisites" in headings

    def test_prerequisites_body_extracted(self) -> None:
        doc = parse_mslearn_module(FIXTURE.read_text(encoding="utf-8"), url="u")
        body = dict(doc.sections).get("Prerequisites", "")
        assert "machine learning" in body.lower()

    def test_rejects_page_without_title(self) -> None:
        with pytest.raises(ValueError):
            parse_mslearn_module("<html><body>no heading</body></html>", url="u")

    def test_safe_variant_returns_error_dict(self) -> None:
        result = parse_mslearn_module_safe("<p>empty</p>", url="u")
        assert result["ok"] is False
        assert "error" in result


class TestCrawledDoc:
    def test_markdown_structure(self) -> None:
        doc = CrawledDoc(
            source="mslearn",
            url="https://example.com/x",
            title="Course X",
            course_id="CRS_001",
            description="A course.",
            sections=[("Learning objectives", "Understand AI."), ("Prerequisites", "None.")],
        )
        md = doc.to_markdown()
        assert md.startswith("# Course X")
        assert "## Learning objectives" in md
        assert "## Prerequisites" in md
        assert "CRS_001" in md and "https://example.com/x" in md

    def test_empty_sections_skipped(self) -> None:
        doc = CrawledDoc(source="s", url="u", title="T", sections=[("H", "  ")])
        assert "## H" not in doc.to_markdown()


class TestFetcher:
    def test_fetch_result_ok(self) -> None:
        assert FetchResult(url="u", status=200, body="x").ok
        assert not FetchResult(url="u", status=404, body="x").ok
        assert not FetchResult(url="u", status=200, body="").ok

    def test_load_course_urls_from_real_data(self) -> None:
        courses = load_course_urls(Path(DEFAULT_DATA_DIR), limit=3)
        assert len(courses) == 3
        for c in courses:
            assert c["url"].startswith("https://")
            assert c["course_id"]

    def test_load_course_urls_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_course_urls(tmp_path)
