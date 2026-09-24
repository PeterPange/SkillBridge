"""推荐模块集成测试(阶段 3A):图谱候选召回 + 端到端 Top-5 + CLI。

- 候选生成:离线采集数据 → 构建图谱 → 按 Skill Gap 沿 TEACHES 关系召回;
- 端到端验收:示例员工李明(生成器 seed 42)→ AI Engineer,输出合理 Top-5;
- CLI:`python -m recommendation EMP_001` 文本与 JSON 输出。

需要 Neo4j(先 ``make up``),与 tests/test_knowledge_graph.py 同一模式。
"""

from __future__ import annotations

import json

import pytest

from data.collect import collect_all
from data.employees import generate_employees
from knowledge_graph import builder
from profile import build_employee_profile, build_gap_report
from recommendation import generate_candidates, recommend_courses, render_recommendation_report
from skillbridge.db import neo4j_driver


# ---------------------------------------------------------------------------
# 公共 fixture:离线数据 + 图谱(本模块全部集成测试复用)
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


@pytest.fixture(scope="module")
def li_ming_setup(processed_dir):
    """示例员工李明(生成器 seed 42)vs AI Engineer 的画像与差距报告。"""
    employees = json.loads(
        (processed_dir / "employees.json").read_text(encoding="utf-8")
    )["employees"]
    positions = json.loads(
        (processed_dir / "positions.json").read_text(encoding="utf-8")
    )["positions"]
    positions_by_id = {position["position_id"]: position for position in positions}

    record = next(e for e in employees if e["employee_id"] == "EMP_001")
    assert record["name"] == "李明"
    profile = build_employee_profile(record)
    gap_report = build_gap_report(
        profile, positions_by_id[profile.target_position_id]
    )
    return profile, gap_report


# ---------------------------------------------------------------------------
# Candidate Generation:按 Skill Gap 从图谱找 TEACHES 关系课程
# ---------------------------------------------------------------------------

def test_candidate_generation_from_graph(graph, li_ming_setup):
    """召回的每门候选课程都至少教授一项缺口技能(TEACHES 关系)。"""
    driver, (_, gap_report) = graph, li_ming_setup
    pool = generate_candidates(driver, gap_report.gaps)

    gap_ids = {gap.skill_id for gap in gap_report.gaps}
    assert pool.candidates, "李明缺口众多,候选不应为空"
    for course in pool.candidates:
        assert course.taught_skills & gap_ids, f"{course.course_id} 未覆盖任何缺口"
        assert course.duration_minutes > 0
        assert course.difficulty in ("beginner", "intermediate", "advanced")

    # 候选按 course_id 升序(确定性)
    ids = [course.course_id for course in pool.candidates]
    assert ids == sorted(ids)

    # 大纲示例链路:缺 AI Agent → Build and extend AI agents(CRS_006)在候选中
    assert "CRS_006" in ids
    # AI 基础课(覆盖 GenAI/ML 缺口)在候选中
    assert "CRS_001" in ids

    # 李明的全部缺口技能均有课程覆盖 → 无未覆盖项
    assert pool.uncovered == ()


def test_candidate_generation_carries_prerequisite_context(graph, li_ming_setup):
    """仅作为前置出现的课程(如 CRS_012 Docker)补充名称与所授技能上下文。"""
    driver, (_, gap_report) = graph, li_ming_setup
    pool = generate_candidates(driver, gap_report.gaps)

    # CRS_015 的前置 CRS_012(容器课)不在候选中(Docker 已达标,非缺口),
    # 但前置满足判定需要它的所授技能
    assert "CRS_012" not in {course.course_id for course in pool.candidates}
    assert pool.taught_skills_of("CRS_012") == {"SKILL_011"}
    assert pool.name_of("CRS_012")


def test_candidate_generation_empty_gaps(graph):
    """无缺口 → 空候选池。"""
    pool = generate_candidates(graph, [])
    assert pool.candidates == ()
    assert pool.uncovered == ()


def test_candidate_generation_excludes_completed(graph, li_ming_setup):
    """exclude:已完成的课程不再召回为候选(闭环重算不重复推荐)。

    被排除的课程若作为其他候选的前置,仍进入前置上下文
    (前置满足判定需要它的所授技能)。
    """
    driver, (_, gap_report) = graph, li_ming_setup
    pool = generate_candidates(
        driver, gap_report.gaps, exclude={"CRS_001", "CRS_004"}
    )
    ids = {course.course_id for course in pool.candidates}
    assert "CRS_001" not in ids
    assert "CRS_004" not in ids
    # 其余候选照常召回(15 门 - 2 门排除)
    assert len(ids) == 13
    # 被排除的课程作为保留候选的前置,仍可解析名称与所授技能:
    # CRS_001 是 CRS_002/CRS_003/CRS_008 的前置,CRS_004 是 CRS_005/CRS_006 的前置
    assert pool.name_of("CRS_001") == "Introduction to AI concepts"
    assert pool.taught_skills_of("CRS_001") == {"SKILL_004", "SKILL_006"}
    assert pool.name_of("CRS_004") == "Introduction to large language models"
    assert pool.taught_skills_of("CRS_004") == {"SKILL_006", "SKILL_007", "SKILL_010"}


# ---------------------------------------------------------------------------
# 端到端验收:示例员工输出合理 Top-5
# ---------------------------------------------------------------------------

def test_acceptance_li_ming_top5(graph, li_ming_setup):
    """李明 → AI Engineer:Top-5 合理(手工验算的确定性排序)。

    李明(Java 后端,GenAI/AI Agent/RAG 为最大缺口)的合理推荐:
    AI 基础概念 → Python 数据分析(前置已凭 Python 2 满足)→
    LLM 导论 → Azure 基础(无前置、时长短)→ Python 入门(难度偏低)。
    """
    driver, (profile, gap_report) = graph, li_ming_setup
    report = recommend_courses(driver, profile, gap_report, top_k=5)

    assert [rec.course.course_id for rec in report.recommendations] == [
        "CRS_001", "CRS_010", "CRS_004", "CRS_017", "CRS_009",
    ]
    # 得分降序、排名连续
    scores = [rec.score for rec in report.recommendations]
    assert scores == sorted(scores, reverse=True)
    assert [rec.rank for rec in report.recommendations] == [1, 2, 3, 4, 5]

    # 每条推荐都覆盖至少一项缺口,且覆盖缺口 ⊆ 差距报告
    gap_ids = {gap.skill_id for gap in gap_report.gaps}
    for rec in report.recommendations:
        assert rec.covered_gaps
        assert {gap.skill_id for gap in rec.covered_gaps} <= gap_ids
        assert rec.reasons, "每条推荐必须携带理由(供 LLM 解释)"

    # 第一名:AI 基础概念,覆盖最大缺口 Generative AI,无前置
    top = report.recommendations[0]
    assert top.course.name == "Introduction to AI concepts"
    assert "SKILL_006" in {gap.skill_id for gap in top.covered_gaps}
    assert top.missing_prerequisites == ()

    # 第二名:Python 数据分析,前置(Python 入门课)凭已有技能判定为已满足
    second = report.recommendations[1]
    assert [ref.course_id for ref in second.satisfied_prerequisites] == ["CRS_009"]

    # 第三名:LLM 导论覆盖 GenAI/LLM/PromptEng 三项缺口,但前置未满足
    third = report.recommendations[2]
    assert {gap.skill_id for gap in third.covered_gaps} == {
        "SKILL_006", "SKILL_007", "SKILL_010",
    }
    assert [ref.course_id for ref in third.missing_prerequisites] == ["CRS_003"]


def test_acceptance_report_serializable_and_deterministic(graph, li_ming_setup):
    """报告 JSON 可序列化(供 Agent / LLM 消费),重复推荐结果一致。"""
    driver, (profile, gap_report) = graph, li_ming_setup
    report = recommend_courses(driver, profile, gap_report, top_k=5)
    again = recommend_courses(driver, profile, gap_report, top_k=5)

    assert report == again
    payload = report.to_dict()
    json.dumps(payload, ensure_ascii=False)
    assert payload["employee"]["name"] == "李明"
    assert payload["target_position"]["position_id"] == "POS_005"
    assert payload["candidate_count"] == 15
    assert len(payload["recommendations"]) == 5
    assert payload["weights"]["prerequisite"] == 0.15
    # 每条推荐含分项得分与理由
    for item in payload["recommendations"]:
        assert set(item["score_breakdown"]) == {
            "gap_coverage", "importance", "difficulty_match",
            "prerequisite", "time_cost", "total",
        }
        assert item["reasons"]


def test_acceptance_uncovered_skill_reported(graph, processed_dir):
    """缺口技能无课程覆盖时(Deep Learning),报告显式提示而非静默丢弃。"""
    employees = json.loads(
        (processed_dir / "employees.json").read_text(encoding="utf-8")
    )["employees"]
    record = next(e for e in employees if e["employee_id"] == "EMP_001")
    profile = build_employee_profile(record)
    deep_learning_position = {
        "position_id": "POS_005",
        "name": "AI Engineer",
        "skills": [
            {"skill_id": "SKILL_005", "importance": 5.0, "required_level": 3},
        ],
    }
    gap_report = build_gap_report(profile, deep_learning_position)

    report = recommend_courses(graph, profile, gap_report, top_k=5)
    assert report.candidate_count == 0
    assert report.recommendations == ()
    assert [gap.skill_id for gap in report.uncovered_skills] == ["SKILL_005"]

    rendered = render_recommendation_report(report)
    assert "未找到教授缺口技能的课程" in rendered
    assert "Deep Learning" in rendered


def test_all_ten_employees_get_valid_reports(graph, processed_dir):
    """全部 10 名模拟员工均可产出合法推荐报告(数据管线兼容性)。"""
    employees = json.loads(
        (processed_dir / "employees.json").read_text(encoding="utf-8")
    )["employees"]
    positions = json.loads(
        (processed_dir / "positions.json").read_text(encoding="utf-8")
    )["positions"]
    positions_by_id = {position["position_id"]: position for position in positions}

    for record in employees:
        profile = build_employee_profile(record)
        gap_report = build_gap_report(
            profile, positions_by_id[profile.target_position_id]
        )
        report = recommend_courses(graph, profile, gap_report, top_k=5)
        assert 0 <= report.candidate_count
        for rec in report.recommendations:
            assert 0.0 <= rec.score <= 1.0
            assert rec.covered_gaps
        json.dumps(report.to_dict(), ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI:python -m recommendation
# ---------------------------------------------------------------------------

def test_cli_default_top5(graph, processed_dir, capsys):
    from recommendation.__main__ import main

    assert main(["EMP_001", "--data-dir", str(processed_dir)]) == 0
    out = capsys.readouterr().out
    assert "个性化课程推荐" in out
    assert "李明" in out
    assert "AI Engineer" in out
    assert "CRS_001" in out
    assert "评分" in out
    assert "推荐理由" in out
    assert "候选课程 : 15 门" in out


def test_cli_json_output(graph, processed_dir, capsys):
    from recommendation.__main__ import main

    assert main(
        ["EMP_001", "--data-dir", str(processed_dir), "--json"]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["employee"]["employee_id"] == "EMP_001"
    assert len(payload["recommendations"]) == 5
    assert payload["recommendations"][0]["course"]["course_id"] == "CRS_001"


def test_cli_top_k_option(graph, processed_dir, capsys):
    from recommendation.__main__ import main

    assert main(
        ["EMP_001", "--data-dir", str(processed_dir), "--top-k", "3"]
    ) == 0
    out = capsys.readouterr().out
    assert "推荐前 3 门" in out
    assert out.count("评分 ") == 3  # 恰好 3 条推荐


def test_cli_list(graph, processed_dir, capsys):
    from recommendation.__main__ import main

    assert main(["--list", "--data-dir", str(processed_dir)]) == 0
    out = capsys.readouterr().out
    assert "EMP_001" in out
    assert "李明" in out


def test_cli_unknown_employee(graph, processed_dir, capsys):
    from recommendation.__main__ import main

    assert main(["EMP_999", "--data-dir", str(processed_dir)]) == 1
    assert "未知员工" in capsys.readouterr().err


def test_cli_invalid_top_k(graph, processed_dir, capsys):
    from recommendation.__main__ import main

    assert main(
        ["EMP_001", "--data-dir", str(processed_dir), "--top-k", "0"]
    ) == 1
    assert "top-k" in capsys.readouterr().err
