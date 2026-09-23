"""推荐管线(大纲第七节):Skill Gap → 候选生成 → 加权排序 → Top-K 报告。

对应大纲第七节的整体流程::

    真实 Skill Gap
          ↓
    候选课程生成(图谱 TEACHES 关系)
          ↓
    推荐模型排序(五因子加权打分)
          ↓
    Top-K + 推荐理由(供 LLM 解释)

两个入口:

- :func:`recommend_courses`    完整管线(图谱召回 + 排序);
- :func:`recommend_from_pool`  纯排序管线(候选池已就绪,不访问数据库,
  排序逻辑可脱离 Neo4j 单测)。
"""

from __future__ import annotations

from neo4j import Driver

from profile.models import EmployeeProfile, GapReport
from recommendation.candidates import generate_candidates
from recommendation.models import (
    CandidatePool,
    Recommendation,
    RecommendationReport,
    ScoringWeights,
)
from recommendation.ranking import (
    build_reasons,
    prerequisite_status,
    rank_candidates,
)

#: 默认推荐数量(大纲验收:输出合理 Top-5)
DEFAULT_TOP_K = 5


def recommend_from_pool(
    pool: CandidatePool,
    profile: EmployeeProfile,
    gap_report: GapReport,
    *,
    top_k: int = DEFAULT_TOP_K,
    weights: ScoringWeights | None = None,
) -> RecommendationReport:
    """对已就绪的候选池打分排序,构建 Top-K 推荐报告(不访问数据库)。

    :param pool: 候选池(:func:`~recommendation.candidates.generate_candidates` 产出)。
    :param profile: 员工画像(提供技能当前等级)。
    :param gap_report: 差距报告(提供缺口与岗位元数据)。
    :param top_k: 推荐数量,≥ 1。
    :param weights: 五因子权重(默认 :class:`ScoringWeights`)。
    :raises ValueError: ``top_k`` 小于 1。
    """
    if top_k < 1:
        raise ValueError(f"top_k 必须大于等于 1,得到 {top_k}")
    weights = weights or ScoringWeights()
    level_of = profile.level_of

    ranked = rank_candidates(
        pool, gap_report.gaps, level_of, weights=weights, top_k=top_k
    )
    recommendations: list[Recommendation] = []
    for index, (course, breakdown, covered) in enumerate(ranked, start=1):
        satisfied, missing = prerequisite_status(course, pool, level_of)
        recommendations.append(
            Recommendation(
                rank=index,
                course=course,
                score=breakdown.total,
                breakdown=breakdown,
                covered_gaps=covered,
                satisfied_prerequisites=satisfied,
                missing_prerequisites=missing,
                reasons=build_reasons(
                    course, breakdown, covered, satisfied, missing, level_of
                ),
            )
        )

    return RecommendationReport(
        employee_id=gap_report.employee_id,
        employee_name=gap_report.employee_name,
        target_position_id=gap_report.target_position_id,
        target_position_name=gap_report.target_position_name,
        top_k=top_k,
        weights=weights,
        recommendations=tuple(recommendations),
        candidate_count=len(pool.candidates),
        uncovered_skills=pool.uncovered,
    )


def recommend_courses(
    driver: Driver,
    profile: EmployeeProfile,
    gap_report: GapReport,
    *,
    top_k: int = DEFAULT_TOP_K,
    weights: ScoringWeights | None = None,
    database: str | None = None,
) -> RecommendationReport:
    """完整推荐管线:按缺口从图谱召回候选 → 加权排序 → Top-K 报告。

    :param driver: Neo4j 驱动(需已导入课程图谱,``make graph``)。
    :param profile: 员工画像。
    :param gap_report: 差距报告(大纲第六节输出,本模块的输入)。
    :param top_k: 推荐数量(默认 5)。
    :param weights: 五因子权重。
    :param database: Neo4j 数据库(默认取 ``NEO4J_DATABASE`` 配置)。
    """
    pool = generate_candidates(driver, gap_report.gaps, database=database)
    return recommend_from_pool(
        pool, profile, gap_report, top_k=top_k, weights=weights
    )
