"""培训反馈与动态调整模块(大纲第十一节,阶段 5)。

系统闭环的关键一环:员工完成课程 → 考试成绩落库 → 更新技能画像
(Evidence 可解释)→ 重新计算 Skill Gap → 刷新课程推荐 → 重排学习路径::

    Course completed(考试 85 分)
          ↓
    training_record + assessment 落库(PostgreSQL)
          ↓
    分数映射技能等级提升(≥85 提升 1 级;70-84 提升 1 级标记「需巩固」;
    <70 不提升,追加「补基础」前置课程)
          ↓
    Evidence 追加(完成记录写入对应技能,可解释「为什么涨级」)
          ↓
    闭环重算:画像刷新 → Skill Gap 重算 → 推荐刷新 → 课表重排
    (已完成课程剪枝:第一次 A → B → C → D,学完 A/B 后只剩 C → D)
          ↓
    画像同步知识图谱(HAS_SKILL 等级 + Evidence)

**只做编排,不重复实现业务逻辑**:差距计算复用 :mod:`profile`,
推荐复用 :mod:`recommendation`,课表复用 :mod:`learning_path`
(两者均新增了可选的「排除已完成课程」参数,向后兼容)。

入口::

    python -m feedback complete EMP_001 CRS_001 --score 85   # 完成登记 + 闭环重算
    python -m feedback status EMP_001                        # 培训历史 + 当前准备度
    python -m feedback plan-diff EMP_001                     # 学习路径前后对比

结构::

    feedback/
    ├── models.py     领域模型(记录 / 等级变化 / 建议 / 闭环结果 / 路径对比)
    ├── store.py      培训记录存储(PostgreSQL + 内存实现,training_record + assessment)
    ├── replay.py      分数映射 + Evidence 追加 + 画像回放(唯一的新业务规则)
    ├── loop.py       闭环编排(登记 / 档案状态 / 路径对比,全部委托已有模块)
    ├── report.py     文本渲染(完成结果 / 培训档案 / 前后对比)
    └── __main__.py   CLI 入口(complete / status / plan-diff)
"""

from feedback.loop import (
    build_feedback_state,
    build_plan_diff,
    load_course_catalog,
    recalculate,
    record_completion,
    sync_profile_to_graph,
)
from feedback.models import (
    FLAG_CONSOLIDATE,
    SCORE_PASS,
    SCORE_SOLID,
    SUGGESTION_REMEDIATE,
    CompletionResult,
    FeedbackState,
    LoopResult,
    PlanDiff,
    ProfileUpdate,
    Suggestion,
    SkillLevelChange,
    TrainingRecord,
)
from feedback.replay import (
    OUTCOME_CONSOLIDATE,
    OUTCOME_FAIL,
    OUTCOME_SOLID,
    build_suggestions,
    replay_history,
    score_outcome,
)
from feedback.report import render_completion, render_plan_diff, render_status
from feedback.store import MemoryTrainingStore, PostgresTrainingStore, TrainingStore

__all__ = [
    # 模型与常量
    "CompletionResult",
    "FeedbackState",
    "LoopResult",
    "PlanDiff",
    "ProfileUpdate",
    "SkillLevelChange",
    "Suggestion",
    "TrainingRecord",
    "FLAG_CONSOLIDATE",
    "SCORE_PASS",
    "SCORE_SOLID",
    "SUGGESTION_REMEDIATE",
    # 分数映射与回放(唯一的新业务规则)
    "OUTCOME_CONSOLIDATE",
    "OUTCOME_FAIL",
    "OUTCOME_SOLID",
    "build_suggestions",
    "replay_history",
    "score_outcome",
    # 闭环编排
    "build_feedback_state",
    "build_plan_diff",
    "load_course_catalog",
    "recalculate",
    "record_completion",
    "sync_profile_to_graph",
    # 存储与渲染
    "MemoryTrainingStore",
    "PostgresTrainingStore",
    "TrainingStore",
    "render_completion",
    "render_plan_diff",
    "render_status",
]
