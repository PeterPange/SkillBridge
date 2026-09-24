"""反馈模块单元测试(大纲第十一节):分数映射 / 画像回放 / Evidence 追加 / 存储。

全部使用合成数据,不依赖 Neo4j / PostgreSQL:

- 分数档位:≥85 提升 1 级;70-84 提升 1 级并标记「需巩固」;
  <70 不提升并生成「补基础」建议;
- 同难度不重复涨级:CRS_001 / CRS_003 / CRS_004 都是 beginner 的
  Generative AI 课,完成三门 GenAI 恰好 0 → 1(验收语义);
- Evidence 追加:完成记录写入对应技能,可解释「为什么涨级」;
- 内存存储:与 PostgreSQL 实现同语义(排序 / 往返 / 清空)。
"""

from __future__ import annotations

import pytest

from feedback import (
    FLAG_CONSOLIDATE,
    MemoryTrainingStore,
    SUGGESTION_REMEDIATE,
    SkillLevelChange,
    Suggestion,
    TrainingRecord,
    build_suggestions,
    replay_history,
    score_outcome,
)
from feedback.models import check_exam_score
from feedback.replay import OUTCOME_CONSOLIDATE, OUTCOME_FAIL, OUTCOME_SOLID
from learning_path.models import PathCourse
from profile import build_employee_profile
from profile.report import render_evidence_explanation


# ---------------------------------------------------------------------------
# 合成数据:课程目录(模拟 CRS_001 → CRS_003 → CRS_004 的 GenAI 课程链)
# ---------------------------------------------------------------------------

def make_course(
    course_id: str,
    name: str,
    *,
    difficulty: str = "beginner",
    minutes: int = 60,
    skills: tuple[str, ...] = (),
    prerequisites: tuple[str, ...] = (),
) -> PathCourse:
    """构造合成课程(与 Microsoft Learn 课程同构)。"""
    return PathCourse(
        course_id=course_id,
        name=name,
        difficulty=difficulty,
        duration_minutes=minutes,
        url="",
        taught_skills=frozenset(skills),
        prerequisites=frozenset(prerequisites),
    )


CATALOG: dict[str, PathCourse] = {
    # AI 基础:授 ML + GenAI(对应真实 CRS_001)
    "C_AI": make_course(
        "C_AI", "AI 基础", skills=("SKILL_004", "SKILL_006"),
    ),
    # GenAI 入门:授 GenAI,前置 AI 基础(对应真实 CRS_003)
    "C_GEN": make_course(
        "C_GEN", "生成式 AI 导论", skills=("SKILL_006",), prerequisites=("C_AI",),
    ),
    # LLM 导论:授 GenAI / LLM / PromptEng,前置 GenAI(对应真实 CRS_004)
    "C_LLM": make_course(
        "C_LLM", "LLM 导论",
        skills=("SKILL_006", "SKILL_007", "SKILL_010"),
        prerequisites=("C_GEN",),
    ),
    # ML 进阶:intermediate,授 ML(验证更高难度可继续涨级)
    "C_ML_INT": make_course(
        "C_ML_INT", "ML 进阶", difficulty="intermediate", skills=("SKILL_004",),
    ),
    # Java 入门:授员工已达 4 级的技能(验证等级封顶)
    "C_JAVA": make_course("C_JAVA", "Java 入门", skills=("SKILL_002",)),
}


def make_record(
    course_id: str,
    score: int,
    record_id: int | None = None,
) -> TrainingRecord:
    """构造培训记录(record_id=None 表示落库前预演的待写入记录)。"""
    return TrainingRecord(
        record_id=record_id,
        employee_id="EMP_001",
        course_id=course_id,
        exam_score=score,
        passed=score >= 70,
        completed_at="2025-01-01T00:00:00+00:00",
    )


@pytest.fixture()
def li_ming() -> dict:
    """大纲第六节的李明:Python 2 / Java 4 / ML 1 / GenAI 0 / AI Agent 0。"""
    return {
        "employee_id": "EMP_001",
        "name": "李明",
        "department": "研发中心",
        "current_position_id": "POS_001",
        "target_position_id": "POS_005",
        "years_of_experience": 3,
        "skills": [
            {
                "skill_id": "SKILL_002", "level": 4,
                "evidence": {
                    "assessment_score": 88, "project_experience": "主导 Java 项目",
                    "self_assessment": 4, "training_records": ["Java 高阶培训已完成"],
                },
            },
            {
                "skill_id": "SKILL_001", "level": 2,
                "evidence": {
                    "assessment_score": 44, "project_experience": "参与 Python 项目",
                    "self_assessment": 2, "training_records": ["Python 基础培训已完成"],
                },
            },
            {
                "skill_id": "SKILL_004", "level": 1,
                "evidence": {
                    "assessment_score": 22, "project_experience": "无",
                    "self_assessment": 1, "training_records": [],
                },
            },
            {
                "skill_id": "SKILL_006", "level": 0,
                "evidence": {
                    "assessment_score": 0, "project_experience": "无",
                    "self_assessment": 0, "training_records": [],
                },
            },
        ],
    }


# ---------------------------------------------------------------------------
# 分数档位映射
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "score, expected",
    [
        (100, OUTCOME_SOLID), (85, OUTCOME_SOLID),
        (84, OUTCOME_CONSOLIDATE), (70, OUTCOME_CONSOLIDATE),
        (69, OUTCOME_FAIL), (0, OUTCOME_FAIL),
    ],
)
def test_score_outcome_bands(score, expected):
    """>=85 优秀;70-84 需巩固;<70 未通过。"""
    assert score_outcome(score) == expected


@pytest.mark.parametrize("bad", [101, -1, "85", None, 85.5])
def test_score_outcome_rejects_invalid(bad):
    """非法分数(越界 / 非整数)抛 ValueError。"""
    with pytest.raises(ValueError, match="考试分数"):
        score_outcome(bad) if isinstance(bad, int) else check_exam_score(bad)


# ---------------------------------------------------------------------------
# 通过(≥70):提升 1 级 + Evidence 追加
# ---------------------------------------------------------------------------

def test_pass_solid_raises_one_level_with_evidence(li_ming):
    """85 分通过:所授技能各提升 1 级,培训记录写入 Evidence。"""
    update, changes = replay_history(li_ming, [make_record("C_AI", 85)], CATALOG)

    assert update.updated_record is not None
    profile = build_employee_profile(dict(update.updated_record))
    assert profile.level_of("SKILL_006") == 1  # Generative AI 0 → 1
    assert profile.level_of("SKILL_004") == 2  # Machine Learning 1 → 2

    # Evidence 追加:完成记录写入对应技能,可解释「为什么涨级」
    evidence = profile.assessment_of("SKILL_006").evidence
    assert evidence.assessment_score == 85
    assert any("《AI 基础》" in note and "85" in note for note in evidence.training_records)
    explanation = render_evidence_explanation(profile, "SKILL_006", skill_name="Generative AI")
    assert "Level 1" in explanation
    assert "《AI 基础》" in explanation

    # 逐条记录的变化明细(写入 assessment.level_changes)
    assert len(changes[(None, "C_AI")]) == 2
    assert update.passed_course_ids == {"C_AI"}
    assert update.flags == {}


def test_acceptance_semantics_genai_zero_to_one(li_ming):
    """验收语义:完成 CRS_001 + CRS_003 + CRS_004(均 85)后 GenAI 恰好 0 → 1。

    同一 (技能, 难度) 层只涨一次——三门 beginner 课都授 GenAI,
    不叠加涨级;LLM / PromptEng 首次出现,各 +1。
    """
    records = [
        make_record("C_AI", 85, record_id=1),
        make_record("C_GEN", 85, record_id=2),
        make_record("C_LLM", 85, record_id=3),
    ]
    update, _ = replay_history(li_ming, records, CATALOG)
    profile = build_employee_profile(dict(update.updated_record))

    assert profile.level_of("SKILL_006") == 1  # GenAI:0 → 1(不叠加到 3)
    assert profile.level_of("SKILL_004") == 2  # ML:C_AI 首次 +1
    assert profile.level_of("SKILL_007") == 1  # LLM:新技能 0 → 1
    assert profile.level_of("SKILL_010") == 1  # PromptEng:新技能 0 → 1
    assert update.passed_course_ids == {"C_AI", "C_GEN", "C_LLM"}


def test_higher_difficulty_raises_again(li_ming):
    """更高难度的课程可继续涨级:beginner +1 后 intermediate 再 +1。"""
    records = [
        make_record("C_AI", 85, record_id=1),
        make_record("C_ML_INT", 85, record_id=2),
    ]
    update, _ = replay_history(li_ming, records, CATALOG)
    profile = build_employee_profile(dict(update.updated_record))
    assert profile.level_of("SKILL_004") == 3  # ML:1 → 2(beginner)→ 3(intermediate)


def test_level_capped_at_max(li_ming):
    """已达 4 级的技能不再提升(Java 4 → 4)。"""
    update, changes = replay_history(li_ming, [make_record("C_JAVA", 85)], CATALOG)
    profile = build_employee_profile(dict(update.updated_record))
    assert profile.level_of("SKILL_002") == 4
    change = changes[(None, "C_JAVA")][0]
    assert (change.from_level, change.to_level) == (4, 4)


def test_new_skill_gets_complete_evidence(li_ming):
    """培训新获得的技能具备完整四类 Evidence,可直接构建画像。"""
    update, _ = replay_history(li_ming, [make_record("C_LLM", 85)], CATALOG)
    profile = build_employee_profile(dict(update.updated_record))  # 校验通过即证明
    evidence = profile.assessment_of("SKILL_007").evidence
    assert evidence.assessment_score == 85
    assert evidence.project_experience == "无相关项目经历"
    assert evidence.self_assessment == 0
    assert evidence.training_records  # 培训记录非空


# ---------------------------------------------------------------------------
# 70-84:提升 1 级但标记「需巩固」,后续 ≥85 可消除
# ---------------------------------------------------------------------------

def test_consolidate_flag_set_and_cleared(li_ming):
    """78 分:+1 级并标记「需巩固」;后续同难度 90 分消除标记、不再涨级。"""
    first = [make_record("C_AI", 78, record_id=1)]
    update, changes = replay_history(li_ming, first, CATALOG)
    assert update.flags == {"SKILL_004": FLAG_CONSOLIDATE, "SKILL_006": FLAG_CONSOLIDATE}
    assert all(c.flag == FLAG_CONSOLIDATE for c in changes[(1, "C_AI")])

    # 后续优秀成绩:消除 GenAI 的标记(C_GEN 只授 GenAI),ML 标记保留
    update2, changes2 = replay_history(
        li_ming, [*first, make_record("C_GEN", 90, record_id=2)], CATALOG
    )
    assert update2.flags == {"SKILL_004": FLAG_CONSOLIDATE}
    profile = build_employee_profile(dict(update2.updated_record))
    assert profile.level_of("SKILL_006") == 1  # 不重复涨级
    evidence = profile.assessment_of("SKILL_006").evidence
    assert any("标记已消除" in note for note in evidence.training_records)
    assert evidence.assessment_score == 90
    # 消除标记也是一次可解释的变化(写入 assessment)
    clearing = changes2[(2, "C_GEN")]
    assert len(clearing) == 1 and clearing[0].from_level == clearing[0].to_level


# ---------------------------------------------------------------------------
# <70:不提升 + 补基础建议(追加前置课程)
# ---------------------------------------------------------------------------

def test_fail_no_raise_and_remediate_suggestion(li_ming):
    """60 分:技能不升级,生成「补基础」建议(追加前置课程 C_GEN)。"""
    records = [make_record("C_LLM", 60, record_id=1)]
    update, changes = replay_history(li_ming, records, CATALOG)
    profile = build_employee_profile(dict(update.updated_record))

    assert profile.level_of("SKILL_006") == 0  # 不升级
    assert profile.level_of("SKILL_007") == 0
    assert update.passed_course_ids == frozenset()
    assert update.flags == {}

    suggestions = build_suggestions(CATALOG["C_LLM"], CATALOG, update.passed_course_ids)
    assert [(s.kind, s.course_id) for s in suggestions] == [
        (SUGGESTION_REMEDIATE, "C_GEN")
    ]
    assert "前置课程" in suggestions[0].reason

    # 未通过也写入 Evidence(考试历史是诚实证据)
    evidence = profile.assessment_of("SKILL_006").evidence
    assert any("60 分未通过" in note for note in evidence.training_records)
    assert all(c.from_level == c.to_level for c in changes[(1, "C_LLM")])


def test_fail_without_pending_prereq_suggests_retake(li_ming):
    """无前置课程可补时,建议重修本课程(C_AI 无前置)。"""
    suggestions = build_suggestions(CATALOG["C_AI"], CATALOG, frozenset())
    assert len(suggestions) == 1
    assert suggestions[0].course_id == "C_AI"
    assert "重修" in suggestions[0].reason


def test_fail_after_pass_no_duplicate_negative_evidence(li_ming):
    """通过后重考失败:不重复记负面证据,也不生成补基础建议。"""
    records = [
        make_record("C_AI", 85, record_id=1),
        make_record("C_AI", 60, record_id=2),  # 重考失败
    ]
    update, changes = replay_history(li_ming, records, CATALOG)
    profile = build_employee_profile(dict(update.updated_record))
    assert profile.level_of("SKILL_006") == 1  # 已通过的成绩不受重考失败影响
    assert update.passed_course_ids == {"C_AI"}
    evidence = profile.assessment_of("SKILL_006").evidence
    assert sum("未通过" in note for note in evidence.training_records) == 0
    assert changes[(2, "C_AI")] == []  # 无新变化


def test_replay_is_deterministic(li_ming):
    """事件溯源:同一历史重放两次结果完全一致。"""
    records = [
        make_record("C_AI", 78, record_id=1),
        make_record("C_GEN", 90, record_id=2),
        make_record("C_LLM", 60, record_id=3),
    ]
    first, _ = replay_history(li_ming, records, CATALOG)
    second, _ = replay_history(li_ming, records, CATALOG)
    assert first.updated_record == second.updated_record
    assert first.changes == second.changes
    assert first.flags == second.flags
    assert first.passed_course_ids == second.passed_course_ids


def test_replay_rejects_unknown_course(li_ming):
    """培训记录引用目录外课程 → ValueError(数据不一致防御)。"""
    with pytest.raises(ValueError, match="未知课程"):
        replay_history(li_ming, [make_record("C_MISSING", 85)], CATALOG)


# ---------------------------------------------------------------------------
# 内存存储(与 PostgreSQL 实现同语义)
# ---------------------------------------------------------------------------

def test_memory_store_roundtrip_and_ordering():
    """写入 → 查询:按 record_id 升序,等级变化与建议完整往返。"""
    store = MemoryTrainingStore()
    store.ensure_schema()
    change = SkillLevelChange(
        skill_id="SKILL_006", skill_name="Generative AI",
        from_level=0, to_level=1, flag=None, note="完成《AI 基础》",
    )
    suggestion = Suggestion(
        kind=SUGGESTION_REMEDIATE, course_id="C_GEN",
        course_name="生成式 AI 导论", reason="先补前置",
    )
    store.add_record("EMP_001", "C_AI", 85, passed=True,
                     level_changes=[change], suggestions=[suggestion])
    store.add_record("EMP_002", "C_LLM", 60, passed=False)
    store.add_record("EMP_001", "C_GEN", 90, passed=True)

    records = store.list_records("EMP_001")
    assert [r.course_id for r in records] == ["C_AI", "C_GEN"]
    assert [r.record_id for r in records] == [1, 3]
    assert records[0].level_changes == (change,)
    assert records[0].suggestions == (suggestion,)
    assert records[0].passed is True
    assert store.list_records("EMP_002")[0].passed is False
    assert store.list_records("EMP_999") == []

    store.reset()
    assert store.list_records("EMP_001") == []
    fresh = store.add_record("EMP_001", "C_AI", 85, passed=True)
    assert fresh.record_id == 1  # 清空后 ID 从 1 重新自增
