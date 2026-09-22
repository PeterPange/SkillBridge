"""员工画像领域模型(大纲第五节「员工能力画像」)。

Knowledge Graph 是公共知识,Employee Profile 是个人状态。本模块定义
画像的核心对象:技能等级(0-4)不再是裸数字,而是携带四类 Evidence
的可解释评估——

- ``assessment_score``   技能考试(0-100)
- ``project_experience`` 项目经历
- ``self_assessment``    员工自评(0-4)
- ``training_records``   培训记录

系统因此可以回答大纲第五节的问题:「为什么认为你 Python 是 Level 2?」
(文本渲染见 :func:`profile.report.render_evidence_explanation`)。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

#: 技能等级范围:0 无基础 / 1 入门 / 2 基础 / 3 熟练 / 4 精通
LEVEL_MIN = 0
LEVEL_MAX = 4

#: Evidence 四类字段(与 ``data/schemas.py`` 员工 Schema 保持一致)
EVIDENCE_FIELDS = (
    "assessment_score",
    "project_experience",
    "self_assessment",
    "training_records",
)


def check_level(level: int, what: str = "技能等级") -> int:
    """校验技能等级为 0-4 的整数,越界抛 ``ValueError``。"""
    if not isinstance(level, int) or isinstance(level, bool):
        raise ValueError(f"{what}必须是整数,得到 {level!r}")
    if not LEVEL_MIN <= level <= LEVEL_MAX:
        raise ValueError(f"{what}必须在 {LEVEL_MIN}-{LEVEL_MAX} 之间,得到 {level}")
    return level


@dataclass(frozen=True)
class SkillEvidence:
    """技能等级证据:技能考试 / 项目经历 / 员工自评 / 培训记录。"""

    assessment_score: int
    project_experience: str
    self_assessment: int
    training_records: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.assessment_score, int) or isinstance(
            self.assessment_score, bool
        ):
            raise ValueError(f"技能考试分数必须是整数,得到 {self.assessment_score!r}")
        if not 0 <= self.assessment_score <= 100:
            raise ValueError(f"技能考试分数必须在 0-100 之间,得到 {self.assessment_score}")
        check_level(self.self_assessment, "员工自评")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SkillEvidence":
        """从 ``employees.json`` 的 evidence 对象构建(校验字段完整性)。"""
        missing = [field for field in EVIDENCE_FIELDS if field not in data]
        if missing:
            raise ValueError(f"Evidence 缺少字段: {', '.join(missing)}")
        return cls(
            assessment_score=data["assessment_score"],
            project_experience=data["project_experience"],
            self_assessment=data["self_assessment"],
            training_records=tuple(data["training_records"]),
        )

    def to_dict(self) -> dict[str, Any]:
        """回写为 JSON 可序列化对象。"""
        return {
            "assessment_score": self.assessment_score,
            "project_experience": self.project_experience,
            "self_assessment": self.self_assessment,
            "training_records": list(self.training_records),
        }


@dataclass(frozen=True)
class SkillAssessment:
    """员工单项技能评估:等级 + 证据。"""

    skill_id: str
    level: int
    evidence: SkillEvidence

    def __post_init__(self) -> None:
        check_level(self.level)


@dataclass(frozen=True)
class EmployeeProfile:
    """员工画像:基本信息 + 当前/目标岗位 + 技能列表(等级 + Evidence)。"""

    employee_id: str
    name: str
    department: str
    current_position_id: str
    target_position_id: str
    years_of_experience: int
    skills: Mapping[str, SkillAssessment]

    def level_of(self, skill_id: str) -> int:
        """当前技能等级;未登记技能视为 0(大纲第六节:GenAI / AI Agent = 0)。"""
        assessment = self.skills.get(skill_id)
        return assessment.level if assessment is not None else LEVEL_MIN

    def has_skill(self, skill_id: str) -> bool:
        """是否登记了该技能(即使等级为 0)。"""
        return skill_id in self.skills

    def assessment_of(self, skill_id: str) -> SkillAssessment | None:
        """取单项技能评估;未登记返回 ``None``。"""
        return self.skills.get(skill_id)

    def to_dict(self) -> dict[str, Any]:
        """回写为 ``employees.json`` 单条记录形状(技能按 skill_id 排序)。"""
        return {
            "employee_id": self.employee_id,
            "name": self.name,
            "department": self.department,
            "current_position_id": self.current_position_id,
            "target_position_id": self.target_position_id,
            "years_of_experience": self.years_of_experience,
            "skills": [
                {
                    "skill_id": assessment.skill_id,
                    "level": assessment.level,
                    "evidence": assessment.evidence.to_dict(),
                }
                for assessment in sorted(
                    self.skills.values(), key=lambda a: a.skill_id
                )
            ],
        }


@dataclass(frozen=True)
class PositionRequirement:
    """岗位对单项技能的要求(经统一技能库补全名称与类别)。"""

    skill_id: str
    skill_name: str
    category: str
    importance: float  # 1-5,岗位侧重要度
    required_level: int

    def __post_init__(self) -> None:
        check_level(self.required_level, "岗位要求等级")
        if not 1 <= self.importance <= 5:
            raise ValueError(f"技能重要度必须在 1-5 之间,得到 {self.importance}")


@dataclass(frozen=True)
class SkillGap:
    """单项技能差距:``gap = required_level - current_level``(恒 > 0)。"""

    skill_id: str
    skill_name: str
    category: str
    current_level: int
    required_level: int
    importance: float
    gap: int
    gap_ratio: float  # gap / required_level,∈ (0, 1]
    weighted_gap: float  # gap × importance,推荐排序输入之一

    def to_dict(self) -> dict[str, Any]:
        """回写为 JSON 可序列化对象。"""
        return {
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "category": self.category,
            "current_level": self.current_level,
            "required_level": self.required_level,
            "gap": self.gap,
            "gap_ratio": self.gap_ratio,
            "importance": self.importance,
            "weighted_gap": self.weighted_gap,
        }


@dataclass(frozen=True)
class MetSkill:
    """已达标技能(当前等级 ≥ 岗位要求)。"""

    skill_id: str
    skill_name: str
    current_level: int
    required_level: int
    importance: float


@dataclass(frozen=True)
class ExtraSkill:
    """员工已具备但目标岗位未要求的技能(如后端出身的 Java / SQL)。"""

    skill_id: str
    skill_name: str
    level: int


@dataclass(frozen=True)
class GapReport:
    """结构化差距报告(大纲第六节):员工 → 缺失技能 → 缺失程度。

    作为课程推荐模块(大纲第七节 Candidate Generation)的输入。
    """

    employee_id: str
    employee_name: str
    department: str
    years_of_experience: int
    current_position_id: str
    current_position_name: str
    target_position_id: str
    target_position_name: str
    gaps: tuple[SkillGap, ...]
    met: tuple[MetSkill, ...]
    extra_skills: tuple[ExtraSkill, ...]
    readiness: float  # 0-1,按重要度加权的岗位准备度

    @property
    def missing_count(self) -> int:
        """缺失技能数。"""
        return len(self.gaps)

    @property
    def total_gap(self) -> int:
        """总差距(各级差值之和)。"""
        return sum(gap.gap for gap in self.gaps)

    @property
    def weighted_total_gap(self) -> float:
        """加权总差距(差距 × 岗位重要度之和)。"""
        return sum(gap.weighted_gap for gap in self.gaps)

    def to_dict(self) -> dict[str, Any]:
        """结构化输出(JSON 可序列化,供推荐模块与 Agent 工具消费)。"""
        return {
            "employee": {
                "employee_id": self.employee_id,
                "name": self.employee_name,
                "department": self.department,
                "years_of_experience": self.years_of_experience,
                "current_position_id": self.current_position_id,
                "target_position_id": self.target_position_id,
            },
            "target_position": {
                "position_id": self.target_position_id,
                "name": self.target_position_name,
            },
            "gaps": [gap.to_dict() for gap in self.gaps],
            "met": [
                {
                    "skill_id": met.skill_id,
                    "skill_name": met.skill_name,
                    "current_level": met.current_level,
                    "required_level": met.required_level,
                    "importance": met.importance,
                }
                for met in self.met
            ],
            "extra_skills": [
                {
                    "skill_id": extra.skill_id,
                    "skill_name": extra.skill_name,
                    "level": extra.level,
                }
                for extra in self.extra_skills
            ],
            "summary": {
                "missing_count": self.missing_count,
                "total_gap": self.total_gap,
                "weighted_total_gap": self.weighted_total_gap,
                "readiness": self.readiness,
            },
        }
