"""产品视图模型:算法输出 → 面向用户展示的结构。

本模块是「算法层 → 产品层」的唯一翻译点:
向量得分、加权差距、后端名、维度等中间数据一律在此吸收,
上层(API / 前端)只见产品语义:等级、进度、标签、纯文字理由。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillView:
    """员工的一项技能(画像展示用)。"""

    name: str
    level: int  # 0-4
    required_level: int | None = None  # 目标岗位要求;None = 岗位未要求
    status: str = "learning"  # met / learning / missing / extra

    @property
    def status_label(self) -> str:
        return {
            "met": "已达标",
            "learning": "提升中",
            "missing": "待补齐",
            "extra": "岗位外技能",
        }[self.status]


@dataclass(frozen=True)
class GapView:
    """一项能力差距(员工视角,纯产品语义)。"""

    skill: str
    current: int
    required: int
    is_core: bool  # 重要度 >= 5 → 核心技能
    suggestion: str  # 一句话说明,如「建议优先补齐」

    @property
    def summary(self) -> str:
        depth = "深度缺口" if self.required - self.current >= 3 else "待提升"
        prefix = "核心技能" if self.is_core else "岗位要求"
        return f"{prefix} · {depth}"


@dataclass(frozen=True)
class CourseCardView:
    """推荐课程卡片(隐藏评分小数,保留可解释理由)。"""

    name: str
    difficulty: str
    duration_minutes: int
    duration_label: str
    url: str
    reasons: list[str] = field(default_factory=list)
    covers: list[str] = field(default_factory=list)  # 覆盖的技能名


def duration_label(minutes: int) -> str:
    if minutes >= 60:
        return f"约 {minutes / 60:.1f} 小时"
    return f"{minutes} 分钟"


@dataclass(frozen=True)
class WeekPlanView:
    """一周的学习安排。"""

    week: int
    courses: list[dict[str, Any]]  # {name, minutes, difficulty, continued}


@dataclass(frozen=True)
class ProgressView:
    """学习进度。"""

    completed_count: int
    passed_count: int
    average_score: float | None
    current_week: int  # 当前应处于第几周
    total_weeks: int
    next_course: str | None


@dataclass(frozen=True)
class EmployeeHomeView:
    """员工端首页的完整数据(一次组装,页面零拼装)。"""

    employee: dict[str, Any]
    readiness_percent: int
    target_position: str
    current_position: str
    skills: list[SkillView]
    top_gaps: list[GapView]
    recommendations: list[CourseCardView]
    plan: list[WeekPlanView]
    progress: ProgressView


@dataclass(frozen=True)
class TeamMemberView:
    """HR 视角的员工行。"""

    employee_id: str
    name: str
    department: str
    current_position: str
    target_position: str
    readiness_percent: int
    bucket: str  # ready / close / far
    completed_courses: int
    average_score: float | None

    @property
    def bucket_label(self) -> str:
        return {"ready": "已达标", "close": "接近达标", "far": "差距较大"}[self.bucket]


@dataclass(frozen=True)
class TeamGapView:
    """团队级能力缺口(HR 聚合分析)。"""

    skill: str
    lacking_count: int  # 多少员工缺这门技能
    team_size: int
    is_core: bool

    @property
    def coverage_percent(self) -> int:
        return round(100 * (self.team_size - self.lacking_count) / self.team_size)


@dataclass(frozen=True)
class HrHomeView:
    """HR 端首页的完整数据。"""

    team_size: int
    average_readiness: int
    buckets: dict[str, int]  # ready/close/far → 人数
    top_team_gaps: list[TeamGapView]
    members: list[TeamMemberView]
    training: dict[str, Any]  # completions / pass_rate / average_score / recent


@dataclass(frozen=True)
class AnswerView:
    """知识库问答的产品化回答。"""

    question: str
    passages: list[dict[str, Any]]  # {doc_title, heading, content, source_name}


def readiness_percent(value: float) -> int:
    """0-1 小数 → 整数百分比(四舍五入,不再暴露长小数)。"""
    return round(float(value) * 100)


def bucket_of(readiness: float) -> str:
    """准备度分桶(HR 分布视图)。"""
    if readiness >= 0.8:
        return "ready"
    if readiness >= 0.5:
        return "close"
    return "far"
