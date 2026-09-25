"""反馈闭环集成测试(大纲第十一节验收,阶段 5)。

核心是**可演示的前后对比**,全部走真实数据 + 真实服务:

- 验收用例 1:李明完成 CRS_001 + CRS_003 + CRS_004(均 85 分)后,
  Generative AI 从 0 升到 1,岗位准备度从 29.6% 上升,
  重排后的学习路径比原路径短(已完成课程被剪枝);
- 验收用例 2:考试不及格(60 分)→ 技能不升级 + 追加补基础建议;
- 落库往返:training_record + assessment 写入 PostgreSQL 后可完整读回;
  画像同步知识图谱(HAS_SKILL 等级 + Evidence);
- CLI:complete / status / plan-diff 的文本与 JSON 输出。

需要 Neo4j + PostgreSQL(先 ``make up``),与 tests/test_recommendation.py
同一模式;培训记录表由反馈模块专有,每个用例前清空隔离。
"""

from __future__ import annotations

import json

import pytest

from data.collect import collect_all
from feedback import (
    FLAG_CONSOLIDATE,
    SUGGESTION_REMEDIATE,
    PostgresTrainingStore,
    build_feedback_state,
    build_plan_diff,
    record_completion,
)
from knowledge_graph import builder
from learning_path.models import PRUNE_REASON_COMPLETED
from profile.report import render_evidence_explanation
from skillbridge.db import neo4j_driver


# ---------------------------------------------------------------------------
# 公共 fixture:离线数据 + 图谱 + 培训记录存储
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def processed_dir(tmp_path_factory):
    """离线采集一份标准化数据(与 data/processed/ 同构,测试隔离)。"""
    out_dir = tmp_path_factory.mktemp("processed")
    raw_dir = tmp_path_factory.mktemp("raw")
    collect_all(raw_dir=raw_dir, out_dir=out_dir, offline=True)
    return out_dir


@pytest.fixture(scope="module")
def graph(processed_dir):
    """构建知识图谱一次,供本模块全部集成测试复用。"""
    driver = neo4j_driver()
    builder.build_graph(driver, processed_dir)
    try:
        yield driver
    finally:
        driver.close()


@pytest.fixture()
def store(training_store_test_db):
    """培训记录存储(独立测试库):每个用例前清空,保证隔离。

    闭环写操作会同步 Neo4j 的 HAS_SKILL,但全部断言均基于回放画像
    (事件溯源),不依赖图谱中的员工关系状态,因此无需重建图谱。
    存储指向 tests/conftest.py 的 skillbridge_test 测试库,
    开发库的培训记录不受影响。
    """
    training_store_test_db.reset()
    yield training_store_test_db


@pytest.fixture()
def cli_uses_test_db(store, monkeypatch):
    """让 CLI(main)内部创建的 PostgresTrainingStore 也指向测试库。

    CLI 入口自建 store(直连开发库),不 patch 会把培训记录写进
    开发库,且用例间状态串扰导致断言不稳定。
    """
    import feedback.__main__ as feedback_cli

    monkeypatch.setattr(
        feedback_cli, "PostgresTrainingStore", lambda **_: store
    )


# ---------------------------------------------------------------------------
# 验收用例 1:完成 CRS_001 + CRS_003 + CRS_004(均 85 分)
# ---------------------------------------------------------------------------

def test_acceptance_li_ming_completes_genai_chain(graph, processed_dir, store):
    """李明完成 GenAI 课程链(均 85 分):GenAI 0→1,准备度上升,路径变短。

    - Generative AI 恰好从 0 升到 1(同难度课程不叠加涨级);
    - 岗位准备度从 29.6% 上升(42/142 → 59/142 = 41.5%);
    - 重排路径比原路径短:14 门 → 10 门,已完成的 CRS_001 / CRS_003 /
      CRS_004 全部剪枝,新掌握的 CRS_002(ML 达 2 级)也被免修。
    """
    state_before = build_feedback_state(store, "EMP_001", data_dir=processed_dir)
    assert state_before.update.records == ()  # 无培训记录
    assert state_before.gap_before.readiness == pytest.approx(42 / 142)
    assert f"{state_before.gap_before.readiness:.1%}" == "29.6%"

    diff_before = build_plan_diff(graph, state_before)
    assert diff_before.before.course_count == 14  # 原路径 14 门
    assert {"CRS_001", "CRS_003", "CRS_004"} <= {
        course.course_id for course in diff_before.before.order
    }

    # 完成三门课程(均 85 分),每次登记自动触发闭环重算
    for course_id in ("CRS_001", "CRS_003", "CRS_004"):
        result = record_completion(
            graph, store, "EMP_001", course_id, 85, data_dir=processed_dir
        )
        assert result.record.record_id is not None
        assert result.record.passed is True

    state_after = build_feedback_state(store, "EMP_001", data_dir=processed_dir)

    # ① Generative AI 从 0 升到 1(验收数字)
    assert state_after.profile.level_of("SKILL_006") == 1
    assert state_after.profile.level_of("SKILL_004") == 2  # ML 1 → 2
    assert state_after.profile.level_of("SKILL_007") == 1  # LLM 新增
    assert state_after.profile.level_of("SKILL_010") == 2  # PromptEng 1 → 2

    # ② 准备度从 29.6% 上升(42/142 → 59/142 = 41.5%)
    assert state_after.gap_after.readiness == pytest.approx(59 / 142)
    assert state_after.gap_after.readiness > state_after.gap_before.readiness
    assert f"{state_after.gap_after.readiness:.1%}" == "41.5%"
    assert state_after.gap_after.total_gap < state_after.gap_before.total_gap

    # ③ 重排路径比原路径短,已完成课程被剪枝
    diff_after = build_plan_diff(graph, state_after)
    assert diff_after.after.course_count < diff_after.before.course_count
    assert diff_after.after.course_count == 10
    completed_pruned = {
        item.course.course_id
        for item in diff_after.after.pruned
        if item.reason == PRUNE_REASON_COMPLETED
    }
    assert {"CRS_001", "CRS_003", "CRS_004"} <= completed_pruned
    assert not completed_pruned & {
        course.course_id for course in diff_after.after.order
    }
    assert diff_after.removed_course_ids == [
        "CRS_001", "CRS_003", "CRS_004", "CRS_002",
    ]
    assert diff_after.added_course_ids == []

    # Evidence 可解释:为什么 GenAI 是 Level 1
    evidence = state_after.profile.assessment_of("SKILL_006").evidence
    assert evidence.assessment_score == 85
    assert any(
        "《Introduction to AI concepts》" in note and "85" in note
        for note in evidence.training_records
    )
    explanation = render_evidence_explanation(
        state_after.profile, "SKILL_006", skill_name="Generative AI"
    )
    assert "Level 1" in explanation


def test_closed_loop_refreshes_recommendation_excluding_completed(
    graph, processed_dir, store
):
    """推荐刷新:已完成课程不再出现在 Top-K(候选同步排除)。"""
    result = record_completion(
        graph, store, "EMP_001", "CRS_001", 85, data_dir=processed_dir
    )
    recommendations = result.loop_after.recommendations
    assert "CRS_001" not in {
        rec.course.course_id for rec in recommendations.recommendations
    }
    assert recommendations.candidate_count == 14  # 15 门候选排除已完成的 1 门
    # 未完成的核心课程仍在推荐中
    assert "CRS_004" in {
        rec.course.course_id for rec in recommendations.recommendations
    }


def test_profile_synced_to_knowledge_graph(graph, processed_dir, store):
    """画像刷新同步知识图谱:HAS_SKILL 等级与 Evidence 已更新。"""
    record_completion(
        graph, store, "EMP_001", "CRS_001", 85, data_dir=processed_dir
    )
    with graph.session() as session:
        rows = {
            record["skill_id"]: dict(record)
            for record in session.run(
                """
                MATCH (e:Employee {employee_id: $id})-[r:HAS_SKILL]->(s:Skill)
                WHERE s.skill_id IN ['SKILL_006', 'SKILL_004']
                RETURN s.skill_id AS skill_id, r.level AS level,
                       r.assessment_score AS score,
                       r.training_records AS records
                """,
                id="EMP_001",
            )
        }
    assert rows["SKILL_006"]["level"] == 1
    assert rows["SKILL_006"]["score"] == 85
    assert any("Introduction to AI concepts" in note for note in rows["SKILL_006"]["records"])
    assert rows["SKILL_004"]["level"] == 2


# ---------------------------------------------------------------------------
# 验收用例 2:考试不及格(60 分)→ 不升级 + 补基础建议
# ---------------------------------------------------------------------------

def test_acceptance_fail_no_promotion_and_remediate(graph, processed_dir, store):
    """60 分:技能不升级、准备度不变,追加「补基础」前置课程建议。"""
    result = record_completion(
        graph, store, "EMP_001", "CRS_004", 60, data_dir=processed_dir
    )

    # 不升级:所有等级变化 from == to
    assert result.record.passed is False
    assert result.record.level_changes
    assert all(
        change.from_level == change.to_level
        for change in result.record.level_changes
    )

    # 补基础建议:追加前置课程 CRS_003(Explore Generative AI)
    assert [(s.kind, s.course_id) for s in result.record.suggestions] == [
        (SUGGESTION_REMEDIATE, "CRS_003")
    ]
    assert "Explore Generative AI" in result.record.suggestions[0].course_name

    # 准备度与缺口完全不变(29.6% / 12 项 / 24 级)
    state = build_feedback_state(store, "EMP_001", data_dir=processed_dir)
    assert state.gap_after.readiness == pytest.approx(state.gap_before.readiness)
    assert state.gap_after.total_gap == state.gap_before.total_gap == 24
    assert state.profile.level_of("SKILL_006") == 0

    # 未通过的课程仍留在学习路径中(需要重修),不被剪枝
    diff = build_plan_diff(graph, state)
    assert "CRS_004" in {course.course_id for course in diff.after.order}
    assert diff.after.course_count == diff.before.course_count


def test_consolidate_flow_end_to_end(graph, processed_dir, store):
    """70-84 分:提升 1 级并标记「需巩固」,后续 ≥85 消除标记。"""
    first = record_completion(
        graph, store, "EMP_001", "CRS_001", 78, data_dir=processed_dir
    )
    assert any(
        change.flag == FLAG_CONSOLIDATE for change in first.record.level_changes
    )
    state = build_feedback_state(store, "EMP_001", data_dir=processed_dir)
    assert state.update.flags == {"SKILL_004": FLAG_CONSOLIDATE, "SKILL_006": FLAG_CONSOLIDATE}
    assert state.profile.level_of("SKILL_006") == 1  # 70-84 同样提升 1 级

    # 后续同难度优秀成绩:消除 GenAI 标记(ML 标记保留,因 CRS_003 不授 ML)
    record_completion(
        graph, store, "EMP_001", "CRS_003", 90, data_dir=processed_dir
    )
    state = build_feedback_state(store, "EMP_001", data_dir=processed_dir)
    assert state.update.flags == {"SKILL_004": FLAG_CONSOLIDATE}
    assert state.profile.level_of("SKILL_006") == 1  # 不重复涨级


# ---------------------------------------------------------------------------
# 落库往返:training_record + assessment(PostgreSQL)
# ---------------------------------------------------------------------------

def test_postgres_store_roundtrip(graph, processed_dir, store):
    """写入的等级变化 / 建议 / 分数可从 PostgreSQL 完整读回。"""
    record_completion(
        graph, store, "EMP_001", "CRS_001", 85, data_dir=processed_dir
    )
    records = store.list_records("EMP_001")
    assert len(records) == 1
    record = records[0]
    assert record.course_id == "CRS_001"
    assert record.exam_score == 85
    assert record.passed is True
    assert record.completed_at  # 数据库生成的时间戳
    changes = {c.skill_id: c for c in record.level_changes}
    assert changes["SKILL_006"].from_level == 0
    assert changes["SKILL_006"].to_level == 1
    assert changes["SKILL_004"].from_level == 1
    assert changes["SKILL_004"].to_level == 2
    assert record.suggestions == ()

    # 员工隔离:其他员工查不到
    assert store.list_records("EMP_002") == []


# ---------------------------------------------------------------------------
# CLI:python -m feedback complete / status / plan-diff
# ---------------------------------------------------------------------------

def test_cli_complete(graph, processed_dir, store, cli_uses_test_db, capsys):
    """complete:登记 + 显示技能提升 / 闭环重算 / 培训历史 / 当前准备度。"""
    from feedback.__main__ import main

    assert main([
        "complete", "EMP_001", "CRS_001", "--score", "85",
        "--data-dir", str(processed_dir),
    ]) == 0
    out = capsys.readouterr().out
    assert "培训反馈闭环" in out
    assert "李明 完成《Introduction to AI concepts》" in out
    assert "Generative AI  Level 0 → 1" in out
    assert "Machine Learning  Level 1 → 2" in out
    assert "岗位准备度 : 29.6% → 35.9%" in out
    assert "培训历史(1 条" in out
    assert "当前准备度 : 35.9%" in out
    assert "training_record #1 + assessment" in out


def test_cli_complete_json(graph, processed_dir, store, cli_uses_test_db, capsys):
    """complete --json:结构化输出(供 Agent / LLM 消费)。"""
    from feedback.__main__ import main

    assert main([
        "complete", "EMP_001", "CRS_001", "--score", "85",
        "--data-dir", str(processed_dir), "--json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["record"]["course_id"] == "CRS_001"
    assert payload["record"]["exam_score"] == 85
    assert payload["profile_update"]["passed_course_ids"] == ["CRS_001"]
    assert payload["gap_before"]["summary"]["readiness"] == pytest.approx(42 / 142)
    assert payload["loop_after"]["gap"]["summary"]["readiness"] == pytest.approx(51 / 142)
    assert payload["loop_after"]["path"]["summary"]["course_count"] == 12
    assert payload["graph_synced"] >= 1


def test_cli_status(graph, processed_dir, store, cli_uses_test_db, capsys):
    """status:培训历史 + 画像变化 + 准备度前后对比。"""
    from feedback.__main__ import main

    assert main([
        "complete", "EMP_001", "CRS_001", "--score", "85",
        "--data-dir", str(processed_dir),
    ]) == 0
    capsys.readouterr()
    assert main([
        "status", "EMP_001", "--data-dir", str(processed_dir),
    ]) == 0
    out = capsys.readouterr().out
    assert "培训档案:李明(EMP_001)" in out
    assert "培训历史(1 条,最近在前)" in out
    assert "Generative AI  Level 0 → 1" in out
    assert "岗位准备度 : 29.6% → 35.9%(+6.3 个百分点)" in out


def test_cli_plan_diff(graph, processed_dir, store, cli_uses_test_db, capsys):
    """plan-diff:学习路径前后对比,已完成课程被剪枝。"""
    from feedback.__main__ import main

    for course_id in ("CRS_001", "CRS_003", "CRS_004"):
        assert main([
            "complete", "EMP_001", course_id, "--score", "85",
            "--data-dir", str(processed_dir),
        ]) == 0
    capsys.readouterr()
    assert main([
        "plan-diff", "EMP_001", "--data-dir", str(processed_dir),
    ]) == 0
    out = capsys.readouterr().out
    assert "学习路径前后对比:李明 → AI Engineer" in out
    assert "原路径(未计入培训记录):14 门" in out
    assert "重排路径(计入培训记录,已完成课程剪枝):10 门" in out
    assert "已完成,不再排课(3 门)" in out
    assert "课程数   : 14 → 10(-4)" in out
    assert "不再排课 : CRS_001、CRS_003、CRS_004、CRS_002" in out


def test_cli_plan_diff_json(graph, processed_dir, store, cli_uses_test_db, capsys):
    """plan-diff --json:前后路径与对比指标的结构化输出。"""
    from feedback.__main__ import main

    assert main([
        "complete", "EMP_001", "CRS_001", "--score", "85",
        "--data-dir", str(processed_dir),
    ]) == 0
    capsys.readouterr()
    assert main([
        "plan-diff", "EMP_001", "--data-dir", str(processed_dir), "--json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["before"]["summary"]["course_count"] == 14
    assert payload["after"]["summary"]["course_count"] == 12
    assert payload["comparison"]["removed_course_ids"] == ["CRS_001", "CRS_002"]
    assert payload["comparison"]["added_course_ids"] == []


def test_cli_complete_fail_shows_suggestion(graph, processed_dir, store, cli_uses_test_db, capsys):
    """complete(不及格):显示补基础建议,准备度不变。"""
    from feedback.__main__ import main

    assert main([
        "complete", "EMP_001", "CRS_004", "--score", "60",
        "--data-dir", str(processed_dir),
    ]) == 0
    out = capsys.readouterr().out
    assert "60 分 → 未通过" in out
    assert "补基础建议 : 先完成《Explore Generative AI》(CRS_003)" in out
    assert "岗位准备度 : 29.6% → 29.6%" in out


@pytest.mark.parametrize(
    "argv, message",
    [
        (["complete", "EMP_999", "CRS_001", "--score", "85"], "未知员工"),
        (["complete", "EMP_001", "CRS_999", "--score", "85"], "未知课程"),
        (["complete", "EMP_001", "CRS_001", "--score", "101"], "0-100"),
        (["status", "EMP_999"], "未知员工"),
    ],
)
def test_cli_errors(graph, processed_dir, store, cli_uses_test_db, capsys, argv, message):
    """未知员工 / 课程、非法分数:退出码 1 + 明确错误信息。"""
    from feedback.__main__ import main

    assert main([*argv, "--data-dir", str(processed_dir)]) == 1
    assert message in capsys.readouterr().err
