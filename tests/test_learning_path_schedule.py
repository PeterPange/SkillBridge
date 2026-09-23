"""周计划分配纯算法测试(大纲第八节,阶段 3B 验收):时间约束分配。

验收不变量:

- 每周实际负载 ≤ 每周预算(时间约束);
- 全部周负载之和 = 全部课程时长(不丢课、不重复计);
- 跨周课程(时长 > 整周预算)按周分段续学,每周仍不超预算。
"""

from __future__ import annotations

import pytest

from learning_path import allocate_weeks
from recommendation.models import CandidateCourse


def make_course(course_id: str, minutes: int) -> CandidateCourse:
    """构造合成课程(beginner,单技能,无前置)。"""
    return CandidateCourse(
        course_id=course_id,
        name=f"课程 {course_id}",
        difficulty="beginner",
        duration_minutes=minutes,
        url="",
        taught_skills=frozenset({"SKILL_001"}),
        prerequisites=frozenset(),
    )


def test_weekly_budget_respected():
    """验收:时间约束分配——每周负载恒不超过预算,总量守恒。"""
    courses = [make_course(f"C{i}", m) for i, m in enumerate([70, 80, 90, 100, 60], 1)]
    plans = allocate_weeks(courses, 2.0)  # 每周 120 分钟

    for plan in plans:
        assert plan.minutes <= plan.budget_minutes + 1e-9
        assert plan.budget_minutes == 120.0
    assert sum(plan.minutes for plan in plans) == 400  # 总量守恒
    # 课程按输入(拓扑)顺序进入周计划,不重排
    flat = [item.course.course_id for plan in plans for item in plan.courses]
    assert flat == [course.course_id for course in courses]


def test_courses_fill_week_greedily():
    """装得下就装:70 + 50 同周,90 移到下一周。"""
    courses = [make_course("A", 70), make_course("B", 50), make_course("C", 90)]
    plans = allocate_weeks(courses, 2.0)
    assert [
        [item.course.course_id for item in plan.courses] for plan in plans
    ] == [["A", "B"], ["C"]]
    assert [plan.minutes for plan in plans] == [120, 90]


def test_exact_fit_starts_new_week():
    """恰好装满一周(120 分钟):下一门课程从新的一周开始。"""
    courses = [make_course("A", 120), make_course("B", 30)]
    plans = allocate_weeks(courses, 2.0)

    assert len(plans) == 2
    assert plans[0].minutes == 120
    assert plans[0].remaining_minutes == 0
    assert [item.course.course_id for item in plans[1].courses] == ["B"]


def test_course_not_split_when_movable():
    """剩余空间装不下时整门移到下一周,不拆分课程。"""
    courses = [make_course("A", 60), make_course("B", 90), make_course("C", 60)]
    plans = allocate_weeks(courses, 2.0)
    # A(60)后剩 60,B(90)装不下 → 整门移到第 2 周;C 与 B 同周超预算 → 第 3 周
    assert [
        [item.course.course_id for item in plan.courses] for plan in plans
    ] == [["A"], ["B"], ["C"]]
    assert [plan.minutes for plan in plans] == [60, 90, 60]


def test_course_longer_than_budget_spans_weeks():
    """超周预算的课程跨周续学(大纲示例「Week 2-3: Generative AI」)。"""
    plans = allocate_weeks([make_course("BIG", 300)], 2.0)

    assert [plan.week for plan in plans] == [1, 2, 3]
    assert [plan.minutes for plan in plans] == [120, 120, 60]
    flags = [item.continued for plan in plans for item in plan.courses]
    assert flags == [False, True, True]  # 首周非续学,后续为续学
    for plan in plans:
        assert plan.minutes <= plan.budget_minutes + 1e-9


def test_long_course_starts_fresh_week():
    """当前周已有负载时,超预算课程从新周开始跨周,不挤占剩余空间。"""
    plans = allocate_weeks(
        [make_course("A", 60), make_course("BIG", 300)], 2.0
    )
    assert [plan.week for plan in plans] == [1, 2, 3, 4]
    assert [item.course.course_id for item in plans[0].courses] == ["A"]
    assert [plan.minutes for plan in plans] == [60, 120, 120, 60]


def test_fractional_hours_supported():
    """每周 1.5 小时(90 分钟):200 分钟课程跨 90 + 90 + 20。"""
    plans = allocate_weeks([make_course("A", 200)], 1.5)
    assert [plan.minutes for plan in plans] == [90, 90, 20]
    assert plans[0].budget_minutes == 90.0


def test_zero_duration_course_visible():
    """零时长课程占位可见,不消耗预算。"""
    plans = allocate_weeks([make_course("Z", 0), make_course("A", 60)], 1.0)
    assert [item.course.course_id for item in plans[0].courses] == ["Z", "A"]
    assert plans[0].minutes == 60


def test_empty_input_yields_no_weeks():
    """空课程序列 → 无周计划。"""
    assert allocate_weeks([], 4.0) == ()


def test_invalid_hours_per_week():
    """每周可学时间必须为正。"""
    with pytest.raises(ValueError, match="每周可学时间"):
        allocate_weeks([make_course("A", 60)], 0)
    with pytest.raises(ValueError, match="每周可学时间"):
        allocate_weeks([make_course("A", 60)], -1.5)


def test_allocation_deterministic():
    """相同输入重复分配,结果完全一致(周计划可复现)。"""
    courses = [make_course("A", 70), make_course("B", 90), make_course("C", 120)]
    assert allocate_weeks(courses, 2.0) == allocate_weeks(courses, 2.0)
