"""培训反馈领域模型(大纲第十一节「学习反馈与动态调整」)。

三类对象:

- **记录**::class:`TrainingRecord` 一次课程完成事件及其考试评估
  (``training_record`` + ``assessment`` 两张表的合并视图)——
  考试分数、是否通过、引发的技能等级变化(:class:`SkillLevelChange`)
  与补基础建议(:class:`Suggestion`);
- **回放**::class:`ProfileUpdate` 培训历史回放到基础画像上的结果——
  更新后的员工记录(等级 + Evidence)、全部等级变化、当前「需巩固」
  标记与已通过课程集合(闭环重算的输入);
- **闭环**::class:`LoopResult` 一次重算的产物(差距报告 + 推荐报告 +
  学习路径),:class:`CompletionResult` 一次完成登记的完整结果,
  :class:`PlanDiff` 学习路径前后对比(大纲第十一节的核心演示)。

所有模型均可 ``to_dict()`` 回写为 JSON 可序列化对象。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from learning_path.models import LearningPathReport
from profile.models import EmployeeProfile, GapReport
from recommendation.models import RecommendationReport

#: 及格线:考试 ≥ 70 视为通过,所授技能提升 1 级
SCORE_PASS = 70

#: 优秀线:考试 ≥ 85 提升且无需巩固;70-84 提升但标记「需巩固」
SCORE_SOLID = 85

#: 「需巩固」标记(70-84 分通过时挂在技能上,后续 ≥85 可消除)
FLAG_CONSOLIDATE = "需巩固"

#: 建议类型:补基础(考试未通过时追加前置课程)
SUGGESTION_REMEDIATE = "补基础"


def check_exam_score(score: int) -> int:
    """校验考试分数为 0-100 的整数,越界抛 ``ValueError``。"""
    if not isinstance(score, int) or isinstance(score, bool):
        raise ValueError(f"考试分数必须是整数,得到 {score!r}")
    if not 0 <= score <= 100:
        raise ValueError(f"考试分数必须在 0-100 之间,得到 {score}")
    return score


@dataclass(frozen=True)
class SkillLevelChange:
    """一次培训完成引发的技能等级变化(可解释:为什么涨级)。

    :param skill_id: 技能 ID;
    :param skill_name: 技能名称;
    :param from_level: 变化前等级(0-4);
    :param to_level: 变化后等级(0-4;未通过或同难度重复完成时不变);
    :param flag: 变化后的标记——:data:`FLAG_CONSOLIDATE`(需巩固)或 ``None``;
    :param note: 写入 Evidence 的培训记录文本(如
        ``完成《X》培训,考试 85 分,技能 Level 0 → 1``)。
    """

    skill_id: str
    skill_name: str
    from_level: int
    to_level: int
    flag: str | None = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """回写为 JSON 可序列化对象。"""
        return {
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "from_level": self.from_level,
            "to_level": self.to_level,
            "flag": self.flag,
            "note": self.note,
        }


@dataclass(frozen=True)
class Suggestion:
    """培训建议(大纲第十一节:考试不及格 → 追加补基础前置课程)。"""

    kind: str  # 目前仅「补基础」
    course_id: str  # 建议追加/重修的课程
    course_name: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """回写为 JSON 可序列化对象。"""
        return {
            "kind": self.kind,
            "course_id": self.course_id,
            "course_name": self.course_name,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class TrainingRecord:
    """一次课程完成事件 + 考试评估(training_record + assessment 合并视图)。

    :param record_id: ``training_record`` 主键(未落库的待写入记录为 ``None``);
    :param employee_id / course_id: 员工与课程 ID;
    :param exam_score: 考试分数(0-100);
    :param passed: 是否通过(≥ :data:`SCORE_PASS`);
    :param completed_at: 完成时间(ISO 8601 字符串);
    :param level_changes: 本次引发的技能等级变化(写入 assessment);
    :param suggestions: 本次生成的建议(如补基础,写入 assessment);
    :param source: 记录来源(CLI / 测试等)。
    """

    record_id: int | None
    employee_id: str
    course_id: str
    exam_score: int
    passed: bool
    completed_at: str
    level_changes: tuple[SkillLevelChange, ...] = ()
    suggestions: tuple[Suggestion, ...] = ()
    source: str = "cli"

    def __post_init__(self) -> None:
        check_exam_score(self.exam_score)

    def to_dict(self) -> dict[str, Any]:
        """回写为 JSON 可序列化对象。"""
        return {
            "record_id": self.record_id,
            "employee_id": self.employee_id,
            "course_id": self.course_id,
            "exam_score": self.exam_score,
            "passed": self.passed,
            "completed_at": self.completed_at,
            "level_changes": [change.to_dict() for change in self.level_changes],
            "suggestions": [item.to_dict() for item in self.suggestions],
            "source": self.source,
        }


@dataclass(frozen=True)
class ProfileUpdate:
    """培训历史回放结果:基础画像 + 培训记录 → 当前画像。

    :param employee_id: 员工 ID;
    :param base_record: 基础员工记录(``employees.json`` 原始形状);
    :param updated_record: 回放后的员工记录(等级 + Evidence 已更新,
        可直接喂给 :func:`profile.build_employee_profile`);
    :param changes: 全部培训引发的技能等级变化(按时间顺序);
    :param flags: 当前仍带「需巩固」标记的技能(skill_id → 标记);
    :param passed_course_ids: 已通过考试的课程集合(闭环重算的剪枝输入);
    :param records: 全部培训记录(按 record_id 升序)。
    """

    employee_id: str
    base_record: Mapping[str, Any]
    updated_record: Mapping[str, Any]
    changes: tuple[SkillLevelChange, ...] = ()
    flags: Mapping[str, str] = field(default_factory=dict)
    passed_course_ids: frozenset[str] = frozenset()
    records: tuple[TrainingRecord, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """回写为 JSON 可序列化对象。"""
        return {
            "employee_id": self.employee_id,
            "updated_record": dict(self.updated_record),
            "changes": [change.to_dict() for change in self.changes],
            "flags": dict(self.flags),
            "passed_course_ids": sorted(self.passed_course_ids),
            "records": [record.to_dict() for record in self.records],
        }


@dataclass(frozen=True)
class LoopResult:
    """一次闭环重算的产物:画像刷新 → Skill Gap → 推荐 → 课表。

    全部委托已有模块产出,本模块只做编排
    (大纲第十一节:update 后自动触发)。
    """

    gap_report: GapReport
    recommendations: RecommendationReport
    path: LearningPathReport

    def to_dict(self) -> dict[str, Any]:
        """回写为 JSON 可序列化对象。"""
        return {
            "gap": self.gap_report.to_dict(),
            "recommendations": self.recommendations.to_dict(),
            "path": self.path.to_dict(),
        }


@dataclass(frozen=True)
class CompletionResult:
    """一次 ``record_completion`` 的完整结果(登记 + 闭环重算)。

    :param record: 已落库的培训记录(training_record + assessment);
    :param update: 回放后的画像更新(等级 + Evidence + 已通过课程);
    :param gap_before: 登记前的差距报告(基础画像);
    :param loop_after: 登记后的闭环重算结果(差距 / 推荐 / 课表);
    :param graph_synced: 已同步到知识图谱 HAS_SKILL 关系的技能数。
    """

    record: TrainingRecord
    update: ProfileUpdate
    gap_before: GapReport
    loop_after: LoopResult
    graph_synced: int = 0

    def to_dict(self) -> dict[str, Any]:
        """回写为 JSON 可序列化对象。"""
        return {
            "record": self.record.to_dict(),
            "profile_update": {
                "changes": [change.to_dict() for change in self.update.changes],
                "flags": dict(self.update.flags),
                "passed_course_ids": sorted(self.update.passed_course_ids),
            },
            "gap_before": self.gap_before.to_dict(),
            "loop_after": self.loop_after.to_dict(),
            "graph_synced": self.graph_synced,
        }


@dataclass(frozen=True)
class FeedbackState:
    """员工培训档案的当前状态(status / plan-diff 的输入)。

    :param update: 培训历史回放结果(更新后画像 + 标记 + 已通过课程);
    :param profile: 更新后的员工画像(已通过 :func:`profile.build_employee_profile` 校验);
    :param gap_before: 基础画像的差距报告(培训前基线);
    :param gap_after: 更新画像的差距报告(当前)。
    """

    update: ProfileUpdate
    profile: EmployeeProfile
    gap_before: GapReport
    gap_after: GapReport

    @property
    def employee_id(self) -> str:
        """员工 ID。"""
        return self.profile.employee_id

    def to_dict(self) -> dict[str, Any]:
        """回写为 JSON 可序列化对象。"""
        return {
            "profile_update": self.update.to_dict(),
            "gap_before": self.gap_before.to_dict(),
            "gap_after": self.gap_after.to_dict(),
        }


@dataclass(frozen=True)
class PlanDiff:
    """学习路径前后对比(大纲第十一节核心演示:学完 A/B 后只剩 C → D)。

    :param before: 原路径(基础画像,未计入培训记录);
    :param after: 重排路径(培训后画像,已完成课程被剪枝)。
    """

    before: LearningPathReport
    after: LearningPathReport

    @property
    def removed_course_ids(self) -> list[str]:
        """原路径有、重排后不再排课的课程(已完成 / 新掌握)。"""
        after_ids = {course.course_id for course in self.after.order}
        return [
            course.course_id
            for course in self.before.order
            if course.course_id not in after_ids
        ]

    @property
    def added_course_ids(self) -> list[str]:
        """重排后新增的课程(理论上为空:等级只升不降,缺口只减不增)。"""
        before_ids = {course.course_id for course in self.before.order}
        return [
            course.course_id
            for course in self.after.order
            if course.course_id not in before_ids
        ]

    def to_dict(self) -> dict[str, Any]:
        """回写为 JSON 可序列化对象。"""
        return {
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "comparison": {
                "course_count": [self.before.course_count, self.after.course_count],
                "planned_weeks": [
                    self.before.planned_weeks, self.after.planned_weeks,
                ],
                "total_minutes": [
                    self.before.total_minutes, self.after.total_minutes,
                ],
                "removed_course_ids": self.removed_course_ids,
                "added_course_ids": self.added_course_ids,
            },
        }
