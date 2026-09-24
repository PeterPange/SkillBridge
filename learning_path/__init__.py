"""自适应学习路径模块(大纲第八节,阶段 3B)。

推荐解决「学什么」,学习路径解决「先学哪个、每周学多少」。
输入为差距报告(大纲第六节)与候选课程(大纲第七节,直接复用
:func:`recommendation.candidates.generate_candidates` 的召回逻辑),
输出按拓扑序排布、满足每周时间约束的周计划::

    课程 DAG(前置关系)
          ↓
    删除已经掌握课程(员工已有能力,按难度门槛判定)
          ↓
    补齐必须前置课程(图谱传递闭包)
          ↓
    拓扑排序(核心缺口优先,Kahn 算法,环检测兜底)
          ↓
    结合每周可学时间(默认 4 小时)→ 周计划
          ↓
    8 周截止期限校验(超出显式提示,不静默截断)

入口::

    python -m learning_path EMP_001            # 李明 → AI Engineer 周计划
    python -m learning_path --list             # 列出全部员工
    python -m learning_path EMP_001 --json     # 结构化 JSON(供 Agent / LLM)
    python -m learning_path EMP_001 --hours-per-week 6 --weeks 12

结构::

    learning_path/
    ├── models.py      领域模型(课程 / 剪枝 / 周计划 / 报告)
    ├── dag.py         DAG 剪枝 + 补齐前置 + 拓扑排序(纯算法,含环检测)
    ├── schedule.py    每周时间约束分配(纯算法,支持跨周续学)
    ├── graph.py       图谱查询:候选课程的传递前置闭包
    ├── path.py        规划管线(纯规划 + 完整管线两个入口)
    ├── report.py      文本渲染
    └── __main__.py    CLI 入口
"""

from learning_path.dag import (
    MASTERY_THRESHOLDS,
    CycleError,
    average_skill_level,
    is_mastered,
    mastery_threshold,
    select_path_courses,
    topological_order,
)
from learning_path.graph import fetch_course_closure
from learning_path.models import (
    PRUNE_REASON_COMPLETED,
    PRUNE_REASON_MASTERED,
    LearningPathReport,
    PathCourse,
    PrunedCourse,
    WeekCourse,
    WeekPlan,
)
from learning_path.path import (
    DEFAULT_DEADLINE_WEEKS,
    DEFAULT_HOURS_PER_WEEK,
    build_learning_path,
    gap_priority,
    generate_learning_path,
)
from learning_path.report import render_learning_path_report
from learning_path.schedule import allocate_weeks

__all__ = [
    # 模型
    "LearningPathReport",
    "PathCourse",
    "PrunedCourse",
    "WeekCourse",
    "WeekPlan",
    # 剪枝原因
    "PRUNE_REASON_COMPLETED",
    "PRUNE_REASON_MASTERED",
    # DAG:剪枝 + 补齐前置 + 拓扑排序
    "MASTERY_THRESHOLDS",
    "CycleError",
    "average_skill_level",
    "is_mastered",
    "mastery_threshold",
    "select_path_courses",
    "topological_order",
    # 时间分配
    "allocate_weeks",
    # 图谱查询
    "fetch_course_closure",
    # 管线与渲染
    "DEFAULT_DEADLINE_WEEKS",
    "DEFAULT_HOURS_PER_WEEK",
    "build_learning_path",
    "gap_priority",
    "generate_learning_path",
    "render_learning_path_report",
]
