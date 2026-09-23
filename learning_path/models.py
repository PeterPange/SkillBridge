"""学习路径领域模型(大纲第八节)。

四类对象:

- **课程**::data:`PathCourse` —— 直接复用
  :class:`recommendation.models.CandidateCourse`(course_id / 名称 / 难度 /
  时长 / URL / 所授技能 / 直接前置),已含 DAG 构建与周计划分配所需的
  全部元数据;候选课程与前置课程使用同一对象,避免重复建模;
- **剪枝**::class:`PrunedCourse` —— 已掌握而被跳过的课程(凭已有技能
  可免修),携带判定依据(所授技能平均等级与掌握门槛);
- **周计划**::class:`WeekCourse` 单周课程条目(支持跨周续学),
  :class:`WeekPlan` 单周计划(周号 + 预算 + 条目 + 负载);
- **报告**::class:`LearningPathReport` 结构化学习路径(拓扑序 + 周计划 +
  剪枝明细 + 无课程覆盖的缺口),供 CLI 渲染、Agent 工具
  (大纲第十节)与 LLM 解释消费。

所有模型均可 ``to_dict()`` 回写为 JSON 可序列化对象。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from profile.models import SkillGap
from recommendation.models import CandidateCourse

#: 路径中的课程对象:复用候选课程模型(含 DAG 与周计划所需全部元数据)。
#: 候选课程(按缺口召回)与补齐的前置课程(传递闭包)统一用该对象表示。
PathCourse = CandidateCourse


@dataclass(frozen=True)
class PrunedCourse:
    """已掌握而被剪枝的课程:员工凭已有技能可免修。

    :param course: 被剪枝的课程;
    :param average_level: 员工在课程所授技能上的平均等级(0-4);
    :param threshold: 该难度的掌握门槛(见 :data:`learning_path.dag.MASTERY_THRESHOLDS`)。
    """

    course: PathCourse
    average_level: float
    threshold: float

    def to_dict(self) -> dict[str, Any]:
        """回写为 JSON 可序列化对象。"""
        return {
            "course_id": self.course.course_id,
            "name": self.course.name,
            "difficulty": self.course.difficulty,
            "duration_minutes": self.course.duration_minutes,
            "average_level": round(self.average_level, 2),
            "threshold": self.threshold,
        }


@dataclass(frozen=True)
class WeekCourse:
    """单周课程条目。

    :param course: 课程;
    :param minutes: 本周分配的学习分钟数(跨周课程为该周的分段时长);
    :param continued: 是否为跨周课程的续学部分(首周为 ``False``)。
    """

    course: PathCourse
    minutes: float
    continued: bool = False

    def to_dict(self) -> dict[str, Any]:
        """回写为 JSON 可序列化对象。"""
        return {
            "course_id": self.course.course_id,
            "name": self.course.name,
            "difficulty": self.course.difficulty,
            "duration_minutes": self.course.duration_minutes,
            "url": self.course.url,
            "minutes": self.minutes,
            "continued": self.continued,
        }


@dataclass(frozen=True)
class WeekPlan:
    """单周计划:周号 + 每周预算 + 课程条目。

    ``minutes``(实际负载)恒 ≤ ``budget_minutes``(每周可学时间),
    由 :func:`learning_path.schedule.allocate_weeks` 保证。
    """

    week: int
    budget_minutes: float
    courses: tuple[WeekCourse, ...]

    @property
    def minutes(self) -> float:
        """本周学习负载(分钟)。"""
        return sum(item.minutes for item in self.courses)

    @property
    def remaining_minutes(self) -> float:
        """本周剩余预算(分钟)。"""
        return self.budget_minutes - self.minutes

    def to_dict(self) -> dict[str, Any]:
        """回写为 JSON 可序列化对象。"""
        return {
            "week": self.week,
            "budget_minutes": self.budget_minutes,
            "minutes": self.minutes,
            "remaining_minutes": self.remaining_minutes,
            "courses": [item.to_dict() for item in self.courses],
        }


@dataclass(frozen=True)
class LearningPathReport:
    """结构化学习路径报告(大纲第八节输出)。

    :param order: 拓扑序课程(合法学习顺序,前置恒在前);
    :param weeks: 周计划(第 1 周起,只含有课件的周);
    :param pruned: 已掌握被剪枝的课程(按 course_id 升序);
    :param covered_gaps: course_id → 该课程覆盖的缺口技能
        (供渲染与 LLM 解释「为什么排在这一周」);
    :param uncovered_skills: 有缺口但图谱中无任何课程教授的技能
        (从候选池透传,显式提示而非静默丢弃)。
    """

    employee_id: str
    employee_name: str
    target_position_id: str
    target_position_name: str
    hours_per_week: float
    deadline_weeks: int | None
    order: tuple[PathCourse, ...]
    weeks: tuple[WeekPlan, ...]
    pruned: tuple[PrunedCourse, ...]
    covered_gaps: Mapping[str, tuple[SkillGap, ...]] = field(default_factory=dict)
    uncovered_skills: tuple[SkillGap, ...] = ()

    @property
    def course_count(self) -> int:
        """计划课程数。"""
        return len(self.order)

    @property
    def planned_weeks(self) -> int:
        """计划周数(有课件的周数)。"""
        return len(self.weeks)

    @property
    def total_minutes(self) -> float:
        """计划总学习时长(分钟)。"""
        return sum(item.minutes for plan in self.weeks for item in plan.courses)

    @property
    def total_hours(self) -> float:
        """计划总学习时长(小时)。"""
        return self.total_minutes / 60.0

    @property
    def fits_deadline(self) -> bool:
        """是否可在截止周数内完成(无截止期限时恒为 ``True``)。"""
        return self.deadline_weeks is None or self.planned_weeks <= self.deadline_weeks

    def to_dict(self) -> dict[str, Any]:
        """结构化输出(JSON 可序列化,供 Agent 工具与 LLM 解释消费)。"""
        return {
            "employee": {
                "employee_id": self.employee_id,
                "name": self.employee_name,
            },
            "target_position": {
                "position_id": self.target_position_id,
                "name": self.target_position_name,
            },
            "constraints": {
                "hours_per_week": self.hours_per_week,
                "weekly_budget_minutes": self.hours_per_week * 60.0,
                "deadline_weeks": self.deadline_weeks,
            },
            "topological_order": [course.course_id for course in self.order],
            "weeks": [plan.to_dict() for plan in self.weeks],
            "covered_gaps": {
                course_id: [
                    {
                        "skill_id": gap.skill_id,
                        "skill_name": gap.skill_name,
                        "gap": gap.gap,
                        "current_level": gap.current_level,
                        "required_level": gap.required_level,
                    }
                    for gap in covered
                ]
                for course_id, covered in sorted(self.covered_gaps.items())
                if covered
            },
            "pruned": [item.to_dict() for item in self.pruned],
            "uncovered_skills": [gap.to_dict() for gap in self.uncovered_skills],
            "summary": {
                "course_count": self.course_count,
                "planned_weeks": self.planned_weeks,
                "total_minutes": self.total_minutes,
                "total_hours": round(self.total_hours, 2),
                "pruned_count": len(self.pruned),
                "fits_deadline": self.fits_deadline,
            },
        }
