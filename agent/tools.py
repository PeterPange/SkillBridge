"""HR Training Agent 工具集(大纲第十节)。

Agent 是「整个系统的智能入口和任务编排层」——工具**只做编排**,
业务逻辑全部调用已有模块,不重复实现:

.. list-table:: 工具 → 已有模块
   :header-rows: 1

   * - 工具
     - 委托模块(大纲章节)
   * - ``get_employee_profile``
     - :mod:`profile`(第五节:员工画像,Evidence 可解释)
   * - ``get_skill_gap``
     - :mod:`profile.gap`(第六节:纯算法差距分析)
   * - ``recommend_courses``
     - :mod:`recommendation`(第七节:图谱召回 + 五因子排序)
   * - ``generate_learning_path``
     - :mod:`learning_path`(第八节:DAG 剪枝 + 拓扑排序 + 周计划)
   * - ``rag_query``
     - :mod:`rag`(第九节:pgvector 检索 + 重排 + 引用)

每个工具返回统一的 JSON 可序列化 payload::

    {"tool": 名称, "ok": bool, "data": {...}, "error": "..."}

后端不可用(Neo4j / PostgreSQL 未启动)时 ``ok=False`` 并携带原因,
状态机据此在回答中显式提示,而不是崩溃。

RAG 工具的防挂起设计:Embedding 模型本地已缓存时,HuggingFace hub
的在线版本检查在受限网络下会无限挂起。工具在加载 sentence-transformers
前设置 ``HF_HUB_OFFLINE=1``(``.env.example`` 已文档化的用法),模型
未缓存时快速失败并降级为「内存库 + 词面编码 + 内置培训制度文档」,
保证任何环境下 ``rag_query`` 都有界返回。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from neo4j.exceptions import AuthError, ServiceUnavailable

from profile import build_employee_profile, build_gap_report
from profile.__main__ import load_data
from rag import MemoryVectorStore, PgvectorStore, RagPipeline
from rag.models import SearchResult
from recommendation import recommend_courses as recommend_pipeline
from learning_path import generate_learning_path as learning_path_pipeline
from skillbridge.db import neo4j_driver
from skill_normalization import LexicalEncoder, SentenceTransformerEncoder

logger = logging.getLogger(__name__)

# Embedding 模型加载防挂起(受限网络下 HuggingFace hub 在线检查会无限阻塞):
# 模块导入时即声明离线模式(用户显式设置优先),模型已缓存时秒级加载,
# 未缓存时快速失败并降级词面编码。同进程内后续所有 sentence-transformers
# 加载(含测试收集阶段的模块级加载)同样受益,不再阻塞。
os.environ.setdefault("HF_HUB_OFFLINE", "1")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: RAG 离线降级时自动入库的内置文档(企业员工培训制度,大纲第九节 fixture)
RAG_FALLBACK_DOCUMENT = PROJECT_ROOT / "data" / "fixtures" / "training_policy.md"

#: sentence-transformers 多语言模型的向量维度(与库内 384 维数据匹配时启用)
ST_EMBEDDING_DIM = 384

#: 词面编码器维度
LEXICAL_DIM = 512

#: 业务数据(岗位 / 员工)进程级缓存:data/processed 优先,缺失自动离线重建
_DATA_CACHE: tuple[list[dict[str, Any]], list[dict[str, Any]]] | None = None

#: RAG 管线进程级缓存(避免每次工具调用重复加载 Embedding 模型)
_RAG_CACHE: tuple[RagPipeline, str] | None = None


# ---------------------------------------------------------------------------
# 业务数据加载(委托 profile.__main__.load_data,与 CLI 同源)
# ---------------------------------------------------------------------------


def load_business_data() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """加载岗位与员工数据,返回 ``(positions, employees)``(进程级缓存)。

    与 ``python -m profile`` 等 CLI 完全同源:优先 ``data/processed/``
    (``make collect`` 产出),缺失时自动回退离线管线(不联网、可复现),
    因此 Agent 引用的员工数据与各业务模块 CLI 一致。
    """
    global _DATA_CACHE
    if _DATA_CACHE is None:
        positions, employees = load_data()
        _DATA_CACHE = (positions, employees)
    return _DATA_CACHE


def reset_caches() -> None:
    """清空进程级缓存(测试隔离用)。"""
    global _DATA_CACHE, _RAG_CACHE
    _DATA_CACHE = None
    _RAG_CACHE = None


def resolve_employee(employee_id: str) -> dict[str, Any]:
    """按员工 ID 取员工记录。

    :raises LookupError: 员工 ID 不存在。
    """
    _, employees = load_business_data()
    for employee in employees:
        if employee["employee_id"] == employee_id:
            return dict(employee)
    known = ", ".join(e["employee_id"] for e in employees)
    raise LookupError(f"未知员工 {employee_id}(可用:{known})")


def _positions_by_id() -> dict[str, dict[str, Any]]:
    positions, _ = load_business_data()
    return {position["position_id"]: position for position in positions}


# ---------------------------------------------------------------------------
# 工具 1:员工画像(大纲第五节)
# ---------------------------------------------------------------------------


def get_employee_profile(employee_id: str) -> dict[str, Any]:
    """员工画像:基本信息 + 当前/目标岗位 + 技能等级(含 Evidence 摘要)。

    委托 :func:`profile.build_employee_profile`(等级 0-4 + 四类证据)。
    """
    try:
        record = resolve_employee(employee_id)
        profile = build_employee_profile(record)
    except (LookupError, ValueError, KeyError) as exc:
        return _failure("get_employee_profile", exc)

    positions = _positions_by_id()
    current = positions.get(profile.current_position_id, {})
    target = positions.get(profile.target_position_id, {})
    from data import skilllib

    def _skill_name(skill_id: str) -> str:
        try:
            return skilllib.get_skill(skill_id)["name"]
        except KeyError:
            return skill_id

    skills = [
        {
            "skill_id": assessment.skill_id,
            "skill_name": _skill_name(assessment.skill_id),
            "level": assessment.level,
            "evidence": {
                "assessment_score": assessment.evidence.assessment_score,
                "project_experience": assessment.evidence.project_experience,
                "self_assessment": assessment.evidence.self_assessment,
                "training_records": list(assessment.evidence.training_records),
            },
        }
        for assessment in sorted(
            profile.skills.values(), key=lambda a: a.skill_id
        )
    ]

    data = {
        "employee": {
            "employee_id": profile.employee_id,
            "name": profile.name,
            "department": profile.department,
            "years_of_experience": profile.years_of_experience,
            "current_position_id": profile.current_position_id,
            "current_position_name": str(current.get("name", profile.current_position_id)),
            "target_position_id": profile.target_position_id,
            "target_position_name": str(target.get("name", profile.target_position_id)),
        },
        "skills": skills,
    }
    return _success(
        "get_employee_profile",
        data,
        summary=(
            f"{profile.name}({profile.employee_id}),"
            f"{data['employee']['current_position_name']} → "
            f"{data['employee']['target_position_name']},"
            f"共登记 {len(skills)} 项技能"
        ),
    )


# ---------------------------------------------------------------------------
# 工具 2:能力差距(大纲第六节)
# ---------------------------------------------------------------------------


def get_skill_gap(employee_id: str) -> dict[str, Any]:
    """能力差距:目标岗位要求 vs 当前等级(纯算法,不含 LLM)。

    委托 :func:`profile.build_gap_report`,输出缺口列表 + 岗位准备度。
    """
    try:
        record = resolve_employee(employee_id)
        profile = build_employee_profile(record)
        positions = _positions_by_id()
        target = positions.get(profile.target_position_id)
        if target is None:
            raise LookupError(
                f"员工 {employee_id} 的目标岗位 {profile.target_position_id} 不存在"
            )
        report = build_gap_report(
            profile,
            target,
            current_position=positions.get(profile.current_position_id),
        )
    except (LookupError, ValueError, KeyError) as exc:
        return _failure("get_skill_gap", exc)

    data = report.to_dict()
    data["summary"]["readiness_percent"] = round(report.readiness * 100, 1)
    top_gaps = [
        f"{gap.skill_name} {gap.current_level}→{gap.required_level}"
        for gap in report.gaps[:3]
    ]
    return _success(
        "get_skill_gap",
        data,
        summary=(
            f"岗位准备度 {data['summary']['readiness_percent']}%,"
            f"缺失 {report.missing_count} 项技能"
            f"(总差距 {report.total_gap} 级),最大缺口:"
            + "、".join(top_gaps)
        ),
    )


# ---------------------------------------------------------------------------
# 工具 3:课程推荐(大纲第七节)
# ---------------------------------------------------------------------------


def recommend_courses(employee_id: str, top_k: int = 5) -> dict[str, Any]:
    """课程推荐:按缺口从图谱召回候选 → 五因子加权排序 → Top-K。

    委托 :func:`recommendation.recommend_courses`(Neo4j TEACHES 关系召回)。
    """
    try:
        record = resolve_employee(employee_id)
        profile = build_employee_profile(record)
        positions = _positions_by_id()
        target = positions.get(profile.target_position_id)
        if target is None:
            raise LookupError(
                f"员工 {employee_id} 的目标岗位 {profile.target_position_id} 不存在"
            )
        gap_report = build_gap_report(
            profile,
            target,
            current_position=positions.get(profile.current_position_id),
        )
    except (LookupError, ValueError, KeyError) as exc:
        return _failure("recommend_courses", exc)

    if top_k < 1:
        return _failure("recommend_courses", ValueError(f"top_k 必须 ≥ 1,得到 {top_k}"))

    try:
        driver = neo4j_driver()
    except Exception as exc:  # 驱动构造失败(服务未启动 / 配置错误等)
        return _failure(
            "recommend_courses",
            exc,
            hint="无法连接 Neo4j;请先 make up 启动服务并 make graph 导入图谱",
        )
    try:
        report = recommend_pipeline(driver, profile, gap_report, top_k=top_k)
    except (ServiceUnavailable, AuthError, OSError) as exc:
        return _failure(
            "recommend_courses",
            exc,
            hint="无法连接 Neo4j;请先 make up 启动服务并 make graph 导入图谱",
        )
    finally:
        driver.close()

    data = report.to_dict()
    names = [rec.course.name for rec in report.recommendations[:3]]
    return _success(
        "recommend_courses",
        data,
        summary=(
            f"候选 {report.candidate_count} 门,推荐 Top-{report.top_k}:"
            + "、".join(names)
            + ("" if len(names) < 3 else " 等")
        ),
    )


# ---------------------------------------------------------------------------
# 工具 4:学习路径(大纲第八节)
# ---------------------------------------------------------------------------


def generate_learning_path(
    employee_id: str,
    hours_per_week: float = 4.0,
    deadline_weeks: int = 8,
) -> dict[str, Any]:
    """学习路径:DAG 剪枝 → 拓扑排序 → 每周时间约束 → 周计划。

    委托 :func:`learning_path.generate_learning_path`(默认每周 4 小时、
    8 周截止,大纲第八节示例)。
    """
    try:
        record = resolve_employee(employee_id)
        profile = build_employee_profile(record)
        positions = _positions_by_id()
        target = positions.get(profile.target_position_id)
        if target is None:
            raise LookupError(
                f"员工 {employee_id} 的目标岗位 {profile.target_position_id} 不存在"
            )
        gap_report = build_gap_report(
            profile,
            target,
            current_position=positions.get(profile.current_position_id),
        )
    except (LookupError, ValueError, KeyError) as exc:
        return _failure("generate_learning_path", exc)

    if hours_per_week <= 0 or deadline_weeks < 1:
        return _failure(
            "generate_learning_path",
            ValueError(
                f"时间参数非法:每周 {hours_per_week} 小时 / 截止 {deadline_weeks} 周"
            ),
        )

    try:
        driver = neo4j_driver()
    except Exception as exc:  # 驱动构造失败(服务未启动 / 配置错误等)
        return _failure(
            "generate_learning_path",
            exc,
            hint="无法连接 Neo4j;请先 make up 启动服务并 make graph 导入图谱",
        )
    try:
        report = learning_path_pipeline(
            driver,
            profile,
            gap_report,
            hours_per_week=hours_per_week,
            deadline_weeks=deadline_weeks,
        )
    except (ServiceUnavailable, AuthError, OSError) as exc:
        return _failure(
            "generate_learning_path",
            exc,
            hint="无法连接 Neo4j;请先 make up 启动服务并 make graph 导入图谱",
        )
    finally:
        driver.close()

    data = report.to_dict()
    fit = "满足" if report.fits_deadline else "超出"
    return _success(
        "generate_learning_path",
        data,
        summary=(
            f"待学 {report.course_count} 门(剪枝已掌握 {len(report.pruned)} 门),"
            f"共 {report.total_hours:.1f} 小时,排期 {report.planned_weeks} 周"
            f"({fit} {deadline_weeks} 周截止)"
        ),
    )


# ---------------------------------------------------------------------------
# 工具 5:知识库问答(大纲第九节)
# ---------------------------------------------------------------------------


def _pgvector_dim() -> int | None:
    """探测 pgvector 已入库的向量维度;不可达 / 空库 / 无表返回 ``None``。

    快速失败:连接拒绝立即返回,不做重试,保证工具调用有界。
    """
    try:
        from skillbridge.db import postgres_connect

        conn = postgres_connect()
    except Exception:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(min(vector_dims(embedding)), 0) FROM rag_chunks")
            row = cur.fetchone()
        dim = int(row[0]) if row else 0
        return dim if dim > 0 else None
    except Exception:
        return None
    finally:
        conn.close()


#: sentence-transformers 加载的硬超时(守护线程兜底,超时降级词面编码)
ST_LOAD_TIMEOUT_SECONDS = 60.0


def _hf_offline_enabled() -> bool:
    """离线模式是否生效(用户显式关闭时尊重用户选择)。"""
    value = os.getenv("HF_HUB_OFFLINE", "").strip().lower()
    return value in ("1", "true", "yes", "on")


def _patch_hf_offline_constant() -> None:
    """修正 huggingface_hub 已烘焏的离线常量。

    ``huggingface_hub`` 在 import 时把 ``HF_HUB_OFFLINE`` 读入模块常量;
    若它先于本模块被导入(如测试收集阶段的模块级模型加载),仅改环境
    变量不生效。``is_offline_mode()`` 动态读该常量,直接补丁即可。
    """
    import sys

    if not _hf_offline_enabled():
        return
    constants = sys.modules.get("huggingface_hub.constants")
    if constants is not None and not getattr(constants, "HF_HUB_OFFLINE", False):
        try:
            constants.HF_HUB_OFFLINE = True
        except Exception:  # 常量补丁失败不阻塞,还有线程超时兜底
            logger.debug("补丁 huggingface_hub.constants.HF_HUB_OFFLINE 失败")


def _sentence_transformer_encoder() -> SentenceTransformerEncoder | None:
    """尝试加载本地缓存的 Embedding 模型;失败 / 超时返回 ``None``(降级词面)。

    三重防护保证有界返回:

    1. **离线模式**:模块导入时已 ``HF_HUB_OFFLINE=1``(用户显式设置优先),
       模型已缓存时跳过 hub 在线检查(受限网络下该检查会无限挂起),
       未缓存时快速失败;若 huggingface_hub 已被提前导入,再补丁其
       烘焏常量(见 :func:`_patch_hf_offline_constant`);
    2. **标准库遮蔽**:加载期间临时弹出 ``sys.modules['profile']``——
       Agent 先导入了仓库 ``profile/`` 包(画像工具),而 torch 懒加载的
       ``import profile`` 需要标准库 profile,不弹出会命中缓存里的仓库包,
       报 ``Could not import module 'PreTrainedModel'``
       (:func:`skill_normalization.matcher._import_sentence_transformers`
       的 sys.path hack 只处理路径,不处理已导入缓存);
    3. **硬超时**:守护线程加载,:data:`ST_LOAD_TIMEOUT_SECONDS` 秒内未
       完成( unforeseen 的阻塞路径)则放弃并降级,不无限等待。
    """
    import sys
    import threading

    _patch_hf_offline_constant()
    saved_profile = sys.modules.pop("profile", None)
    outcome: list[Any] = []

    def _load() -> None:
        try:
            encoder = SentenceTransformerEncoder()
            encoder.encode(["probe"])  # 触发模型加载,失败快速抛出
            outcome.append(encoder)
        except BaseException as exc:  # noqa: BLE001 - 线程内任何异常都转为降级
            outcome.append(exc)

    thread = threading.Thread(target=_load, name="st-encoder-load", daemon=True)
    thread.start()
    thread.join(ST_LOAD_TIMEOUT_SECONDS)
    # 超时时加载线程可能仍阻塞在网络上,但 import 阶段早已完成,恢复缓存安全
    if saved_profile is not None:
        sys.modules["profile"] = saved_profile

    if thread.is_alive():
        logger.warning(
            "sentence-transformers 加载超过 %.0f 秒,降级词面编码",
            ST_LOAD_TIMEOUT_SECONDS,
        )
        return None
    if not outcome:  # pragma: no cover - 线程既未完成也未报错
        return None
    result = outcome[0]
    if isinstance(result, BaseException):
        logger.info("sentence-transformers 不可用,降级词面编码: %s", result)
        return None
    return result


def _build_rag_pipeline() -> tuple[RagPipeline, str]:
    """构建 RAG 管线(进程级缓存),按存储维度选择编码后端。

    1. pgvector 有 384 维数据 → 本地 sentence-transformers 模型
       (加载失败降级 3);
    2. pgvector 有 512 维数据 → 词面编码;
    3. 其余(不可达 / 空库 / 维度不匹配)→ 内存库 + 词面编码,
       自动入库内置培训制度文档,离线可用。
    """
    global _RAG_CACHE
    if _RAG_CACHE is not None:
        return _RAG_CACHE

    dim = _pgvector_dim()
    pipeline: RagPipeline | None = None
    backend = ""
    if dim == ST_EMBEDDING_DIM:
        encoder = _sentence_transformer_encoder()
        if encoder is not None:
            pipeline, backend = (
                RagPipeline(encoder=encoder, store=PgvectorStore()),
                "pgvector + sentence-transformers",
            )
    elif dim == LEXICAL_DIM:
        pipeline, backend = (
            RagPipeline(encoder=LexicalEncoder(), store=PgvectorStore()),
            "pgvector + lexical",
        )

    if pipeline is None:
        # 离线降级:内存库 + 词面编码 + 内置培训制度文档
        pipeline = RagPipeline(encoder=LexicalEncoder(), store=MemoryVectorStore())
        if RAG_FALLBACK_DOCUMENT.is_file():
            pipeline.ingest_file(RAG_FALLBACK_DOCUMENT)
        backend = "memory + lexical(离线降级)"

    _RAG_CACHE = (pipeline, backend)
    return _RAG_CACHE


def rag_query(question: str, top_k: int = 4) -> dict[str, Any]:
    """知识库问答:检索企业培训制度 / 岗位说明等文档,带来源引用。

    委托 :class:`rag.RagPipeline`(pgvector 余弦召回 + 词面重排)。
    """
    if not question.strip():
        return _failure("rag_query", ValueError("问题不能为空"))
    if top_k < 1:
        return _failure("rag_query", ValueError(f"top_k 必须 ≥ 1,得到 {top_k}"))

    pipeline, backend = _build_rag_pipeline()
    try:
        result: SearchResult = pipeline.query(question, top_k=top_k)
    except Exception as exc:
        return _failure("rag_query", exc, hint=f"检索失败(后端 {backend})")

    hits = [
        {
            "title": scored.chunk.doc_title,
            "source": scored.chunk.source,
            "heading": " > ".join(scored.chunk.heading_path),
            "score": round(scored.score, 3),
            "content": scored.chunk.content,
        }
        for scored in result.chunks
    ]
    return _success(
        "rag_query",
        {"query": question, "backend": backend, "hits": hits, "context": result.context},
        summary=(
            f"后端 {backend},命中 {len(hits)} 个相关段落"
            + (f"(来自《{hits[0]['title']}》)" if hits else "")
        ),
    )


# ---------------------------------------------------------------------------
# 工具注册表:名称 → (实现, OpenAI function schema)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_employee_profile",
            "description": (
                "查询员工画像:基本信息、当前/目标岗位、技能等级与证据"
                "(大纲第五节)。参数:employee_id 如 EMP_001。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {
                        "type": "string",
                        "description": "员工 ID,如 EMP_001(李明)",
                    }
                },
                "required": ["employee_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_skill_gap",
            "description": (
                "计算员工相对目标岗位的能力差距:缺失技能列表、差距值、"
                "岗位准备度(大纲第六节,纯算法)。参数:employee_id。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {
                        "type": "string",
                        "description": "员工 ID,如 EMP_001(李明)",
                    }
                },
                "required": ["employee_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_courses",
            "description": (
                "按能力缺口推荐课程:知识图谱候选召回 + 五因子加权排序,"
                "输出 Top-K 推荐与理由(大纲第七节)。需要 Neo4j。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {
                        "type": "string",
                        "description": "员工 ID,如 EMP_001(李明)",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "推荐数量,默认 5",
                    },
                },
                "required": ["employee_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_learning_path",
            "description": (
                "生成学习路径周计划:课程 DAG 剪枝 + 拓扑排序 + 每周时间"
                "约束(大纲第八节)。需要 Neo4j。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {
                        "type": "string",
                        "description": "员工 ID,如 EMP_001(李明)",
                    },
                    "hours_per_week": {
                        "type": "number",
                        "description": "每周可学习小时数,默认 4",
                    },
                    "deadline_weeks": {
                        "type": "integer",
                        "description": "培训截止周数,默认 8",
                    },
                },
                "required": ["employee_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_query",
            "description": (
                "企业知识库问答:检索培训制度、岗位说明等文档,返回带来源"
                "引用的相关段落(大纲第九节)。用于回答「为什么推荐 / 公司"
                "规定是什么」类问题。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "要检索的自然语言问题",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回引用块数,默认 4",
                    },
                },
                "required": ["question"],
            },
        },
    },
]

#: 工具名 → 实现(执行节点按名称分发)
TOOL_IMPLEMENTATIONS: dict[str, Any] = {
    "get_employee_profile": get_employee_profile,
    "get_skill_gap": get_skill_gap,
    "recommend_courses": recommend_courses,
    "generate_learning_path": generate_learning_path,
    "rag_query": rag_query,
}

#: 全部工具名(顺序即大纲第十节的编排顺序)
TOOL_NAMES: tuple[str, ...] = tuple(TOOL_IMPLEMENTATIONS)


def run_tool(name: str, **kwargs: Any) -> dict[str, Any]:
    """按名称执行工具(状态机 execute 节点的分发入口)。

    :raises KeyError: 工具名不在注册表中(规划节点已过滤,防御兜底)。
    """
    implementation = TOOL_IMPLEMENTATIONS[name]
    return implementation(**kwargs)


def _success(tool: str, data: Any, *, summary: str = "") -> dict[str, Any]:
    """统一成功 payload。"""
    return {"tool": tool, "ok": True, "data": data, "error": None, "summary": summary}


def _failure(
    tool: str, exc: Exception | str, *, hint: str | None = None
) -> dict[str, Any]:
    """统一失败 payload(后端不可用等,不抛异常,由回答层显式提示)。"""
    message = str(exc) or exc.__class__.__name__
    if hint:
        message = f"{hint}:{message}"
    logger.warning("工具 %s 执行失败: %s", tool, message)
    return {"tool": tool, "ok": False, "data": None, "error": message, "summary": ""}
