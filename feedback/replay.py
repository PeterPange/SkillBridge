"""培训历史回放:考试分数 → 技能等级提升 → Evidence 追加(大纲第十一节)。

本模块是反馈闭环中**唯一的新业务规则**,其余环节全部委托已有模块:

**分数映射(按考试分数映射技能等级提升)**::

    ≥ 85     提升 1 级(优秀,无需巩固)
    70 - 84  提升 1 级,但标记「需巩固」
    < 70     不提升,生成「补基础」建议(追加前置课程)

**同难度不重复涨级**:一次完成对课程所授的每项技能提升 1 级,
但同一 ``(技能, 课程难度)`` 层只涨一次——CRS_001 与 CRS_003 都是
beginner 的 Generative AI 课,完成两门只证明同一水平,不叠加涨级;
要继续提升需完成更高难度的课程。因此李明完成 CRS_001 + CRS_003 +
CRS_004(均 85 分)后,Generative AI 恰好从 0 升到 1。

**Evidence 追加(可解释:为什么涨级)**:每次完成把培训记录写入对应
技能的证据(``training_records``),并把 ``assessment_score`` 更新为
最新通过考试的分数;70-84 分的「需巩固」标记由后续 ≥ 85 分的完成消除。
回放是**事件溯源**式的:基础画像(``employees.json``)+ 培训记录 →
当前画像,不修改源数据,任何时候重放结果一致。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from data import skilllib
from feedback.models import (
    FLAG_CONSOLIDATE,
    SCORE_PASS,
    SCORE_SOLID,
    SUGGESTION_REMEDIATE,
    ProfileUpdate,
    Suggestion,
    SkillLevelChange,
    TrainingRecord,
    check_exam_score,
)
from learning_path.models import PathCourse
from profile.models import LEVEL_MAX

#: 分数档位:优秀(≥85)/ 通过需巩固(70-84)/ 未通过(<70)
OUTCOME_SOLID = "solid"
OUTCOME_CONSOLIDATE = "consolidate"
OUTCOME_FAIL = "fail"

#: 逐条记录变化的键:(record_id, course_id)——未落库的待写入记录为 (None, course_id)
RecordKey = tuple[int | None, str]


def score_outcome(score: int) -> str:
    """考试分数 → 档位(:data:`OUTCOME_SOLID` / ``CONSOLIDATE`` / ``FAIL``)。"""
    check_exam_score(score)
    if score >= SCORE_SOLID:
        return OUTCOME_SOLID
    if score >= SCORE_PASS:
        return OUTCOME_CONSOLIDATE
    return OUTCOME_FAIL


def build_suggestions(
    course: PathCourse,
    catalog: Mapping[str, PathCourse],
    passed_course_ids: Iterable[str],
) -> list[Suggestion]:
    """考试未通过时的「补基础」建议:追加尚未完成的前置课程。

    :param course: 未通过的课程;
    :param catalog: 课程目录(解析前置课程名称);
    :param passed_course_ids: 已通过的课程(已完成的前置不必再补);
    :return: 建议列表——有未完成前置 → 逐门追加;无前置或前置均已完成
        → 建议重修本课程夯实基础。
    """
    passed = frozenset(passed_course_ids)
    pending = [
        prereq_id
        for prereq_id in sorted(course.prerequisites)
        if prereq_id not in passed
    ]
    suggestions: list[Suggestion] = []
    for prereq_id in pending:
        prereq = catalog.get(prereq_id)
        name = prereq.name if prereq else prereq_id
        suggestions.append(
            Suggestion(
                kind=SUGGESTION_REMEDIATE,
                course_id=prereq_id,
                course_name=name,
                reason=(
                    f"《{course.name}》考试未通过,建议先完成前置课程"
                    f"《{name}》夯实基础,再重修《{course.name}》"
                ),
            )
        )
    if not suggestions:
        suggestions.append(
            Suggestion(
                kind=SUGGESTION_REMEDIATE,
                course_id=course.course_id,
                course_name=course.name,
                reason=(
                    f"《{course.name}》无未完成的前置课程,"
                    f"建议重修本课程夯实基础后再次参加考试"
                ),
            )
        )
    return suggestions


def _skill_name(skill_id: str) -> str:
    """技能显示名(未知技能回退 skill_id)。"""
    try:
        return skilllib.get_skill(skill_id)["name"]
    except KeyError:
        return skill_id


def _new_skill_entry() -> dict:
    """培训新获得的技能条目:等级 0 + 完整四类 Evidence。"""
    return {
        "level": 0,
        "evidence": {
            "assessment_score": 0,
            "project_experience": "无相关项目经历",
            "self_assessment": 0,
            "training_records": [],
        },
    }


def replay_history(
    base_employee: Mapping[str, object],
    records: Sequence[TrainingRecord],
    catalog: Mapping[str, PathCourse],
) -> tuple[ProfileUpdate, dict[RecordKey, list[SkillLevelChange]]]:
    """把培训历史回放到基础画像上,得到当前画像与逐条记录的变化明细。

    :param base_employee: 基础员工记录(``employees.json`` 单条);
    :param records: 培训记录(按时间升序;record_id 为 ``None`` 的
        待写入记录排在末尾,用于落库前预演本次完成的效果);
    :param catalog: 课程目录(course_id → :data:`learning_path.models.PathCourse`,
        含所授技能 / 难度 / 前置);
    :return: ``(update, record_changes)``——

        ``update`` 为 :class:`~feedback.models.ProfileUpdate`(更新后记录 +
        全部变化 + 需巩固标记 + 已通过课程);
        ``record_changes`` 为每条培训记录引发的等级变化
        (键 ``(record_id, course_id)``,保持插入顺序)。
    :raises ValueError: 培训记录引用了目录外的课程。
    """
    employee_id = str(base_employee["employee_id"])
    skills: dict[str, dict] = {}
    for item in base_employee.get("skills", []):  # type: ignore[union-attr]
        entry = dict(item)  # type: ignore[arg-type]
        entry["evidence"] = dict(entry["evidence"])
        entry["evidence"]["training_records"] = list(
            entry["evidence"]["training_records"]
        )
        skills[str(entry["skill_id"])] = entry

    consumed_tiers: set[tuple[str, str]] = set()  # (skill_id, difficulty)
    flags: dict[str, str] = {}  # skill_id → 需巩固
    passed: set[str] = set()
    all_changes: list[SkillLevelChange] = []
    record_changes: dict[RecordKey, list[SkillLevelChange]] = {}

    for record in records:
        course = catalog.get(record.course_id)
        if course is None:
            raise ValueError(
                f"员工 {employee_id} 的培训记录引用未知课程 {record.course_id}"
            )
        outcome = score_outcome(record.exam_score)
        already_passed = record.course_id in passed
        if outcome != OUTCOME_FAIL:
            passed.add(record.course_id)

        changes: list[SkillLevelChange] = []
        for skill_id in sorted(course.taught_skills):
            entry = skills.setdefault(skill_id, _new_skill_entry())
            evidence = entry["evidence"]
            old_level = int(entry["level"])

            if outcome == OUTCOME_FAIL:
                if not already_passed:  # 重考失败不重复记负面证据
                    note = f"《{course.name}》考试 {record.exam_score} 分未通过"
                    evidence["training_records"].append(note)
                    changes.append(
                        SkillLevelChange(
                            skill_id=skill_id,
                            skill_name=_skill_name(skill_id),
                            from_level=old_level,
                            to_level=old_level,
                            note=note,
                        )
                    )
                continue

            tier = (skill_id, course.difficulty)
            if tier not in consumed_tiers:
                # 通过(≥70):提升 1 级;70-84 追加「需巩固」标记
                new_level = min(old_level + 1, LEVEL_MAX)
                entry["level"] = new_level
                consumed_tiers.add(tier)
                flag = FLAG_CONSOLIDATE if outcome == OUTCOME_CONSOLIDATE else None
                if flag:
                    flags[skill_id] = flag
                mark = f",{flag}" if flag else ""
                note = (
                    f"完成《{course.name}》培训,考试 {record.exam_score} 分,"
                    f"技能 Level {old_level} → {new_level}{mark}"
                )
                evidence["training_records"].append(note)
                evidence["assessment_score"] = record.exam_score
                changes.append(
                    SkillLevelChange(
                        skill_id=skill_id,
                        skill_name=_skill_name(skill_id),
                        from_level=old_level,
                        to_level=new_level,
                        flag=flag,
                        note=note,
                    )
                )
            elif outcome == OUTCOME_SOLID and skill_id in flags:
                # 同难度已涨过级:不再提升,但优秀成绩消除「需巩固」标记
                del flags[skill_id]
                note = (
                    f"通过《{course.name}》再考核({record.exam_score} 分),"
                    f"「{FLAG_CONSOLIDATE}」标记已消除"
                )
                evidence["training_records"].append(note)
                evidence["assessment_score"] = record.exam_score
                changes.append(
                    SkillLevelChange(
                        skill_id=skill_id,
                        skill_name=_skill_name(skill_id),
                        from_level=old_level,
                        to_level=old_level,
                        note=note,
                    )
                )

        record_changes[(record.record_id, record.course_id)] = changes
        all_changes.extend(changes)

    updated_record = {
        "employee_id": base_employee["employee_id"],
        "name": base_employee["name"],
        "department": base_employee["department"],
        "current_position_id": base_employee["current_position_id"],
        "target_position_id": base_employee["target_position_id"],
        "years_of_experience": base_employee["years_of_experience"],
        "skills": [
            {
                "skill_id": skill_id,
                "level": entry["level"],
                "evidence": entry["evidence"],
            }
            for skill_id, entry in sorted(skills.items())
        ],
    }
    update = ProfileUpdate(
        employee_id=employee_id,
        base_record=dict(base_employee),  # type: ignore[arg-type]
        updated_record=updated_record,
        changes=tuple(all_changes),
        flags=dict(flags),
        passed_course_ids=frozenset(passed),
        records=tuple(records),
    )
    return update, record_changes
