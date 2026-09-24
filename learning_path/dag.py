"""课程 DAG 构建(大纲第八节):剪枝 + 补齐前置 + 拓扑排序——纯算法。

对应大纲第八节的管线::

    课程 DAG(前置关系)
          ↓
    删除已经掌握课程(员工已有能力)/ 已完成课程(培训记录,第十一节)
          ↓
    补齐必须前置课程
          ↓
    拓扑排序

**掌握判定**(与 :mod:`recommendation.ranking` 的难度期望一致):
课程难度代表它所构建的技能等级——beginner 构建 ≤2 级基础,
intermediate 达到 3 级熟练,advanced 冲击 4 级精通。员工在课程
所授技能上的平均等级达到该难度门槛即视为**已掌握**,可凭已有
技能跳过,而非必须学过该课(beginner 门槛 2 与
:data:`recommendation.ranking.PREREQUISITE_SATISFY_LEVEL` 一致):

    beginner       平均等级 ≥ 2
    intermediate   平均等级 ≥ 3
    advanced       平均等级 ≥ 4

**补齐前置**:保留课程的直接前置递归入图;已掌握的前置同样剪枝
(其前置更加基础,必然也已掌握,不再展开)。

**拓扑排序**:Kahn 算法;同层多个就绪课程按
「覆盖加权缺口降序 → course_id 升序」选取,保证确定性——
先学对目标岗位缺口贡献最大的课程。剩余入度非零即存在前置环,
抛出 :class:`CycleError`(数据采集阶段已校验课程前置构成 DAG,
此处兜底防御,环检测可单测)。
"""

from __future__ import annotations

import heapq
from collections.abc import Callable, Iterable, Mapping

from learning_path.models import (
    PRUNE_REASON_COMPLETED,
    PRUNE_REASON_MASTERED,
    PathCourse,
    PrunedCourse,
)
from recommendation.models import DIFFICULTIES

#: 各难度的掌握门槛:所授技能平均等级 ≥ 门槛 → 已掌握,可跳过
MASTERY_THRESHOLDS: dict[str, float] = {
    "beginner": 2.0,
    "intermediate": 3.0,
    "advanced": 4.0,
}

#: level_of:skill_id → 当前等级(0-4);由 EmployeeProfile.level_of 提供
LevelOf = Callable[[str], int]

#: priority:course → 优先级(越大越先学);由调用方提供(如缺口覆盖度)
Priority = Callable[[PathCourse], float]

#: 浮点比较容差(分钟 / 等级均为有限小数)
_EPSILON = 1e-9


def mastery_threshold(difficulty: str) -> float:
    """课程难度对应的掌握门槛(平均技能等级)。"""
    if difficulty not in MASTERY_THRESHOLDS:
        raise ValueError(
            f"课程难度必须是 {'/'.join(DIFFICULTIES)} 之一,得到 {difficulty!r}"
        )
    return MASTERY_THRESHOLDS[difficulty]


def average_skill_level(course: PathCourse, level_of: LevelOf) -> float:
    """员工在课程所授技能上的平均当前等级(掌握判定的依据)。"""
    if not course.taught_skills:
        return 0.0
    return sum(level_of(skill_id) for skill_id in course.taught_skills) / len(
        course.taught_skills
    )


def is_mastered(course: PathCourse, level_of: LevelOf) -> bool:
    """课程是否已被员工掌握(可凭已有技能跳过)。

    判定:所授技能非空,且平均等级 ≥ 该难度的掌握门槛。
    无所授技能的课程无法验证,保守视为未掌握(保留在路径中)。
    """
    if not course.taught_skills:
        return False
    return (
        average_skill_level(course, level_of) + _EPSILON
        >= mastery_threshold(course.difficulty)
    )


def select_path_courses(
    candidates: Iterable[PathCourse],
    catalog: Mapping[str, PathCourse],
    level_of: LevelOf,
    completed: Iterable[str] = (),
) -> tuple[dict[str, PathCourse], dict[str, PrunedCourse]]:
    """从候选课程出发,剪枝已掌握/已完成课程并补齐必须前置课程。

    遍历规则(对应大纲「删除已经掌握课程 → 补齐必须前置课程」,
    第十一节闭环重排追加「已完成课程同样剪枝」):

    1. 候选课程逐门判定:已完成(培训记录归档)→ 剪枝;
       已掌握(凭技能门槛)→ 剪枝;两者均不展开其前置;
    2. 保留课程的直接前置递归入图,同样按完成 / 掌握判定剪枝;
    3. 已剪枝的前置不继续展开——已掌握的前置更基础必然已掌握;
       已完成的前置能完成它说明基础已具备。

    :param candidates: 候选课程(第七节 Candidate Generation 的产出,
        每门至少教授一项缺口技能);
    :param catalog: 课程目录(候选 + 全部传递前置的完整元数据,
        见 :func:`learning_path.graph.fetch_course_closure`);
    :param level_of: 员工技能等级查询;
    :param completed: 已完成(考试通过)的课程 course_id 集合,
        重排时不再重复排课(大纲第十一节:学完 A/B 后只剩 C → D)。
    :return: ``(保留课程, 剪枝课程)``,均为 course_id → 对象;
        保留课程即学习路径 DAG 的节点集。
    :raises ValueError: 候选或前置课程不在目录中(数据不一致)。
    """
    completed_ids = frozenset(completed)
    kept: dict[str, PathCourse] = {}
    pruned: dict[str, PrunedCourse] = {}
    visited: set[str] = set()

    stack: list[PathCourse] = []
    for course in sorted(candidates, key=lambda c: c.course_id):
        if course.course_id not in catalog:
            raise ValueError(
                f"候选课程 {course.course_id} 不在课程目录中(目录缺失,无法规划)"
            )
        stack.append(course)

    while stack:
        course = stack.pop()
        course_id = course.course_id
        if course_id in visited:
            continue
        visited.add(course_id)

        if course_id in completed_ids:
            pruned[course_id] = PrunedCourse(
                course=course,
                average_level=average_skill_level(course, level_of),
                threshold=mastery_threshold(course.difficulty),
                reason=PRUNE_REASON_COMPLETED,
            )
            continue  # 已完成:不展开它的前置课程(基础已具备)

        if is_mastered(course, level_of):
            pruned[course_id] = PrunedCourse(
                course=course,
                average_level=average_skill_level(course, level_of),
                threshold=mastery_threshold(course.difficulty),
                reason=PRUNE_REASON_MASTERED,
            )
            continue  # 已掌握:不补齐它的前置课程

        kept[course_id] = course
        for prereq_id in sorted(course.prerequisites, reverse=True):
            if prereq_id in visited:
                continue
            prereq = catalog.get(prereq_id)
            if prereq is None:
                raise ValueError(
                    f"课程 {course_id} 的前置 {prereq_id} 不在课程目录中"
                    f"(前置关系不完整,无法规划)"
                )
            stack.append(prereq)

    return kept, pruned


class CycleError(ValueError):
    """课程前置关系存在环,无法拓扑排序。

    ``cycle`` 为环上的课程 id 序列(首尾相同),如 ``[A, B, A]``
    表示 A 的前置是 B、B 的前置又是 A。
    """

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        super().__init__(
            "课程前置关系存在环,无法拓扑排序:"
            + " → ".join(cycle)
            + "(前置链成环)"
        )


def _find_cycle(courses: Mapping[str, PathCourse]) -> list[str]:
    """在子图中沿前置关系找一个具体环(DFS,返回首尾相同的 id 序列)。

    只应作用于 Kahn 算法剩余的节点(必含环);理论上不会返回空。
    """
    ON_STACK, DONE = 1, 2
    state: dict[str, int] = {}
    path: list[str] = []

    def visit(course_id: str) -> list[str] | None:
        state[course_id] = ON_STACK
        path.append(course_id)
        for prereq_id in sorted(courses[course_id].prerequisites):
            if prereq_id not in courses:
                continue  # 不在子图中的前置(已剪枝)不参与环
            if state.get(prereq_id) == ON_STACK:
                return path[path.index(prereq_id):] + [prereq_id]
            if state.get(prereq_id, 0) != DONE:
                found = visit(prereq_id)
                if found:
                    return found
        state[course_id] = DONE
        path.pop()
        return None

    for course_id in sorted(courses):
        if state.get(course_id, 0) != DONE:
            found = visit(course_id)
            if found:
                return found
    return sorted(courses)  # 兜底:Kahn 剩余节点必有环,不应到达


def topological_order(
    courses: Mapping[str, PathCourse],
    priority: Priority | None = None,
) -> list[PathCourse]:
    """Kahn 拓扑排序:前置恒在前,同层就绪课程按优先级选取。

    不在节点集内的前置(已被剪枝,凭已有技能满足)不参与排序,
    其依赖课程视为立即可学。

    :param courses: 学习路径 DAG 的节点集(course_id → 课程);
    :param priority: 就绪课程的选取优先级(返回值越大越先学),
        默认全部 0(退化为 course_id 升序);推荐传入缺口覆盖度
        (:func:`learning_path.path.gap_priority`)。
    :return: 拓扑序课程列表(确定性:优先级降序 → course_id 升序)。
    :raises CycleError: 前置关系存在环。
    """
    weight = priority or (lambda course: 0.0)

    indegree: dict[str, int] = {course_id: 0 for course_id in courses}
    successors: dict[str, list[str]] = {course_id: [] for course_id in courses}
    for course in courses.values():
        for prereq_id in course.prerequisites:
            if prereq_id in courses:
                indegree[course.course_id] += 1
                successors[prereq_id].append(course.course_id)

    # 就绪堆:(-优先级, course_id) → 优先级降序,course_id 升序
    ready: list[tuple[float, str]] = [
        (-weight(courses[course_id]), course_id)
        for course_id, degree in indegree.items()
        if degree == 0
    ]
    heapq.heapify(ready)

    order_ids: list[str] = []
    while ready:
        _, course_id = heapq.heappop(ready)
        order_ids.append(course_id)
        for successor_id in sorted(successors[course_id]):
            indegree[successor_id] -= 1
            if indegree[successor_id] == 0:
                heapq.heappush(
                    ready, (-weight(courses[successor_id]), successor_id)
                )

    if len(order_ids) < len(courses):
        remaining = {
            course_id: courses[course_id]
            for course_id in courses
            if course_id not in set(order_ids)
        }
        raise CycleError(_find_cycle(remaining))

    return [courses[course_id] for course_id in order_ids]
