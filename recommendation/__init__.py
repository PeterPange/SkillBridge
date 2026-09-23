"""个性化课程推荐模块(大纲第七节,阶段 3A)。

推荐分两步(大纲第七节):

1. **Candidate Generation**:按 Skill Gap 从知识图谱沿
   ``(:Course)-[:TEACHES]->(:Skill)`` 关系召回候选课程
   (大纲示例:缺少 AI Agent → Develop AI Agents);
2. **Course Ranking**:候选课程五因子加权打分——
   Gap 覆盖度 / 技能重要性 / 难度匹配 / 前置满足 / 时间成本——
   排序输出 Top-K,并携带推荐理由数据(供 LLM 解释)。

系统因此不是「LLM,你觉得我应该学什么?」,而是::

    真实 Skill Gap → 候选课程生成 → 推荐模型排序 → LLM 解释为什么推荐

入口::

    python -m recommendation EMP_001            # 李明 → AI Engineer Top-5
    python -m recommendation --list             # 列出全部员工
    python -m recommendation EMP_001 --json     # 结构化 JSON(供 Agent / LLM)
    python -m recommendation EMP_001 --top-k 3  # 指定 Top-K

结构::

    recommendation/
    ├── models.py      领域模型(候选 / 权重 / 得分 / 推荐 / 报告)
    ├── candidates.py  Candidate Generation(图谱 TEACHES 关系召回)
    ├── ranking.py     Course Ranking(五因子加权打分,纯算法)
    ├── recommend.py   推荐管线(候选 → 排序 → Top-K 报告)
    ├── report.py      文本渲染
    └── __main__.py    CLI 入口
"""

from recommendation.candidates import generate_candidates
from recommendation.models import (
    CandidateCourse,
    CandidatePool,
    CourseContext,
    CourseRef,
    Recommendation,
    RecommendationReport,
    ScoreBreakdown,
    ScoringWeights,
)
from recommendation.ranking import (
    DIFFICULTY_RANK,
    PREREQUISITE_SATISFY_LEVEL,
    build_reasons,
    covered_gaps,
    difficulty_match_score,
    gap_coverage_score,
    importance_score,
    prerequisite_score,
    prerequisite_status,
    rank_candidates,
    score_candidate,
    time_cost_score,
)
from recommendation.recommend import DEFAULT_TOP_K, recommend_courses, recommend_from_pool
from recommendation.report import render_recommendation_report

__all__ = [
    # 模型
    "CandidateCourse",
    "CandidatePool",
    "CourseContext",
    "CourseRef",
    "Recommendation",
    "RecommendationReport",
    "ScoreBreakdown",
    "ScoringWeights",
    # 候选生成
    "generate_candidates",
    # 打分与排序
    "DIFFICULTY_RANK",
    "PREREQUISITE_SATISFY_LEVEL",
    "build_reasons",
    "covered_gaps",
    "difficulty_match_score",
    "gap_coverage_score",
    "importance_score",
    "prerequisite_score",
    "prerequisite_status",
    "rank_candidates",
    "score_candidate",
    "time_cost_score",
    # 管线与渲染
    "DEFAULT_TOP_K",
    "recommend_courses",
    "recommend_from_pool",
    "render_recommendation_report",
]
