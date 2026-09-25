"""Web 服务层测试:视图模型组装 + 「算法细节不泄漏」约束。

核心断言:产品视图里不允许出现向量得分、后端名、维度、
未舍入小数等中间数据——这是本层的存在意义。
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from webapp.services.viewmodels import (
    SkillView,
    bucket_of,
    readiness_percent,
)


def _webapp_ready() -> bool:
    """数据与依赖齐备才跑集成部分(与 rag 测试同一套前置)。"""
    return (Path(__file__).resolve().parent.parent / "data" / "processed" / "employees.json").exists()


class TestViewmodels:
    def test_readiness_percent_rounds(self) -> None:
        assert readiness_percent(0.4154929577464789) == 42
        assert readiness_percent(0.29577464788732394) == 30
        assert readiness_percent(1.0) == 100

    def test_bucket_thresholds(self) -> None:
        assert bucket_of(0.85) == "ready"
        assert bucket_of(0.6) == "close"
        assert bucket_of(0.3) == "far"

    def test_skill_status_labels(self) -> None:
        assert SkillView(name="x", level=3, required_level=3, status="met").status_label == "已达标"
        assert SkillView(name="x", level=0, required_level=3, status="missing").status_label == "待补齐"

    def test_gapview_summary_core(self) -> None:
        from webapp.services.viewmodels import GapView

        core = GapView(skill="RAG", current=0, required=3, is_core=True, suggestion="优先")
        assert "核心技能" in core.summary
        assert "深度缺口" in core.summary


@pytest.mark.skipif(not _webapp_ready(), reason="需要 data/processed 数据(先 python -m data.collect)")
class TestEmployeeService:
    def test_home_view_hides_algorithm_internals(self) -> None:
        """产品视图不得泄漏算法中间数据。"""
        import dataclasses
        import json

        from webapp.services.employee_service import build_employee_home

        view = build_employee_home("EMP_001")
        raw = json.dumps(dataclasses.asdict(view), ensure_ascii=False)

        forbidden = [
            "vector_score",
            "lexical_score",
            "weighted_gap",
            "gap_ratio",
            "backend",
            "sentence-transformers",
            "paraphrase",
            "384",
            "importance",
        ]
        for token in forbidden:
            assert token not in raw, f"产品视图泄漏了算法细节:{token}"

        assert 0 <= view.readiness_percent <= 100
        assert isinstance(view.readiness_percent, int)
        assert view.recommendations  # 有推荐
        assert view.plan  # 有计划
        # 推荐理由是给人看的:非空、无小数评分
        for r in view.recommendations:
            assert r.reasons, "推荐卡片必须带纯文字理由"

    def test_progress_counts(self) -> None:
        from webapp.services.employee_service import build_employee_home

        view = build_employee_home("EMP_001")
        assert view.progress.completed_count >= 0
        assert view.progress.total_weeks >= 1


@pytest.mark.skipif(not _webapp_ready(), reason="需要 data/processed 数据(先 python -m data.collect)")
class TestHrService:
    def test_hr_home_aggregates_team(self) -> None:
        import dataclasses
        import json

        from webapp.services.hr_service import build_hr_home

        view = build_hr_home()
        assert view.team_size >= 1
        assert sum(view.buckets.values()) == view.team_size
        assert 0 <= view.average_readiness <= 100
        assert len(view.members) == view.team_size
        # 缺口排行:缺的人数不超过团队规模
        for gap in view.top_team_gaps:
            assert 0 < gap.lacking_count <= gap.team_size
            assert 0 <= gap.coverage_percent <= 100
        # 不泄漏
        raw = json.dumps(dataclasses.asdict(view), ensure_ascii=False)
        for token in ["vector_score", "weighted_gap", "importance", "backend"]:
            assert token not in raw, f"HR 视图泄漏了算法细节:{token}"
