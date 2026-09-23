"""学习路径集成测试(阶段 3B):图谱端到端 + 8 周计划可复现 + CLI。

- 端到端验收:示例员工李明(生成器 seed 42)→ AI Engineer,
  默认每周 4 小时、截止 8 周,输出合法拓扑序周计划(手工验算的
  确定性结果,即大纲第八节「8 周培训计划」示例的可复现版本);
- 全部 10 名模拟员工的计划均满足拓扑合法性与时间约束;
- CLI:`python -m learning_path EMP_001` 文本与 JSON 输出。

需要 Neo4j(先 ``make up``),与 tests/test_recommendation.py 同一模式。
"""

from __future__ import annotations

import json

import pytest

from data.collect import collect_all
from knowledge_graph import builder
from learning_path import generate_learning_path, render_learning_path_report
from profile import build_employee_profile, build_gap_report
from skillbridge.db import neo4j_driver

#: 每周 4 小时的周预算(分钟)
WEEKLY_BUDGET = 240.0


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


def _assert_valid_plan(report) -> None:
    """周计划合法性:预算不超 + 拓扑合法 + 总量守恒(全部员工通用)。"""
    # 1) 每周负载 ≤ 每周预算
    for plan in report.weeks:
        assert plan.minutes <= plan.budget_minutes + 1e-9

    # 2) 拓扑合法:任一课程的保留前置必须出现在更早的周(或同周更早位置)
    position: dict[str, tuple[int, int]] = {}
    for plan in report.weeks:
        for index, item in enumerate(plan.courses):
            position[item.course.course_id] = (plan.week, index)
    kept_ids = set(position)
    courses_by_id = {course.course_id: course for course in report.order}
    for course_id, where in position.items():
        for prereq_id in courses_by_id[course_id].prerequisites:
            if prereq_id in kept_ids:  # 已剪枝的前置凭已有技能满足
                assert position[prereq_id] < where, (
                    f"{prereq_id} 必须先于 {course_id} 学习"
                )

    # 3) 总量守恒:周计划分钟数之和 = 课程时长之和
    assert report.total_minutes == sum(
        course.duration_minutes for course in report.order
    )


# ---------------------------------------------------------------------------
# 端到端验收:李明的 8 周截止周计划(可复现)
# ---------------------------------------------------------------------------

def test_acceptance_li_ming_weekly_plan(graph, li_ming_setup):
    """验收:python -m learning_path EMP_001 输出合法拓扑序周计划。

    默认每周 4 小时、截止 8 周,手工验算的确定性结果:

    - 候选 15 门 → 剪枝已掌握 2 门(Python/Docker 的 beginner 课)
      → 补齐前置后待学 14 门,共 754 分钟;
    - 第 1 周 AI 基础链(概念→GenAI→LLM→RAG),第 2 周 Agent 与
      Python 进阶,第 3 周治理/ML/部署,第 4 周监控与 DevOps;
    - 4 周完成 ≤ 8 周截止,可按期完成。
    """
    driver, (profile, gap_report) = graph, li_ming_setup
    report = generate_learning_path(driver, profile, gap_report)

    assert report.hours_per_week == 4.0
    assert report.deadline_weeks == 8

    # 剪枝:李明已掌握的课程(Python 2 / Docker 2 ≥ beginner 门槛 2)
    assert [item.course.course_id for item in report.pruned] == [
        "CRS_009", "CRS_012",
    ]
    assert all(item.threshold == 2.0 for item in report.pruned)

    # 拓扑序(核心缺口优先:GenAI 链先行,凭已有技能跳过已剪枝前置)
    assert [course.course_id for course in report.order] == [
        "CRS_001", "CRS_003", "CRS_004", "CRS_005",  # AI 基础链
        "CRS_006", "CRS_007", "CRS_010",             # AI Agent + Python 进阶
        "CRS_008", "CRS_002", "CRS_015",             # 治理 / ML / K8s 部署
        "CRS_016", "CRS_013", "CRS_014", "CRS_017",  # 监控 / DevOps / Azure
    ]

    # 周计划(每周预算 240 分钟)
    assert [
        (plan.week, [item.course.course_id for item in plan.courses], plan.minutes)
        for plan in report.weeks
    ] == [
        (1, ["CRS_001", "CRS_003", "CRS_004", "CRS_005"], 203),
        (2, ["CRS_006", "CRS_007", "CRS_010"], 181),
        (3, ["CRS_008", "CRS_002", "CRS_015"], 207),
        (4, ["CRS_016", "CRS_013", "CRS_014", "CRS_017"], 163),
    ]

    assert report.course_count == 14
    assert report.planned_weeks == 4
    assert report.total_minutes == 754
    assert report.fits_deadline  # 4 周 ≤ 8 周截止
    _assert_valid_plan(report)


def test_acceptance_plan_reproducible(graph, li_ming_setup):
    """8 周计划示例可复现:重复生成结果一致,JSON 可序列化。"""
    driver, (profile, gap_report) = graph, li_ming_setup
    report = generate_learning_path(driver, profile, gap_report)
    again = generate_learning_path(driver, profile, gap_report)

    assert report == again
    payload = report.to_dict()
    json.dumps(payload, ensure_ascii=False)
    assert payload["summary"] == {
        "course_count": 14,
        "planned_weeks": 4,
        "total_minutes": 754.0,
        "total_hours": 12.57,
        "pruned_count": 2,
        "fits_deadline": True,
    }
    assert payload["covered_gaps"]["CRS_006"][0]["skill_name"] == "AI Agent"


def test_acceptance_rendered_report(graph, li_ming_setup):
    """文本渲染:周计划 + 剪枝明细 + 截止期限结论。"""
    driver, (profile, gap_report) = graph, li_ming_setup
    rendered = render_learning_path_report(
        generate_learning_path(driver, profile, gap_report)
    )
    assert "自适应学习路径:李明 → AI Engineer" in rendered
    assert "每周 4 小时(预算 240 分钟) · 截止 8 周" in rendered
    assert "第 1 周   203 / 240 分钟" in rendered
    assert "Introduction to AI concepts(CRS_001)" in rendered
    assert "已掌握,跳过(2 门" in rendered
    assert "Write your first Python code(CRS_009)" in rendered
    assert "4 周完成 · 可按期完成(截止 8 周)" in rendered


def test_deadline_exceeded_reported(graph, li_ming_setup):
    """截止期限收紧到 2 周:计划不截断,显式提示超出。"""
    driver, (profile, gap_report) = graph, li_ming_setup
    report = generate_learning_path(
        driver, profile, gap_report, deadline_weeks=2
    )
    assert report.planned_weeks == 4
    assert not report.fits_deadline
    rendered = render_learning_path_report(report)
    assert "超出截止期限 2 周" in rendered


def test_hours_per_week_changes_packing(graph, li_ming_setup):
    """每周 2 小时:预算收紧 → 周数增加,负载仍不超预算。"""
    driver, (profile, gap_report) = graph, li_ming_setup
    report = generate_learning_path(
        driver, profile, gap_report, hours_per_week=2.0
    )
    assert report.planned_weeks > 4
    for plan in report.weeks:
        assert plan.minutes <= 120.0 + 1e-9
    assert report.total_minutes == 754
    _assert_valid_plan(report)


def test_all_ten_employees_get_valid_plans(graph, processed_dir):
    """全部 10 名模拟员工均产出合法拓扑序周计划(数据管线兼容性)。"""
    employees = json.loads(
        (processed_dir / "employees.json").read_text(encoding="utf-8")
    )["employees"]
    positions = json.loads(
        (processed_dir / "positions.json").read_text(encoding="utf-8")
    )["positions"]
    positions_by_id = {position["position_id"]: position for position in positions}

    planned = 0
    for record in employees:
        profile = build_employee_profile(record)
        gap_report = build_gap_report(
            profile, positions_by_id[profile.target_position_id]
        )
        report = generate_learning_path(driver=graph, profile=profile, gap_report=gap_report)
        assert report.employee_id == record["employee_id"]
        # 剪枝的课程必然已掌握;计划课程不重复
        pruned_ids = {item.course.course_id for item in report.pruned}
        planned_ids = {course.course_id for course in report.order}
        assert not pruned_ids & planned_ids
        if report.order:
            planned += 1
            _assert_valid_plan(report)
        json.dumps(report.to_dict(), ensure_ascii=False)
    assert planned > 0


def test_uncovered_skills_reported(graph, processed_dir):
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

    report = generate_learning_path(graph, profile, gap_report)
    assert report.order == ()
    assert report.weeks == ()
    assert [gap.skill_id for gap in report.uncovered_skills] == ["SKILL_005"]

    rendered = render_learning_path_report(report)
    assert "未覆盖缺口" in rendered
    assert "Deep Learning" in rendered


# ---------------------------------------------------------------------------
# CLI:python -m learning_path
# ---------------------------------------------------------------------------

def test_cli_default_plan(graph, processed_dir, capsys):
    """验收命令:python -m learning_path EMP_001 输出周计划。"""
    from learning_path.__main__ import main

    assert main(["EMP_001", "--data-dir", str(processed_dir)]) == 0
    out = capsys.readouterr().out
    assert "自适应学习路径:李明 → AI Engineer" in out
    assert "每周 4 小时(预算 240 分钟) · 截止 8 周" in out
    assert "第 1 周   203 / 240 分钟" in out
    assert "CRS_001" in out
    assert "已掌握,跳过(2 门" in out
    assert "4 周完成 · 可按期完成(截止 8 周)" in out


def test_cli_json_output(graph, processed_dir, capsys):
    from learning_path.__main__ import main

    assert main(
        ["EMP_001", "--data-dir", str(processed_dir), "--json"]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["employee"]["employee_id"] == "EMP_001"
    assert len(payload["topological_order"]) == 14
    assert [plan["week"] for plan in payload["weeks"]] == [1, 2, 3, 4]
    assert payload["summary"]["fits_deadline"] is True


def test_cli_hours_and_weeks_options(graph, processed_dir, capsys):
    from learning_path.__main__ import main

    assert main(
        ["EMP_001", "--data-dir", str(processed_dir),
         "--hours-per-week", "2", "--weeks", "12"]
    ) == 0
    out = capsys.readouterr().out
    assert "每周 2 小时(预算 120 分钟) · 截止 12 周" in out

    assert main(
        ["EMP_001", "--data-dir", str(processed_dir), "--weeks", "2"]
    ) == 0
    out = capsys.readouterr().out
    assert "超出截止期限 2 周" in out


def test_cli_list(graph, processed_dir, capsys):
    from learning_path.__main__ import main

    assert main(["--list", "--data-dir", str(processed_dir)]) == 0
    out = capsys.readouterr().out
    assert "EMP_001" in out
    assert "李明" in out


def test_cli_unknown_employee(graph, processed_dir, capsys):
    from learning_path.__main__ import main

    assert main(["EMP_999", "--data-dir", str(processed_dir)]) == 1
    assert "未知员工" in capsys.readouterr().err


def test_cli_invalid_options(graph, processed_dir, capsys):
    from learning_path.__main__ import main

    assert main(
        ["EMP_001", "--data-dir", str(processed_dir), "--hours-per-week", "0"]
    ) == 1
    assert "每周可学时间" in capsys.readouterr().err

    assert main(
        ["EMP_001", "--data-dir", str(processed_dir), "--weeks", "0"]
    ) == 1
    assert "截止周数" in capsys.readouterr().err
