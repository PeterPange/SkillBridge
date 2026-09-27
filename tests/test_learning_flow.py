"""站内学习闭环测试:内容组装 / 进度 / 测验生成 / 自动结业。

集成部分使用 conftest 的测试库(training_store_test_db 同款隔离);
learning_progress 表在测试库中建(不碰开发库)。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from profile.__main__ import DEFAULT_DATA_DIR

LEARNING_DIR = Path(DEFAULT_DATA_DIR).parent / "learning"


def _learning_ready() -> bool:
    return (
        (Path(DEFAULT_DATA_DIR) / "courses.json").exists()
        and any(LEARNING_DIR.glob("CRS_001-*.md"))
    )


class TestQuizGeneration:
    def test_quiz_deterministic_and_hides_answers(self) -> None:
        from webapp.services.learning_service import build_quiz

        q1 = build_quiz("CRS_001")
        q2 = build_quiz("CRS_001")
        assert q1 == q2  # 确定性:同课程同题
        assert q1, "必须有题目"
        for q in q1:
            assert "answer_index" in q  # 服务端持有
            assert len(q["options"]) >= 2
            assert q["options"][q["answer_index"]]  # 正确项存在

    def test_quiz_questions_differ_across_courses(self) -> None:
        from webapp.services.learning_service import build_quiz

        a = build_quiz("CRS_001")
        b = build_quiz("CRS_002")
        assert a[0]["options"][a[0]["answer_index"]] != b[0]["options"][b[0]["answer_index"]]


@pytest.mark.skipif(not _learning_ready(), reason="需要课程数据与单元内容(先 data.collect + crawler run-units)")
class TestLearningFlow:
    def test_course_view_and_unit_progress(self, monkeypatch) -> None:
        """进度标记 → 视图刷新 → 全部完成后测验解锁。"""
        from webapp.services import learning_service as svc

        # 学习进度表指向测试库(隔离)
        from tests.conftest import ensure_test_database

        conn = ensure_test_database()
        store = svc.PostgresLearningProgressStore(connection=conn)
        monkeypatch.setattr(
            svc, "PostgresLearningProgressStore", lambda **_: store
        )

        view = svc.build_course_learning("EMP_001", "CRS_001")
        assert view.total_units >= 8  # 真实单元数
        assert view.completed_units == 0
        assert not view.quiz_unlocked

        # 完成全部单元
        for unit in view.units:
            svc.mark_unit_complete("EMP_001", "CRS_001", unit.index)
        view = svc.build_course_learning("EMP_001", "CRS_001")
        assert view.completed_units == view.total_units
        assert view.quiz_unlocked

        store.reset("EMP_001")
        store.close()
        conn.close()

    def test_quiz_grade_pass_auto_records(self, monkeypatch) -> None:
        """答对全部 → 达标 → 自动写入培训记录(不手填分数)。"""
        from webapp.services import learning_service as svc
        from tests.conftest import ensure_test_database

        conn = ensure_test_database()
        progress = svc.PostgresLearningProgressStore(connection=conn)
        monkeypatch.setattr(svc, "PostgresLearningProgressStore", lambda **_: progress)

        # feedback 的 store 也指向测试库(CLI 同款 patch 思路)
        from feedback.store import PostgresTrainingStore

        training = PostgresTrainingStore(connection=conn)
        training.ensure_schema()
        training.reset()
        import feedback.store as feedback_store_mod

        monkeypatch.setattr(
            feedback_store_mod, "PostgresTrainingStore", lambda **_: training
        )

        questions = svc.build_quiz("CRS_001")
        answers = [q["answer_index"] for q in questions]
        result = svc.grade_quiz("EMP_001", "CRS_001", answers)

        assert result["passed"] is True
        assert result["score"] == 100
        assert result["message"], "必须有产品化提示语"
        records = training.list_records("EMP_001")
        assert any(r.course_id == "CRS_001" and r.passed for r in records), "结业应自动登记"

        training.reset()
        progress.reset("EMP_001")
        training.close()
        progress.close()
        conn.close()

    def test_quiz_fail_does_not_record(self, monkeypatch) -> None:
        """不及格 → 不写培训记录,给出复习建议。"""
        from webapp.services import learning_service as svc
        from tests.conftest import ensure_test_database

        conn = ensure_test_database()
        progress = svc.PostgresLearningProgressStore(connection=conn)
        monkeypatch.setattr(svc, "PostgresLearningProgressStore", lambda **_: progress)
        from feedback.store import PostgresTrainingStore

        training = PostgresTrainingStore(connection=conn)
        training.ensure_schema()
        training.reset()
        import feedback.store as feedback_store_mod

        monkeypatch.setattr(feedback_store_mod, "PostgresTrainingStore", lambda **_: training)

        questions = svc.build_quiz("CRS_001")
        wrong = [(q["answer_index"] + 1) % len(q["options"]) for q in questions]
        result = svc.grade_quiz("EMP_001", "CRS_001", wrong)

        assert result["passed"] is False
        assert training.list_records("EMP_001") == [], "不及格不得写入记录"

        training.reset()
        progress.reset("EMP_001")
        training.close()
        progress.close()
        conn.close()
