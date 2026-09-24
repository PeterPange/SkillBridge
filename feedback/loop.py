"""反馈闭环编排(大纲第十一节):登记 → 画像刷新 → Gap → 推荐 → 课表重排。

**只做编排,业务逻辑全部委托已有模块**:

.. list-table:: 步骤 → 委托模块
   :header-rows: 1

   * - 闭环步骤
     - 委托模块(大纲章节)
   * - 培训记录落库(training_record + assessment)
     - :mod:`feedback.store`(第十一节存储层)
   * - 画像刷新(等级 + Evidence 回放)
     - :mod:`feedback.replay` + :mod:`profile`(第五节)
   * - Skill Gap 重算
     - :func:`profile.build_gap_report`(第六节,纯算法)
   * - 推荐刷新(排除已完成课程)
     - :func:`recommendation.recommend_courses`(第七节,图谱 + 排序)
   * - 课表重排(已完成课程剪枝)
     - :func:`learning_path.generate_learning_path`(第八节,DAG + 周计划)
   * - 画像同步知识图谱(HAS_SKILL 等级 + Evidence)
     - Neo4j MERGE(与 :mod:`knowledge_graph.builder` 同语义)

入口(均被 CLI 与测试直接调用)::

    record_completion(...)   # 培训完成登记 + 自动触发闭环重算
    build_feedback_state(...) # 培训档案当前状态(培训历史 + 准备度)
    build_plan_diff(...)     # 学习路径前后对比(核心演示)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from neo4j import Driver

from data.collect import collect_all
from feedback.models import (
    CompletionResult,
    FeedbackState,
    LoopResult,
    PlanDiff,
    ProfileUpdate,
    Suggestion,
    TrainingRecord,
    check_exam_score,
)
from feedback.replay import build_suggestions, replay_history, score_outcome
from feedback.store import TrainingStore
from learning_path import generate_learning_path
from learning_path.models import PathCourse
from learning_path.path import DEFAULT_DEADLINE_WEEKS, DEFAULT_HOURS_PER_WEEK
from profile import build_employee_profile, build_gap_report
from profile.__main__ import (
    DEFAULT_DATA_DIR,
    DEFAULT_RAW_DIR,
    DEFAULT_SEED,
    load_data,
)
from recommendation import DEFAULT_TOP_K, recommend_courses
from skillbridge.config import get_settings

# ---------------------------------------------------------------------------
# 数据加载:岗位 / 员工(复用 profile CLI 的离线兜底)+ 课程目录
# ---------------------------------------------------------------------------


def load_course_catalog(
    data_dir: Path = DEFAULT_DATA_DIR,
    *,
    raw_dir: Path = DEFAULT_RAW_DIR,
    seed: int = DEFAULT_SEED,
) -> dict[str, PathCourse]:
    """加载课程目录(course_id → :data:`PathCourse`)。

    优先读取 ``data_dir/courses.json``;缺失时离线重建到临时目录
    (与 ``python -m profile`` 的兜底策略一致,不联网、不写仓库目录)。
    """
    courses_file = Path(data_dir) / "courses.json"
    if not courses_file.is_file():
        with tempfile.TemporaryDirectory(prefix="skillbridge-courses-") as tmp:
            out_dir = Path(tmp)
            collect_all(raw_dir=raw_dir, out_dir=out_dir, offline=True, seed=seed)
            courses_file = out_dir / "courses.json"
            courses = json.loads(courses_file.read_text(encoding="utf-8"))["courses"]
    else:
        courses = json.loads(courses_file.read_text(encoding="utf-8"))["courses"]
    return {
        course["course_id"]: PathCourse(
            course_id=course["course_id"],
            name=course["name"],
            difficulty=course["difficulty"],
            duration_minutes=int(course["duration_minutes"]),
            url=course.get("url") or "",
            taught_skills=frozenset(course["skills"]),
            prerequisites=frozenset(course["prerequisites"]),
        )
        for course in courses
    }


def _load_context(
    data_dir: Path, *, raw_dir: Path, seed: int
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, PathCourse]]:
    """加载岗位 / 员工 / 课程三类业务数据。"""
    positions, employees = load_data(Path(data_dir), raw_dir=raw_dir, seed=seed)
    positions_by_id = {position["position_id"]: position for position in positions}
    employees_by_id = {employee["employee_id"]: employee for employee in employees}
    catalog = load_course_catalog(Path(data_dir), raw_dir=raw_dir, seed=seed)
    return positions_by_id, employees_by_id, catalog


def _resolve_employee(
    employees_by_id: dict[str, dict[str, Any]], employee_id: str
) -> dict[str, Any]:
    """按 ID 取员工记录。

    :raises LookupError: 员工 ID 不存在(消息附可用 ID 列表)。
    """
    record = employees_by_id.get(employee_id)
    if record is None:
        known = ", ".join(sorted(employees_by_id))
        raise LookupError(f"未知员工 {employee_id}(可用:{known})")
    return record


def _build_gap(
    employee_record: dict[str, Any],
    positions_by_id: dict[str, dict[str, Any]],
) -> Any:
    """按员工记录构建差距报告(委托 :func:`profile.build_gap_report`)。"""
    profile = build_employee_profile(employee_record)
    target = positions_by_id.get(profile.target_position_id)
    if target is None:
        raise LookupError(
            f"员工 {profile.employee_id} 的目标岗位 "
            f"{profile.target_position_id} 不存在"
        )
    return build_gap_report(
        profile,
        target,
        current_position=positions_by_id.get(profile.current_position_id),
    )


# ---------------------------------------------------------------------------
# 闭环重算:画像刷新 → Skill Gap → 推荐刷新 → 课表重排
# ---------------------------------------------------------------------------


def sync_profile_to_graph(
    driver: Driver,
    update: ProfileUpdate,
    *,
    database: str | None = None,
) -> int:
    """把回放后的画像同步到知识图谱(HAS_SKILL 等级 + Evidence)。

    与 :mod:`knowledge_graph.builder` 的 HAS_SKILL 导入同语义
    (MERGE + SET),保证图谱中的员工画像与培训反馈一致;
    返回同步的技能关系数。
    """
    profile = build_employee_profile(dict(update.updated_record))
    rows = [
        {
            "employee_id": profile.employee_id,
            "skill_id": assessment.skill_id,
            "level": assessment.level,
            "assessment_score": assessment.evidence.assessment_score,
            "project_experience": assessment.evidence.project_experience,
            "self_assessment": assessment.evidence.self_assessment,
            "training_records": list(assessment.evidence.training_records),
        }
        for assessment in profile.skills.values()
    ]
    if not rows:
        return 0
    query = """
    UNWIND $rows AS row
    MATCH (e:Employee {employee_id: row.employee_id})
    MATCH (s:Skill {skill_id: row.skill_id})
    MERGE (e)-[r:HAS_SKILL]->(s)
    SET r.level = row.level,
        r.assessment_score = row.assessment_score,
        r.project_experience = row.project_experience,
        r.self_assessment = row.self_assessment,
        r.training_records = row.training_records
    RETURN count(r) AS synced
    """
    with driver.session(
        database=database or get_settings().neo4j_database
    ) as session:
        record = session.run(query, rows=rows).single(strict=True)
    return int(record["synced"])


def recalculate(
    driver: Driver,
    update: ProfileUpdate,
    positions_by_id: dict[str, dict[str, Any]],
    *,
    top_k: int = DEFAULT_TOP_K,
    hours_per_week: float = DEFAULT_HOURS_PER_WEEK,
    deadline_weeks: int | None = DEFAULT_DEADLINE_WEEKS,
    database: str | None = None,
) -> LoopResult:
    """闭环重算:画像刷新 → Skill Gap 重算 → 推荐刷新 → 课表重排。

    :param driver: Neo4j 驱动(推荐与路径需要图谱)。
    :param update: 培训历史回放结果(提供更新后画像与已通过课程)。
    :param positions_by_id: 岗位索引(目标岗位要求)。
    :param top_k: 推荐数量;
    :param hours_per_week / deadline_weeks: 课表时间约束(与
        ``python -m learning_path`` 默认一致:每周 4 小时、8 周截止)。
    """
    profile = build_employee_profile(dict(update.updated_record))
    gap_report = _build_gap(dict(update.updated_record), positions_by_id)
    recommendations = recommend_courses(
        driver,
        profile,
        gap_report,
        top_k=top_k,
        exclude=update.passed_course_ids,  # 已完成课程不再重复推荐
        database=database,
    )
    path = generate_learning_path(
        driver,
        profile,
        gap_report,
        hours_per_week=hours_per_week,
        deadline_weeks=deadline_weeks,
        completed=update.passed_course_ids,  # 已完成课程剪枝,不再排课
        database=database,
    )
    return LoopResult(
        gap_report=gap_report, recommendations=recommendations, path=path
    )


# ---------------------------------------------------------------------------
# 入口 1:培训完成登记(落库 + Evidence 追加 + 自动闭环重算)
# ---------------------------------------------------------------------------


def record_completion(
    driver: Driver,
    store: TrainingStore,
    employee_id: str,
    course_id: str,
    exam_score: int,
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    raw_dir: Path = DEFAULT_RAW_DIR,
    seed: int = DEFAULT_SEED,
    top_k: int = DEFAULT_TOP_K,
    hours_per_week: float = DEFAULT_HOURS_PER_WEEK,
    deadline_weeks: int | None = DEFAULT_DEADLINE_WEEKS,
    source: str = "cli",
) -> CompletionResult:
    """登记一次培训完成,并自动触发闭环重算(大纲第十一节)。

    流程:校验 → 落库(training_record + assessment)→ Evidence 追加
    (画像回放)→ 画像刷新 → Skill Gap 重算 → 推荐刷新 → 课表重排
    → 画像同步知识图谱。

    :param driver: Neo4j 驱动(闭环重算需要图谱)。
    :param store: 培训记录存储(见 :mod:`feedback.store`)。
    :param employee_id / course_id: 员工与课程 ID(如 EMP_001 / CRS_001)。
    :param exam_score: 考试分数(0-100;≥85 提升 1 级,70-84 提升 1 级
        并标记「需巩固」,<70 不提升并生成「补基础」建议)。
    :raises ValueError: 分数越界,或课程不在课程目录中。
    :raises LookupError: 员工(或其目标岗位)不存在。
    """
    check_exam_score(exam_score)
    positions_by_id, employees_by_id, catalog = _load_context(
        Path(data_dir), raw_dir=Path(raw_dir), seed=seed
    )
    employee = _resolve_employee(employees_by_id, employee_id)
    course = catalog.get(course_id)
    if course is None:
        known = ", ".join(sorted(catalog))
        raise ValueError(f"未知课程 {course_id}(可用:{known})")

    outcome = score_outcome(exam_score)
    history = store.list_records(employee_id)
    # 本次登记前已通过的课程(重考失败时不再重复生成补基础建议)
    passed_before = {
        record.course_id for record in history if record.passed
    }

    # 落库前预演:回放「历史 + 本次」,得到本次引发的等级变化
    pending = TrainingRecord(
        record_id=None,
        employee_id=employee_id,
        course_id=course_id,
        exam_score=exam_score,
        passed=outcome != "fail",
        completed_at="",
        source=source,
    )
    update_after, record_changes = replay_history(
        employee, [*history, pending], catalog
    )
    changes = record_changes.get((None, course_id), [])
    suggestions: list[Suggestion] = (
        build_suggestions(course, catalog, update_after.passed_course_ids)
        if outcome == "fail" and course_id not in passed_before
        else []
    )

    # 落库:training_record + assessment(等级变化与建议挂在 assessment 上)
    stored = store.add_record(
        employee_id,
        course_id,
        exam_score,
        passed=outcome != "fail",
        level_changes=changes,
        suggestions=suggestions,
        source=source,
    )
    # 用落库后的真实记录重放,保证后续读取与本次写入完全一致
    update, _ = replay_history(
        employee, store.list_records(employee_id), catalog
    )

    # 闭环重算:画像刷新 → Skill Gap → 推荐 → 课表
    gap_before = _build_gap(employee, positions_by_id)
    loop = recalculate(
        driver,
        update,
        positions_by_id,
        top_k=top_k,
        hours_per_week=hours_per_week,
        deadline_weeks=deadline_weeks,
    )
    synced = sync_profile_to_graph(driver, update)

    return CompletionResult(
        record=TrainingRecord(
            record_id=stored.record_id,
            employee_id=stored.employee_id,
            course_id=stored.course_id,
            exam_score=stored.exam_score,
            passed=stored.passed,
            completed_at=stored.completed_at,
            level_changes=tuple(changes),
            suggestions=tuple(suggestions),
            source=stored.source,
        ),
        update=update,
        gap_before=gap_before,
        loop_after=loop,
        graph_synced=synced,
    )


# ---------------------------------------------------------------------------
# 入口 2 / 3:培训档案状态 与 学习路径前后对比
# ---------------------------------------------------------------------------


def build_feedback_state(
    store: TrainingStore,
    employee_id: str,
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    raw_dir: Path = DEFAULT_RAW_DIR,
    seed: int = DEFAULT_SEED,
) -> FeedbackState:
    """构建员工培训档案的当前状态(status 的输入,不访问 Neo4j)。

    基础画像 + 培训记录回放 → 更新后画像;同时给出培训前基线,
    供「准备度从 29.6% 上升」类前后对比。
    """
    positions_by_id, employees_by_id, catalog = _load_context(
        Path(data_dir), raw_dir=Path(raw_dir), seed=seed
    )
    employee = _resolve_employee(employees_by_id, employee_id)
    update, _ = replay_history(employee, store.list_records(employee_id), catalog)
    return FeedbackState(
        update=update,
        profile=build_employee_profile(dict(update.updated_record)),
        gap_before=_build_gap(employee, positions_by_id),
        gap_after=_build_gap(dict(update.updated_record), positions_by_id),
    )


def build_plan_diff(
    driver: Driver,
    state: FeedbackState,
    *,
    hours_per_week: float = DEFAULT_HOURS_PER_WEEK,
    deadline_weeks: int | None = DEFAULT_DEADLINE_WEEKS,
    database: str | None = None,
) -> PlanDiff:
    """学习路径前后对比:原路径(基础画像)vs 重排路径(培训后)。

    原路径 = 尚未计入培训记录时 :func:`learning_path.generate_learning_path`
    的产出;重排路径 = 培训后画像 + 已完成课程剪枝。两条路径均由
    第八节模块生成,本函数只做编排与对比。
    """
    before = generate_learning_path(
        driver,
        build_employee_profile(dict(state.update.base_record)),
        state.gap_before,
        hours_per_week=hours_per_week,
        deadline_weeks=deadline_weeks,
        database=database,
    )
    after = generate_learning_path(
        driver,
        state.profile,
        state.gap_after,
        hours_per_week=hours_per_week,
        deadline_weeks=deadline_weeks,
        completed=state.update.passed_course_ids,
        database=database,
    )
    return PlanDiff(before=before, after=after)
