"""学习路径纯管线测试:build_learning_path(不访问数据库)。

用合成课程目录 + 大纲示例员工(李明画像)验证完整规划链路:
候选 → 剪枝 → 补齐前置 → 拓扑排序 → 周计划 → 截止期限校验。
剪枝 / 环检测 / 时间分配的算法细节见
test_learning_path_dag.py 与 test_learning_path_schedule.py。
"""

from __future__ import annotations

import json

import pytest

from conftest import outline_skill
from learning_path import (
    DEFAULT_DEADLINE_WEEKS,
    DEFAULT_HOURS_PER_WEEK,
    build_learning_path,
    render_learning_path_report,
)
from profile import build_employee_profile, build_gap_report
from recommendation.models import CandidateCourse, CandidatePool


def make_course(
    course_id: str,
    *,
    name: str,
    difficulty: str = "beginner",
    minutes: int = 60,
    skills: tuple[str, ...] = (),
    prerequisites: tuple[str, ...] = (),
) -> CandidateCourse:
    return CandidateCourse(
        course_id=course_id,
        name=name,
        difficulty=difficulty,
        duration_minutes=minutes,
        url=f"https://example.test/{course_id}",
        taught_skills=frozenset(skills),
        prerequisites=frozenset(prerequisites),
    )


@pytest.fixture()
def employee_record() -> dict:
    """李明式员工:Python 2 / Docker 2(达标)/ GenAI、AI Agent 为 0。"""
    return {
        "employee_id": "EMP_001",
        "name": "李明",
        "department": "研发中心",
        "current_position_id": "POS_001",
        "target_position_id": "POS_005",
        "years_of_experience": 3,
        "skills": [
            outline_skill("SKILL_001", 2),  # Python 2 → beginner 课已掌握
            outline_skill("SKILL_004", 1),  # Machine Learning
            outline_skill("SKILL_006", 0),  # Generative AI
            outline_skill("SKILL_009", 0),  # AI Agent
            outline_skill("SKILL_011", 2),  # Docker 已达标
            outline_skill("SKILL_015", 1),  # Monitoring(目录中无课程覆盖)
        ],
    }


@pytest.fixture()
def setup(outline_position, employee_record):
    """画像 + 差距报告 + 合成候选池与课程目录。"""
    profile = build_employee_profile(employee_record)
    gap_report = build_gap_report(profile, outline_position)

    # 课程目录:AI 链 A→B→C(前置 D 已掌握),Python 链 E→F
    a = make_course("A", name="AI 基础", minutes=60,
                    skills=("SKILL_004", "SKILL_006"))
    b = make_course("B", name="生成式 AI", minutes=90,
                    skills=("SKILL_006",), prerequisites=("A",))
    c = make_course("C", name="AI Agent 开发", difficulty="intermediate",
                    minutes=120, skills=("SKILL_009",), prerequisites=("B", "D"))
    d = make_course("D", name="Docker 容器", minutes=30, skills=("SKILL_011",))
    e = make_course("E", name="Python 入门", minutes=30, skills=("SKILL_001",))
    f = make_course("F", name="Python 数据分析", difficulty="intermediate",
                    minutes=60, skills=("SKILL_001",), prerequisites=("E",))
    catalog = {course.course_id: course for course in (a, b, c, d, e, f)}

    # 候选池:教授缺口技能的课程(D 教授的 Docker 已达标,不是候选)
    pool = CandidatePool(candidates=(a, b, c, e, f))
    return profile, gap_report, pool, catalog


def test_build_learning_path_plan(setup):
    """端到端纯规划:剪枝 → 补齐前置 → 拓扑序 → 周计划。"""
    profile, gap_report, pool, catalog = setup
    report = build_learning_path(pool, catalog, profile, gap_report)

    # 剪枝:Python/Docker 的 beginner 课已掌握;补齐前置:B、A 随 C 入图
    assert [item.course.course_id for item in report.pruned] == ["D", "E"]
    # 拓扑序:核心缺口优先(GenAI 链 A→B→C 先于 Python 的 F)
    assert [course.course_id for course in report.order] == ["A", "B", "C", "F"]
    # 周计划:每周 4 小时(240 分钟),A+B 同周,C+F 移到第 2 周
    assert [
        [item.course.course_id for item in plan.courses] for plan in report.weeks
    ] == [["A", "B"], ["C", "F"]]
    assert [plan.minutes for plan in report.weeks] == [150, 180]
    assert report.course_count == 4
    assert report.total_minutes == 330
    assert report.planned_weeks == 2
    assert report.fits_deadline  # 2 周 ≤ 默认 8 周截止


def test_build_learning_path_defaults(setup):
    """默认参数:每周 4 小时、截止 8 周(大纲第八节)。"""
    profile, gap_report, pool, catalog = setup
    report = build_learning_path(pool, catalog, profile, gap_report)
    assert report.hours_per_week == DEFAULT_HOURS_PER_WEEK == 4.0
    assert report.deadline_weeks == DEFAULT_DEADLINE_WEEKS == 8


def test_covered_gaps_annotated(setup):
    """每门课程标注覆盖的缺口(供渲染与 LLM 解释)。"""
    profile, gap_report, pool, catalog = setup
    report = build_learning_path(pool, catalog, profile, gap_report)

    # 差距报告顺序(差距降序):GenAI → AI Agent → Python → ML → Monitoring
    assert [gap.skill_name for gap in report.covered_gaps["A"]] == [
        "Generative AI", "Machine Learning",
    ]
    assert [gap.skill_name for gap in report.covered_gaps["C"]] == ["AI Agent"]
    assert [gap.skill_name for gap in report.covered_gaps["F"]] == ["Python"]


def test_uncovered_skills_carried_through(setup):
    """无课程覆盖的缺口(Monitoring)透传到报告,显式提示而非静默丢弃。"""
    profile, gap_report, pool, catalog = setup
    monitoring = next(
        gap for gap in gap_report.gaps if gap.skill_id == "SKILL_015"
    )
    pool = CandidatePool(
        candidates=pool.candidates, uncovered=(monitoring,)
    )
    report = build_learning_path(pool, catalog, profile, gap_report)

    assert [gap.skill_id for gap in report.uncovered_skills] == ["SKILL_015"]
    payload = report.to_dict()
    assert payload["uncovered_skills"][0]["skill_id"] == "SKILL_015"
    rendered = render_learning_path_report(report)
    assert "未覆盖缺口" in rendered
    assert "Monitoring" in rendered


def test_deadline_exceeded_flagged(setup):
    """超出截止期限:显式标记,不静默截断(截断会丢失缺口覆盖)。"""
    profile, gap_report, pool, catalog = setup
    report = build_learning_path(
        pool, catalog, profile, gap_report, deadline_weeks=1
    )
    assert report.planned_weeks == 2
    assert not report.fits_deadline
    rendered = render_learning_path_report(report)
    assert "超出截止期限 1 周" in rendered

    # 放宽截止期限后按期完成
    relaxed = build_learning_path(
        pool, catalog, profile, gap_report, deadline_weeks=2
    )
    assert relaxed.fits_deadline


def test_no_deadline_always_fits(setup):
    """deadline_weeks=None:不设截止,恒视为可完成。"""
    profile, gap_report, pool, catalog = setup
    report = build_learning_path(
        pool, catalog, profile, gap_report, deadline_weeks=None
    )
    assert report.deadline_weeks is None
    assert report.fits_deadline
    rendered = render_learning_path_report(report)
    assert "截止" not in rendered


def test_hours_per_week_changes_packing(setup):
    """每周 1 小时:预算收紧 → 周数增加,跨周续学,负载仍不超预算。"""
    profile, gap_report, pool, catalog = setup
    report = build_learning_path(
        pool, catalog, profile, gap_report, hours_per_week=1.0
    )
    assert report.hours_per_week == 1.0
    assert report.planned_weeks == 6  # 60+90(跨2周)+120(跨2周)+60
    for plan in report.weeks:
        assert plan.minutes <= 60.0 + 1e-9
    # 跨周课程标记续学
    continued = [
        item.continued for plan in report.weeks for item in plan.courses
    ]
    assert continued.count(True) == 2  # B 与 C 各跨一周
    assert report.total_minutes == 330


def test_empty_pool_yields_empty_path(outline_position, employee_record):
    """无缺口 → 空候选池 → 空路径(合法输出,而非报错)。"""
    profile = build_employee_profile(employee_record)
    gap_report = build_gap_report(profile, outline_position)
    report = build_learning_path(
        CandidatePool(), {}, profile, gap_report
    )
    assert report.order == ()
    assert report.weeks == ()
    assert report.course_count == 0
    assert report.fits_deadline
    rendered = render_learning_path_report(report)
    assert "无需规划学习路径" in rendered


def test_report_serializable_and_deterministic(setup):
    """报告 JSON 可序列化(供 Agent / LLM 消费),重复规划结果一致。"""
    profile, gap_report, pool, catalog = setup
    report = build_learning_path(pool, catalog, profile, gap_report)
    again = build_learning_path(pool, catalog, profile, gap_report)

    assert report == again
    payload = report.to_dict()
    json.dumps(payload, ensure_ascii=False)
    assert payload["employee"]["name"] == "李明"
    assert payload["target_position"]["position_id"] == "POS_005"
    assert payload["constraints"] == {
        "hours_per_week": 4.0,
        "weekly_budget_minutes": 240.0,
        "deadline_weeks": 8,
    }
    assert payload["topological_order"] == ["A", "B", "C", "F"]
    assert payload["summary"]["fits_deadline"] is True
    # 周计划与覆盖缺口标注
    assert payload["weeks"][0]["courses"][0]["course_id"] == "A"
    assert payload["covered_gaps"]["A"][0]["skill_name"] == "Generative AI"


def test_invalid_time_parameters(setup):
    """非法时间参数:每周时间非正 / 截止周数小于 1。"""
    profile, gap_report, pool, catalog = setup
    with pytest.raises(ValueError, match="每周可学时间"):
        build_learning_path(pool, catalog, profile, gap_report, hours_per_week=0)
    with pytest.raises(ValueError, match="截止周数"):
        build_learning_path(pool, catalog, profile, gap_report, deadline_weeks=0)
