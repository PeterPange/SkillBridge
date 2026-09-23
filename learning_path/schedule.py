"""周计划分配(大纲第八节):拓扑序 × 每周可学时间 → 周计划——纯算法。

分配规则(默认每周 4 小时,对应大纲「结合员工学习时间」):

1. 课程按拓扑序依次进入**当前周**;
2. 当前周剩余预算装得下整门课程 → 整门放入(**不拆分**);
3. 装不下 → 从下一周开始;课程时长超过整周预算 → **跨周续学**
   (对应大纲示例「Week 2-3: Generative AI」),每周负载仍不超过预算;
4. 恰好装满一周时,下一门课程自动从新的一周开始。

由此保证两条不变量(测试断言):

- 每周实际负载 ≤ 每周预算(时间约束);
- 全部周负载之和 = 全部课程时长(不丢课、不重复计)。
"""

from __future__ import annotations

from collections.abc import Sequence

from learning_path.models import PathCourse, WeekCourse, WeekPlan

#: 浮点比较容差(分钟)
_EPSILON = 1e-9


def allocate_weeks(
    courses: Sequence[PathCourse],
    hours_per_week: float,
) -> tuple[WeekPlan, ...]:
    """把拓扑序课程分配到每周预算内,产出周计划(确定性)。

    :param courses: 拓扑序课程(前置在前,见
        :func:`learning_path.dag.topological_order`)。
    :param hours_per_week: 每周可学习小时数,必须 > 0。
    :return: 周计划元组(第 1 周起,只含有课件的周;空输入 → 空元组)。
    :raises ValueError: ``hours_per_week`` 不为正。
    """
    if hours_per_week <= 0:
        raise ValueError(f"每周可学时间必须大于 0 小时,得到 {hours_per_week}")

    budget = hours_per_week * 60.0
    entries: list[tuple[int, WeekCourse]] = []
    week = 1
    used = 0.0  # 当前周已用预算

    for course in courses:
        duration = float(course.duration_minutes)
        if duration <= _EPSILON:
            # 零时长课程:占位可见,不消耗预算
            entries.append((week, WeekCourse(course, 0.0, False)))
            continue

        # 当前周装不下整门课程 → 移到下一周(整门课程不拆分)
        if used > _EPSILON and used + duration > budget + _EPSILON:
            week += 1
            used = 0.0

        # 超过整周预算的课程跨周续学,每周负载仍不超过预算
        remaining = duration
        first_chunk = True
        while remaining > _EPSILON:
            chunk = min(budget - used, remaining)
            entries.append((week, WeekCourse(course, chunk, not first_chunk)))
            used += chunk
            remaining -= chunk
            if remaining > _EPSILON:
                week += 1
                used = 0.0
            first_chunk = False

    if not entries:
        return ()

    by_week: dict[int, list[WeekCourse]] = {}
    for week_number, item in entries:
        by_week.setdefault(week_number, []).append(item)
    return tuple(
        WeekPlan(
            week=week_number,
            budget_minutes=budget,
            courses=tuple(items),
        )
        for week_number, items in sorted(by_week.items())
    )
