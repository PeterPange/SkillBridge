"""资源中心与技能测评测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from profile.__main__ import DEFAULT_DATA_DIR

RESOURCES_JSON = Path(DEFAULT_DATA_DIR) / "resources.json"


def _resources_ready() -> bool:
    return RESOURCES_JSON.exists()


class TestResourceIndexer:
    @pytest.mark.skipif(not _resources_ready(), reason="需要资源索引(先 python -m crawler index)")
    def test_index_structure_and_tags(self) -> None:
        from crawler.indexer import build_index

        resources = build_index()
        assert len(resources) >= 50
        types = {r.type for r in resources}
        assert "video" in types and "module" in types
        tagged = [r for r in resources if r.skills]
        assert len(tagged) >= 30, "大部分资源应带技能标签"
        for r in resources:
            assert r.title
            if r.type == "video":
                assert r.url.startswith("https://www.bilibili.com/video/")

    def test_markdown_parsing(self, tmp_path: Path) -> None:
        from crawler.indexer import _parse_markdown

        doc = _parse_markdown.__wrapped__ if hasattr(_parse_markdown, "__wrapped__") else _parse_markdown
        path = tmp_path / "video-x.md"
        path.write_text(
            "# 视频课程:RAG 实战\n\nB 站课程\n\n## 视频信息\n\nUP主:讲师\n时长:90:00\n\n来源:https://www.bilibili.com/video/BV1\n",
            encoding="utf-8",
        )
        parsed = _parse_markdown(path)
        assert parsed["title"] == "视频课程:RAG 实战"
        assert "UP主:讲师" in parsed["sections"]["视频信息"]


@pytest.mark.skipif(not _resources_ready(), reason="需要资源索引")
class TestResourceService:
    def test_library_matches_gap_skills(self) -> None:
        from webapp.services.resource_service import resource_library

        library = resource_library("EMP_001")
        assert library["counts"]["video"] > 0
        assert library["counts"]["module"] > 0
        # 推荐资源必须命中李明的缺口技能
        assert library["recommended"], "李明缺口多,应有匹配资源"


class TestAssessment:
    def test_questions_deterministic_and_hide_answers(self) -> None:
        from webapp.services import assessment_service as svc

        skills = svc.assessable_skills("EMP_001")
        assert skills, "必须有可测评技能(有课程支撑的)"
        skill_id = skills[0]["skill_id"]
        q1 = svc.build_skill_questions(skill_id)
        q2 = svc.build_skill_questions(skill_id)
        assert q1 == q2
        assert 1 <= len(q1) <= 5
        for q in q1:
            assert "answer_index" in q

    def test_grade_stores_evidence(self, monkeypatch) -> None:
        """测评落档 + 未通过联动推荐课程。"""
        from webapp.services import assessment_service as svc
        from tests.conftest import ensure_test_database

        conn = ensure_test_database()
        store = svc.PostgresAssessmentStore(connection=conn)
        monkeypatch.setattr(svc, "PostgresAssessmentStore", lambda **_: store)

        skills = svc.assessable_skills("EMP_001")
        skill_id = next(s["skill_id"] for s in skills if s["course_count"] >= 1)
        questions = svc.build_skill_questions(skill_id)

        # 全对 → 优秀
        result = svc.grade_assessment("EMP_001", skill_id, [q["answer_index"] for q in questions])
        assert result["verdict"] == "excellent"
        history = svc.assessment_history("EMP_001")
        assert any(h["skill_name"] == result["skill_name"] for h in history)

        # 全错 → 未通过 + 推荐课程
        wrong = [(q["answer_index"] + 1) % len(q["options"]) for q in questions]
        result_fail = svc.grade_assessment("EMP_001", skill_id, wrong)
        assert result_fail["verdict"] == "failed"
        assert result_fail["recommended_courses"], "未通过应联动推荐课程"

        store.reset("EMP_001")
        store.close()
        conn.close()

    def test_team_stats(self, monkeypatch) -> None:
        from webapp.services import assessment_service as svc
        from tests.conftest import ensure_test_database

        conn = ensure_test_database()
        store = svc.PostgresAssessmentStore(connection=conn)
        monkeypatch.setattr(svc, "PostgresAssessmentStore", lambda **_: store)
        store.ensure_schema()
        store.reset("EMP_001")

        stats = svc.team_assessment_stats()
        assert stats["total"] == 0  # 测试库干净

        store.reset("EMP_001")
        store.close()
        conn.close()
