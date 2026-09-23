"""Course Ranking 纯算法单测(阶段 3A 验收:排序可单测,不依赖数据库)。

验收用例即大纲第六/七节的示例:员工李明 vs AI Engineer 岗位——
对 13 门真实候选课程(Microsoft Learn 目录的难度 / 时长 / 前置关系)
手工验算五因子加权得分,校验 Top-5 排序与推荐理由。
"""

from __future__ import annotations

import json

import pytest

from profile import build_employee_profile, build_gap_report
from recommendation import (
    CandidateCourse,
    CandidatePool,
    CourseContext,
    ScoringWeights,
    build_reasons,
    covered_gaps,
    difficulty_match_score,
    gap_coverage_score,
    importance_score,
    prerequisite_score,
    prerequisite_status,
    rank_candidates,
    recommend_from_pool,
    time_cost_score,
)


# ---------------------------------------------------------------------------
# 测试数据:大纲示例员工 + 真实课程目录(取自 data/fixtures 课程目录)
# ---------------------------------------------------------------------------

def _course(
    course_id: str,
    name: str,
    difficulty: str,
    minutes: int,
    skills: tuple[str, ...],
    prerequisites: tuple[str, ...] = (),
) -> CandidateCourse:
    return CandidateCourse(
        course_id=course_id,
        name=name,
        difficulty=difficulty,
        duration_minutes=minutes,
        url=f"https://learn.microsoft.com/training/{course_id.lower()}/",
        taught_skills=frozenset(skills),
        prerequisites=frozenset(prerequisites),
    )


#: 13 门候选课程:难度 / 时长 / 所授技能 / 前置关系与 data/fixtures 一致
CATALOG = (
    _course("CRS_001", "Introduction to AI concepts", "beginner", 40,
            ("SKILL_004", "SKILL_006")),
    _course("CRS_002", "Introduction to machine learning concepts", "beginner", 93,
            ("SKILL_004",), ("CRS_001",)),
    _course("CRS_003", "Explore Generative AI", "beginner", 37,
            ("SKILL_006",), ("CRS_001",)),
    _course("CRS_004", "Introduction to large language models", "beginner", 25,
            ("SKILL_006", "SKILL_007", "SKILL_010"), ("CRS_003",)),
    _course("CRS_005", "Build RAG applications with Azure Database for PostgreSQL",
            "intermediate", 101, ("SKILL_008", "SKILL_003", "SKILL_001"), ("CRS_004",)),
    _course("CRS_006", "Build and extend AI agents with Microsoft Foundry",
            "intermediate", 59, ("SKILL_009", "SKILL_013"), ("CRS_004",)),
    _course("CRS_007", "Implement generative AI agents with Azure Database for PostgreSQL",
            "intermediate", 62, ("SKILL_009", "SKILL_003"), ("CRS_005", "CRS_006")),
    _course("CRS_009", "Write your first Python code", "beginner", 39,
            ("SKILL_001",)),
    _course("CRS_010", "Explore and analyze data with Python", "intermediate", 60,
            ("SKILL_001", "SKILL_004"), ("CRS_009",)),
    _course("CRS_012", "Build a containerized web application with Docker",
            "beginner", 57, ("SKILL_011",)),
    _course("CRS_014", "Introduction to DevOps principles for machine learning",
            "beginner", 33, ("SKILL_016", "SKILL_015"), ("CRS_002", "CRS_013")),
    _course("CRS_015", "Deploy your AI Copilot with Azure Kubernetes",
            "intermediate", 39, ("SKILL_012", "SKILL_011"), ("CRS_006", "CRS_012")),
    _course("CRS_016", "Monitor your generative AI application",
            "intermediate", 60, ("SKILL_015",), ("CRS_004",)),
)

#: 仅作为前置出现、不是候选的课程上下文(CI/CD 不在李明缺口内)
POOL = CandidatePool(
    candidates=CATALOG,
    prerequisite_context={
        "CRS_013": CourseContext(
            name="Introduction to DevOps", skills=frozenset({"SKILL_016"})
        ),
    },
)


@pytest.fixture()
def li_ming(outline_employee, outline_position):
    """大纲示例:李明的画像与差距报告(GenAI/AI Agent +3 为最大缺口)。"""
    profile = build_employee_profile(outline_employee)
    gap_report = build_gap_report(profile, outline_position)
    return profile, gap_report


# ---------------------------------------------------------------------------
# 验收:大纲示例员工输出合理 Top-5(手工验算)
# ---------------------------------------------------------------------------

def test_acceptance_top5_order_and_scores(li_ming):
    """李明 → AI Engineer:Top-5 排序与加权得分(手工验算,权重 30/25/20/15/10)。

    加权总缺口 W = 3×5 + 3×5 + 1×5 + 1×4 + 1×3 + 1×3 = 45。
    """
    profile, gap_report = li_ming
    ranked = rank_candidates(POOL, gap_report.gaps, profile.level_of, top_k=5)

    assert [course.course_id for course, _, _ in ranked] == [
        "CRS_001",  # AI 基础:覆盖 GenAI+ML 两大缺口,无前置,难度匹配
        "CRS_010",  # Python 数据分析:前置(Python 基础)已凭已有技能满足
        "CRS_004",  # LLM 导论:覆盖最大缺口 GenAI,时长最短
        "CRS_003",  # 探索生成式 AI:前置未满足,时长略长于 CRS_004
        "CRS_007",  # GenAI Agent 实战:覆盖 AI Agent 缺口,两门前置均未满足
    ]
    expected = [
        0.30 * 19 / 45 + 0.25 + 0.20 + 0.15 + 0.10 * 0.60,       # CRS_001
        0.30 * 9 / 45 + 0.25 + 0.20 + 0.15 + 0.10 * 0.50,        # CRS_010
        0.30 * 15 / 45 + 0.25 + 0.20 + 0.00 + 0.10 * 60 / 85,    # CRS_004
        0.30 * 15 / 45 + 0.25 + 0.20 + 0.00 + 0.10 * 60 / 97,    # CRS_003
        0.30 * 15 / 45 + 0.25 + 0.20 + 0.00 + 0.10 * 60 / 122,   # CRS_007
    ]
    for (_, breakdown, _), want in zip(ranked, expected):
        assert breakdown.total == pytest.approx(want, abs=1e-6)


def test_acceptance_report_and_reasons(li_ming):
    """Top-K 报告:排名连续、理由覆盖评分因子、JSON 可序列化(供 LLM 解释)。"""
    profile, gap_report = li_ming
    report = recommend_from_pool(POOL, profile, gap_report, top_k=5)

    assert report.employee_name == "李明"
    assert report.target_position_name == "AI Engineer"
    assert report.candidate_count == 13
    assert [rec.rank for rec in report.recommendations] == [1, 2, 3, 4, 5]
    scores = [rec.score for rec in report.recommendations]
    assert scores == sorted(scores, reverse=True)

    top = report.recommendations[0]
    assert top.course.course_id == "CRS_001"
    assert [(gap.skill_id, gap.gap) for gap in top.covered_gaps] == [
        ("SKILL_006", 3),  # Generative AI(差距报告顺序)
        ("SKILL_004", 1),  # Machine Learning
    ]
    assert top.missing_prerequisites == ()
    assert any("无前置课程" in reason for reason in top.reasons)
    assert any("Generative AI" in reason for reason in top.reasons)

    # CRS_010 的前置(Python 基础)凭已有技能(Python 2)判定为已满足
    second = report.recommendations[1]
    assert [ref.course_id for ref in second.satisfied_prerequisites] == ["CRS_009"]
    assert any("前置课程已满足" in reason for reason in second.reasons)

    # CRS_007 两门前置均未满足,理由需显式提示
    agent = report.recommendations[4]
    assert {ref.course_id for ref in agent.missing_prerequisites} == {
        "CRS_005", "CRS_006",
    }
    assert any("前置课程未满足" in reason for reason in agent.reasons)

    payload = report.to_dict()
    json.dumps(payload, ensure_ascii=False)  # 不抛异常即可
    assert payload["recommendations"][0]["course"]["course_id"] == "CRS_001"
    assert payload["weights"]["gap_coverage"] == pytest.approx(0.30)


def test_acceptance_uncovered_skills_reported(li_ming):
    """有缺口但无课程覆盖的技能进入 uncovered,而非静默丢弃。"""
    profile, gap_report = li_ming
    # 构造仅含 Deep Learning 缺口的岗位(目录中无课程教授该技能)
    deep_learning_position = {
        "position_id": "POS_005",
        "name": "AI Engineer",
        "skills": [
            {"skill_id": "SKILL_005", "importance": 5.0, "required_level": 3},
        ],
    }
    report = build_gap_report(profile, deep_learning_position)
    # 模拟召回结果：无任何课程教授 Deep Learning → 空候选 + 未覆盖缺口
    pool = CandidatePool(uncovered=report.gaps)
    result = recommend_from_pool(pool, profile, report, top_k=5)

    assert result.candidate_count == 0
    assert result.recommendations == ()
    assert [gap.skill_id for gap in result.uncovered_skills] == ["SKILL_005"]


# ---------------------------------------------------------------------------
# 五因子打分(纯函数,逐因子验算)
# ---------------------------------------------------------------------------

def test_gap_coverage_score(li_ming):
    """Gap 覆盖度 = 覆盖的加权缺口 / 全部加权缺口(W = 45)。"""
    _, gap_report = li_ming
    gaps = gap_report.gaps

    # CRS_001 覆盖 GenAI(15) + ML(4)
    assert gap_coverage_score(POOL.candidates[0], gaps) == pytest.approx(19 / 45)
    # CRS_009 仅覆盖 Python(5)
    python_course = next(c for c in CATALOG if c.course_id == "CRS_009")
    assert gap_coverage_score(python_course, gaps) == pytest.approx(5 / 45)
    # 不覆盖任何缺口 → 0
    empty = _course("CRS_999", "无关课程", "beginner", 30, ("SKILL_018",))
    assert gap_coverage_score(empty, gaps) == 0.0


def test_importance_score(li_ming):
    """技能重要性 = 覆盖缺口技能的最高岗位重要度 / 5。"""
    _, gap_report = li_ming
    gaps = gap_report.gaps

    docker_course = next(c for c in CATALOG if c.course_id == "CRS_012")
    assert importance_score(docker_course, gaps) == pytest.approx(3 / 5)
    ml_course = next(c for c in CATALOG if c.course_id == "CRS_002")
    assert importance_score(ml_course, gaps) == pytest.approx(4 / 5)
    genai_course = next(c for c in CATALOG if c.course_id == "CRS_003")
    assert importance_score(genai_course, gaps) == 1.0


def test_difficulty_match_three_branches(li_ming):
    """难度匹配:期望难度由课程所授技能的平均等级推导,按等级距离打分。"""
    profile, _ = li_ming
    level_of = profile.level_of

    # 李明 GenAI=0 → 期望 beginner:beginner 1.0 / intermediate 0.5 / advanced 0
    genai_beginner = next(c for c in CATALOG if c.course_id == "CRS_003")
    assert difficulty_match_score(genai_beginner, level_of) == 1.0
    genai_intermediate = _course(
        "CRS_901", "生成式 AI 进阶", "intermediate", 60, ("SKILL_006",)
    )
    assert difficulty_match_score(genai_intermediate, level_of) == 0.5
    genai_advanced = _course(
        "CRS_902", "生成式 AI 高级", "advanced", 60, ("SKILL_006",)
    )
    assert difficulty_match_score(genai_advanced, level_of) == 0.0

    # 李明 Python=2 → 期望 intermediate:intermediate 1.0,beginner 反而只有 0.5
    python_intermediate = next(c for c in CATALOG if c.course_id == "CRS_010")
    assert difficulty_match_score(python_intermediate, level_of) == 1.0
    python_beginner = next(c for c in CATALOG if c.course_id == "CRS_009")
    assert difficulty_match_score(python_beginner, level_of) == 0.5

    # 员工技能越过硬(等级 3-4)→ 期望 advanced
    senior = build_employee_profile(
        {
            "employee_id": "EMP_009",
            "name": "周杰",
            "department": "AI 创新组",
            "current_position_id": "POS_002",
            "target_position_id": "POS_005",
            "years_of_experience": 5,
            "skills": [
                {
                    "skill_id": "SKILL_006",
                    "level": 3,
                    "evidence": {
                        "assessment_score": 80,
                        "project_experience": "主导 GenAI 项目",
                        "self_assessment": 3,
                        "training_records": ["GenAI 进阶培训已完成"],
                    },
                },
            ],
        }
    )
    genai_advanced_for_senior = _course(
        "CRS_903", "生成式 AI 高级", "advanced", 60, ("SKILL_006",)
    )
    assert difficulty_match_score(genai_advanced_for_senior, senior.level_of) == 1.0
    assert difficulty_match_score(genai_beginner, senior.level_of) == 0.0


def test_prerequisite_score_and_status(li_ming):
    """前置满足:无前置 1.0;所授技能平均等级 ≥ 2 视为满足;未知前置按未满足。"""
    profile, _ = li_ming
    level_of = profile.level_of

    no_prereq = next(c for c in CATALOG if c.course_id == "CRS_001")
    assert prerequisite_score(no_prereq, POOL, level_of) == 1.0

    # CRS_010 的前置 CRS_009 教授 Python(李明 2 级)→ 满足
    data_python = next(c for c in CATALOG if c.course_id == "CRS_010")
    satisfied, missing = prerequisite_status(data_python, POOL, level_of)
    assert [ref.course_id for ref in satisfied] == ["CRS_009"]
    assert missing == ()
    assert prerequisite_score(data_python, POOL, level_of) == 1.0

    # CRS_015 的前置:CRS_012(Docker,李明 1 级 → 未满足)、
    # CRS_006(AI Agent/API,平均 0 → 未满足)
    aks_course = next(c for c in CATALOG if c.course_id == "CRS_015")
    assert prerequisite_score(aks_course, POOL, level_of) == 0.0
    _, missing = prerequisite_status(aks_course, POOL, level_of)
    assert {ref.course_id for ref in missing} == {"CRS_006", "CRS_012"}

    # 图谱中查不到所授技能的前置 → 保守按未满足
    orphan = _course(
        "CRS_904", "孤儿课程", "beginner", 30, ("SKILL_006",), ("CRS_990",)
    )
    assert prerequisite_score(orphan, POOL, level_of) == 0.0

    # 混合满足:构造一门前置为 CRS_009(满足)+ CRS_003(未满足)的课程
    mixed = _course(
        "CRS_905", "混合前置", "beginner", 30,
        ("SKILL_006",), ("CRS_003", "CRS_009"),
    )
    assert prerequisite_score(mixed, POOL, level_of) == pytest.approx(0.5)


def test_time_cost_score():
    """时间成本:1/(1+小时数),单调递减;非正时长不惩罚。"""
    assert time_cost_score(_course("CRS_906", "一小时", "beginner", 60, ("SKILL_006",))) == pytest.approx(0.5)
    assert time_cost_score(_course("CRS_907", "两小时", "beginner", 120, ("SKILL_006",))) == pytest.approx(1 / 3)
    short = time_cost_score(_course("CRS_908", "半小时", "beginner", 30, ("SKILL_006",)))
    assert short > 0.5
    assert time_cost_score(_course("CRS_909", "零时长", "beginner", 0, ("SKILL_006",))) == 1.0


# ---------------------------------------------------------------------------
# 排序确定性与边界
# ---------------------------------------------------------------------------

def test_rank_tie_breaks_by_course_id(li_ming):
    """同分课程按 course_id 升序(确定性)。"""
    profile, gap_report = li_ming
    twin_a = _course("CRS_901", "孪生课程 A", "beginner", 40, ("SKILL_006",))
    twin_b = _course("CRS_902", "孪生课程 B", "beginner", 40, ("SKILL_006",))
    pool = CandidatePool(candidates=(twin_b, twin_a))
    ranked = rank_candidates(pool, gap_report.gaps, profile.level_of)
    assert [course.course_id for course, _, _ in ranked] == ["CRS_901", "CRS_902"]


def test_rank_top_k_truncation_and_full(li_ming):
    """top_k 截断;top_k 超过候选数时返回全部。"""
    profile, gap_report = li_ming
    ranked_top3 = rank_candidates(
        POOL, gap_report.gaps, profile.level_of, top_k=3
    )
    assert len(ranked_top3) == 3
    ranked_all = rank_candidates(POOL, gap_report.gaps, profile.level_of)
    assert len(ranked_all) == len(CATALOG)
    # 前 3 名与全量排序的前 3 名一致
    assert [c.course_id for c, _, _ in ranked_top3] == [
        c.course_id for c, _, _ in ranked_all[:3]
    ]


def test_ranking_is_deterministic(li_ming):
    """同一输入重复排序结果完全一致(可复现)。"""
    profile, gap_report = li_ming
    first = rank_candidates(POOL, gap_report.gaps, profile.level_of, top_k=5)
    second = rank_candidates(POOL, gap_report.gaps, profile.level_of, top_k=5)
    assert first == second


def test_recommend_from_pool_empty_gaps(outline_employee, outline_position):
    """员工已满足岗位全部要求(无缺口)→ 空推荐。"""
    profile = build_employee_profile(outline_employee)
    met_position = {
        "position_id": "POS_005",
        "name": "AI Engineer",
        "skills": [
            {"skill_id": "SKILL_001", "importance": 5.0, "required_level": 1},
        ],
    }
    gap_report = build_gap_report(profile, met_position)
    assert gap_report.gaps == ()

    report = recommend_from_pool(POOL, profile, gap_report, top_k=5)
    assert report.recommendations == ()
    assert report.candidate_count == 13


def test_recommend_from_pool_validates_top_k(li_ming):
    profile, gap_report = li_ming
    with pytest.raises(ValueError, match="top_k"):
        recommend_from_pool(POOL, profile, gap_report, top_k=0)


def test_custom_weights_change_order(li_ming):
    """权重可注入:把前置满足权重调到最高后,无前置课程升到第一。"""
    profile, gap_report = li_ming
    weights = ScoringWeights(
        gap_coverage=0.10, importance=0.10, difficulty_match=0.10,
        prerequisite=0.60, time_cost=0.10,
    )
    report = recommend_from_pool(POOL, profile, gap_report, weights=weights)
    # CRS_001 无前置(1.0),CRS_010 前置已满足(1.0)——两者前置因子并列,
    # 但 CRS_001 的 Gap 覆盖度更高,仍应第一;前置未满足的 CRS_004/CRS_003
    # 掉出前二,由 CRS_009(无前置)顶上。
    assert [rec.course.course_id for rec in report.recommendations[:3]] == [
        "CRS_001", "CRS_010", "CRS_009",
    ]


# ---------------------------------------------------------------------------
# 模型校验
# ---------------------------------------------------------------------------

def test_scoring_weights_validation():
    """权重非负、和为 1。"""
    with pytest.raises(ValueError, match="不能为负"):
        ScoringWeights(gap_coverage=-0.1)
    with pytest.raises(ValueError, match="之和必须为 1"):
        ScoringWeights(gap_coverage=0.5)
    ScoringWeights(
        gap_coverage=0.2, importance=0.2, difficulty_match=0.2,
        prerequisite=0.2, time_cost=0.2,
    )  # 合法


def test_candidate_course_validation():
    """难度枚举与时长校验。"""
    with pytest.raises(ValueError, match="难度"):
        _course("CRS_901", "坏难度", "expert", 30, ("SKILL_006",))
    with pytest.raises(ValueError, match="不能为负"):
        _course("CRS_902", "负时长", "beginner", -5, ("SKILL_006",))


def test_candidate_pool_helpers():
    """taught_skills_of / name_of:候选 → 自身;上下文 → 补充;未知 → 空缺。"""
    assert POOL.taught_skills_of("CRS_001") == frozenset({"SKILL_004", "SKILL_006"})
    assert POOL.name_of("CRS_001") == "Introduction to AI concepts"
    assert POOL.taught_skills_of("CRS_013") == frozenset({"SKILL_016"})
    assert POOL.name_of("CRS_013") == "Introduction to DevOps"
    assert POOL.taught_skills_of("CRS_999") == frozenset()
    assert POOL.name_of("CRS_999") is None


def test_build_reasons_covers_all_factors(li_ming):
    """推荐理由逐因子生成:覆盖缺口 / 难度 / 前置 / 时长。"""
    profile, gap_report = li_ming
    course = next(c for c in CATALOG if c.course_id == "CRS_001")
    covered = covered_gaps(course, gap_report.gaps)
    from recommendation import score_candidate

    breakdown = score_candidate(
        course, gap_report.gaps, POOL, profile.level_of, ScoringWeights()
    )
    reasons = build_reasons(
        course, breakdown, covered, (), (), profile.level_of
    )
    assert len(reasons) == 4
    assert reasons[0].startswith("覆盖 2 项能力缺口")
    assert "Generative AI" in reasons[0] and "Machine Learning" in reasons[0]
    assert "难度" in reasons[1]
    assert reasons[2] == "无前置课程,可立即开始"
    assert "40 分钟" in reasons[3]
