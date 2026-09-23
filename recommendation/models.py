"""推荐领域模型(大纲第七节)。

三类对象:

- **候选**::class:`CandidateCourse` —— 按 Skill Gap 从图谱 ``TEACHES``
  关系召回的课程(含所授技能与直接前置);:class:`CandidatePool` 为一次
  召回的完整结果(候选 + 非候选前置课程上下文 + 无课程覆盖的缺口技能);
- **打分**::class:`ScoringWeights` 五因子权重(Gap 覆盖度 / 技能重要性 /
  难度匹配 / 前置满足 / 时间成本),:class:`ScoreBreakdown` 为单门课程的
  分项得分与加权总分;
- **输出**::class:`Recommendation` 单条推荐(排名 + 得分 + 分项 +
  覆盖缺口 + 前置状态 + 推荐理由),:class:`RecommendationReport`
  Top-K 结构化报告,供 LLM 解释(大纲第九节「为什么推荐」)与
  Agent 工具(大纲第十节)消费。

所有模型均可 ``to_dict()`` 回写为 JSON 可序列化对象。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from profile.models import GapReport, SkillGap

#: 课程难度等级(与 data/schemas.py 课程 Schema 的枚举一致)
DIFFICULTIES = ("beginner", "intermediate", "advanced")


def check_difficulty(difficulty: str) -> str:
    """校验课程难度枚举,非法值抛 ``ValueError``。"""
    if difficulty not in DIFFICULTIES:
        raise ValueError(
            f"课程难度必须是 {'/'.join(DIFFICULTIES)} 之一,得到 {difficulty!r}"
        )
    return difficulty


@dataclass(frozen=True)
class CandidateCourse:
    """候选课程:图谱 ``TEACHES`` 关系召回,携带打分所需元数据。"""

    course_id: str
    name: str
    difficulty: str  # beginner / intermediate / advanced
    duration_minutes: int
    url: str
    taught_skills: frozenset[str]  # 所授技能 skill_id(TEACHES 关系)
    prerequisites: frozenset[str]  # 直接前置课程 course_id(PREREQUISITE 关系)

    def __post_init__(self) -> None:
        check_difficulty(self.difficulty)
        if not self.course_id or not self.name:
            raise ValueError("候选课程必须包含 course_id 与 name")
        if self.duration_minutes < 0:
            raise ValueError(f"学习时长不能为负,得到 {self.duration_minutes}")

    def to_dict(self) -> dict[str, Any]:
        """回写为 JSON 可序列化对象(技能与前置按 id 排序,确定性输出)。"""
        return {
            "course_id": self.course_id,
            "name": self.name,
            "difficulty": self.difficulty,
            "duration_minutes": self.duration_minutes,
            "url": self.url,
            "taught_skills": sorted(self.taught_skills),
            "prerequisites": sorted(self.prerequisites),
        }


@dataclass(frozen=True)
class CourseContext:
    """非候选前置课程的上下文:名称 + 所授技能(用于前置满足判定)。"""

    name: str
    skills: frozenset[str]


@dataclass(frozen=True)
class CandidatePool:
    """一次候选生成的完整结果(大纲第七节 Candidate Generation)。

    :param candidates: 候选课程(按 course_id 升序),每门至少教授一项缺口技能;
    :param prerequisite_context: 仅作为前置出现、自身不是候选的课程上下文;
    :param uncovered: 有缺口但图谱中无任何课程教授的技能(推荐报告需显式提示)。
    """

    candidates: tuple[CandidateCourse, ...] = ()
    prerequisite_context: Mapping[str, CourseContext] = field(
        default_factory=dict
    )
    uncovered: tuple[SkillGap, ...] = ()

    def taught_skills_of(self, course_id: str) -> frozenset[str]:
        """课程所授技能:候选课程取自身,否则查前置上下文;未知返回空集。"""
        for course in self.candidates:
            if course.course_id == course_id:
                return course.taught_skills
        context = self.prerequisite_context.get(course_id)
        return context.skills if context is not None else frozenset()

    def name_of(self, course_id: str) -> str | None:
        """课程名称:候选课程取自身,否则查前置上下文;未知返回 ``None``。"""
        for course in self.candidates:
            if course.course_id == course_id:
                return course.name
        context = self.prerequisite_context.get(course_id)
        return context.name if context is not None else None


@dataclass(frozen=True)
class ScoringWeights:
    """五因子加权权重(大纲第七节 Course Ranking),和恒为 1。

    - ``gap_coverage``      Gap 覆盖度:课程覆盖的加权缺口占全部加权缺口比例;
    - ``importance``        技能重要性:覆盖缺口技能的最高岗位重要度;
    - ``difficulty_match``  难度匹配:课程难度与员工在课程技能上的基础匹配度;
    - ``prerequisite``      前置满足:直接前置课程按员工已有技能判定的满足率;
    - ``time_cost``         时间成本:学习时长越短得分越高。
    """

    gap_coverage: float = 0.30
    importance: float = 0.25
    difficulty_match: float = 0.20
    prerequisite: float = 0.15
    time_cost: float = 0.10

    def __post_init__(self) -> None:
        values = (
            self.gap_coverage, self.importance, self.difficulty_match,
            self.prerequisite, self.time_cost,
        )
        if any(value < 0 for value in values):
            raise ValueError(f"权重不能为负,得到 {values}")
        if abs(sum(values) - 1.0) > 1e-6:
            raise ValueError(f"权重之和必须为 1,得到 {sum(values):.6f}")

    def to_dict(self) -> dict[str, float]:
        return {
            "gap_coverage": self.gap_coverage,
            "importance": self.importance,
            "difficulty_match": self.difficulty_match,
            "prerequisite": self.prerequisite,
            "time_cost": self.time_cost,
        }


@dataclass(frozen=True)
class ScoreBreakdown:
    """单门课程的五因子分项得分与加权总分(全部 0-1)。"""

    gap_coverage: float
    importance: float
    difficulty_match: float
    prerequisite: float
    time_cost: float
    total: float

    def to_dict(self) -> dict[str, float]:
        return {
            "gap_coverage": self.gap_coverage,
            "importance": self.importance,
            "difficulty_match": self.difficulty_match,
            "prerequisite": self.prerequisite,
            "time_cost": self.time_cost,
            "total": self.total,
        }


@dataclass(frozen=True)
class CourseRef:
    """课程引用(course_id + 名称),用于前置状态展示。"""

    course_id: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {"course_id": self.course_id, "name": self.name}


@dataclass(frozen=True)
class Recommendation:
    """单条推荐:排名 + 得分 + 分项 + 覆盖缺口 + 前置状态 + 推荐理由。

    ``reasons`` 为面向 LLM 的结构化理由(大纲第七节「LLM 解释为什么推荐」
    的输入),每条对应一个评分因子,可直接嵌入 Agent 回复。
    """

    rank: int
    course: CandidateCourse
    score: float
    breakdown: ScoreBreakdown
    covered_gaps: tuple[SkillGap, ...]
    satisfied_prerequisites: tuple[CourseRef, ...]
    missing_prerequisites: tuple[CourseRef, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "score": self.score,
            "course": self.course.to_dict(),
            "score_breakdown": self.breakdown.to_dict(),
            "covered_gaps": [gap.to_dict() for gap in self.covered_gaps],
            "prerequisites": {
                "satisfied": [ref.to_dict() for ref in self.satisfied_prerequisites],
                "missing": [ref.to_dict() for ref in self.missing_prerequisites],
            },
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class RecommendationReport:
    """Top-K 推荐报告(大纲第七节输出)。"""

    employee_id: str
    employee_name: str
    target_position_id: str
    target_position_name: str
    top_k: int
    weights: ScoringWeights
    recommendations: tuple[Recommendation, ...]
    candidate_count: int
    uncovered_skills: tuple[SkillGap, ...]

    def to_dict(self) -> dict[str, Any]:
        """结构化输出(JSON 可序列化,供 LLM 解释与 Agent 工具消费)。"""
        return {
            "employee": {
                "employee_id": self.employee_id,
                "name": self.employee_name,
            },
            "target_position": {
                "position_id": self.target_position_id,
                "name": self.target_position_name,
            },
            "top_k": self.top_k,
            "weights": self.weights.to_dict(),
            "candidate_count": self.candidate_count,
            "recommendations": [rec.to_dict() for rec in self.recommendations],
            "uncovered_skills": [gap.to_dict() for gap in self.uncovered_skills],
        }


def report_metadata(gap_report: GapReport) -> dict[str, str]:
    """从差距报告提取推荐报告所需的员工与岗位元数据。"""
    return {
        "employee_id": gap_report.employee_id,
        "employee_name": gap_report.employee_name,
        "target_position_id": gap_report.target_position_id,
        "target_position_name": gap_report.target_position_name,
    }
