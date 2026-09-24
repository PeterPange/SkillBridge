"""学习路径管线(大纲第八节):Skill Gap → 候选 → DAG 剪枝 → 拓扑排序 → 周计划。

对应大纲第八节的整体流程::

    推荐课程(第七节候选生成,可复用)
          ↓
    删除已经掌握课程(员工已有能力)
          ↓
    补齐必须前置课程(传递闭包)
          ↓
    拓扑排序(核心缺口优先)
          ↓
    结合每周可学时间 → 周计划(默认每周 4 小时,8 周截止)

两个入口(与 :mod:`recommendation.recommend` 同构):

- :func:`generate_learning_path`  完整管线(图谱召回候选 + 前置闭包 + 规划);
- :func:`build_learning_path`     纯规划(候选池与课程目录已就绪,不访问
  数据库——剪枝 / 排序 / 分配可脱离 Neo4j 单测)。

「8 周计划」语义:大纲示例的 8 周为培训截止期限(``deadline_weeks``),
计划按每周预算贪心分配、能提前完成则提前;超出截止期限时
``fits_deadline = False``,报告显式提示而非静默截断(截断会丢失
缺口覆盖)。默认参数(每周 4 小时、截止 8 周)下,
``python -m learning_path EMP_001`` 的输出确定可复现。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence

from neo4j import Driver

from learning_path.dag import select_path_courses, topological_order
from learning_path.graph import fetch_course_closure
from learning_path.models import LearningPathReport, PathCourse
from learning_path.schedule import allocate_weeks
from profile.models import EmployeeProfile, GapReport, SkillGap
from recommendation.candidates import generate_candidates
from recommendation.models import CandidatePool

#: 默认每周可学时间(大纲第八节:每周 4 小时)
DEFAULT_HOURS_PER_WEEK = 4.0

#: 默认培训截止周数(大纲第八节示例:8 周培训计划)
DEFAULT_DEADLINE_WEEKS = 8


def gap_priority(gaps: Sequence[SkillGap]) -> Callable[[PathCourse], float]:
    """构建拓扑排序的选取优先级:课程覆盖的加权缺口(差距 × 岗位重要度)。

    覆盖核心缺口(缺口大且岗位重要)的课程在就绪集合中优先被选取,
    保证「先学对目标岗位贡献最大的课程」;同优先级按 course_id 升序,
    输出确定可复现。
    """
    weighted = {gap.skill_id: gap.weighted_gap for gap in gaps}

    def priority(course: PathCourse) -> float:
        return sum(weighted.get(skill_id, 0.0) for skill_id in course.taught_skills)

    return priority


def build_learning_path(
    pool: CandidatePool,
    catalog: Mapping[str, PathCourse],
    profile: EmployeeProfile,
    gap_report: GapReport,
    *,
    hours_per_week: float = DEFAULT_HOURS_PER_WEEK,
    deadline_weeks: int | None = DEFAULT_DEADLINE_WEEKS,
    completed: Iterable[str] = (),
) -> LearningPathReport:
    """纯规划管线:候选池 + 课程目录 → 剪枝 → 拓扑排序 → 周计划。

    不访问数据库,剪枝 / 环检测 / 时间分配可脱离 Neo4j 单测。

    :param pool: 候选池(:func:`~recommendation.candidates.generate_candidates`
        产出,候选课程为路径种子,``uncovered`` 透传到报告)。
    :param catalog: 课程目录(候选 + 全部传递前置,见
        :func:`~learning_path.graph.fetch_course_closure`)。
    :param profile: 员工画像(提供技能当前等级,掌握判定依据)。
    :param gap_report: 差距报告(缺口与岗位元数据)。
    :param hours_per_week: 每周可学习小时数(默认 4)。
    :param deadline_weeks: 培训截止周数(默认 8);``None`` 表示不设截止。
    :param completed: 已完成(考试通过)的课程 course_id 集合——
        重排时直接剪枝、不再重复排课(大纲第十一节闭环:
        学完 A/B 后只剩 C → D)。
    :raises ValueError: 时间参数非法,或候选 / 前置课程不在目录中。
    :raises CycleError: 课程前置关系存在环。
    """
    if hours_per_week <= 0:
        raise ValueError(f"每周可学时间必须大于 0 小时,得到 {hours_per_week}")
    if deadline_weeks is not None and deadline_weeks < 1:
        raise ValueError(f"截止周数必须大于等于 1,得到 {deadline_weeks}")

    kept, pruned = select_path_courses(
        pool.candidates, catalog, profile.level_of, completed=completed
    )
    order = topological_order(kept, gap_priority(gap_report.gaps))
    weeks = allocate_weeks(order, hours_per_week)

    covered = {
        course.course_id: tuple(
            gap for gap in gap_report.gaps if gap.skill_id in course.taught_skills
        )
        for course in order
    }

    return LearningPathReport(
        employee_id=gap_report.employee_id,
        employee_name=gap_report.employee_name,
        target_position_id=gap_report.target_position_id,
        target_position_name=gap_report.target_position_name,
        hours_per_week=hours_per_week,
        deadline_weeks=deadline_weeks,
        order=tuple(order),
        weeks=weeks,
        pruned=tuple(pruned[course_id] for course_id in sorted(pruned)),
        covered_gaps=covered,
        uncovered_skills=pool.uncovered,
    )


def generate_learning_path(
    driver: Driver,
    profile: EmployeeProfile,
    gap_report: GapReport,
    *,
    hours_per_week: float = DEFAULT_HOURS_PER_WEEK,
    deadline_weeks: int | None = DEFAULT_DEADLINE_WEEKS,
    completed: Iterable[str] = (),
    database: str | None = None,
) -> LearningPathReport:
    """完整学习路径管线:图谱召回候选 → 前置闭包 → 剪枝 → 排序 → 周计划。

    :param driver: Neo4j 驱动(需已导入课程图谱,``make graph``)。
    :param profile: 员工画像。
    :param gap_report: 差距报告(大纲第六节输出,本模块的输入)。
    :param hours_per_week: 每周可学习小时数(默认 4)。
    :param deadline_weeks: 培训截止周数(默认 8);``None`` 表示不设截止。
    :param completed: 已完成(考试通过)的课程 course_id 集合——
        重排时直接剪枝(大纲第十一节闭环重排)。
    :param database: Neo4j 数据库(默认取 ``NEO4J_DATABASE`` 配置)。
    """
    # 复用第七节 Candidate Generation:按缺口技能沿 TEACHES 关系召回候选课程
    pool = generate_candidates(driver, gap_report.gaps, database=database)
    catalog = fetch_course_closure(
        driver,
        [course.course_id for course in pool.candidates],
        database=database,
    )
    return build_learning_path(
        pool,
        catalog,
        profile,
        gap_report,
        hours_per_week=hours_per_week,
        deadline_weeks=deadline_weeks,
        completed=completed,
    )
