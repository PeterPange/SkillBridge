"""SkillBridge Web 平台:FastAPI 后端,包装全部业务模块。

大纲第十二节的员工端/演示端:一个页面展示
画像 → 能力差距 → 课程推荐 → 学习路径 → 培训反馈 的全流程,
并提供知识库问答与 HR Agent 入口。
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

# 预热 sentence-transformers:必须在下方业务模块导入之前完成。
# 本地 profile/ 包会遮蔽标准库 profile(torch 导入链依赖);反过来,
# torch 导入链会把标准库 profile 先入 sys.modules,导致本地包不可导入。
# 顺序:先预热(torch 拿到标准库 profile)→ 弹出该缓存项 → 再导入
# 业务模块(本地 profile 包重新接管 sys.modules)。
import sys as _sys

from skill_normalization.matcher import _import_sentence_transformers

_import_sentence_transformers()
_sys.modules.pop("profile", None)

from feedback import build_feedback_state, build_plan_diff, record_completion
from feedback.store import PostgresTrainingStore
from learning_path import generate_learning_path
from profile import build_employee_profile, build_gap_report
from profile.__main__ import DEFAULT_DATA_DIR
from recommendation import recommend_courses
from skillbridge.db import neo4j_driver

app = FastAPI(title="SkillBridge", version="0.1.0")

_STATIC_DIR = Path(__file__).parent / "static"


def _serialize(obj: Any) -> Any:
    """统一序列化:dataclass / to_dict / 原样。"""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if is_dataclass(obj) and not hasattr(obj, "__dataclass_fields__"):
        return obj
    if is_dataclass(obj):
        try:
            return asdict(obj)
        except TypeError:
            pass
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    return str(obj)


def _load_employees() -> list[dict[str, Any]]:
    path = Path(DEFAULT_DATA_DIR) / "employees.json"
    if not path.exists():
        raise HTTPException(status_code=503, detail="员工数据未生成,请先运行 python -m data.collect")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["employees"]


def _position_names() -> dict[str, str]:
    path = Path(DEFAULT_DATA_DIR) / "positions.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {p["position_id"]: p["name"] for p in data["positions"]}


def _skill_names() -> dict[str, str]:
    path = Path(DEFAULT_DATA_DIR) / "skills.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("skills", data) if isinstance(data, dict) else data
    return {s["skill_id"]: s["name"] for s in items}


def _find_employee(employee_id: str) -> dict[str, Any]:
    for record in _load_employees():
        if record.get("employee_id") == employee_id:
            return record
    raise HTTPException(status_code=404, detail=f"员工不存在:{employee_id}")


class CompleteRequest(BaseModel):
    employee_id: str
    course_id: str
    score: int


class AskRequest(BaseModel):
    question: str


@app.get("/api/employees")
def list_employees() -> list[dict[str, Any]]:
    """员工列表(左侧选择器数据源)。"""
    names = _position_names()
    employees = []
    for record in _load_employees():
        employees.append(
            {
                "id": record["employee_id"],
                "name": record["name"],
                "department": record.get("department", ""),
                "current_position": names.get(record.get("current_position_id", ""), ""),
                "target_position": names.get(record.get("target_position_id", ""), ""),
                "years": record.get("years_of_experience", 0),
            }
        )
    return employees


@app.get("/api/employee/{employee_id}/overview")
def employee_overview(employee_id: str, hours: float = 4.0, weeks: int = 8) -> dict[str, Any]:
    """全流程总览:画像 → 差距(前后) → 推荐 → 路径(前后) → 培训记录。"""
    record = _find_employee(employee_id)
    store = PostgresTrainingStore()
    store.ensure_schema()

    state = build_feedback_state(store, employee_id)
    gap = state.gap_after
    driver = neo4j_driver()
    try:
        driver.verify_connectivity()
        recommendations = recommend_courses(
            driver, state.profile, state.gap_after, top_k=5
        )
        plan_diff = build_plan_diff(
            driver, state, hours_per_week=hours, deadline_weeks=weeks
        )
    finally:
        driver.close()

    return {
        "employee": {
            "id": record["employee_id"],
            "name": gap.employee_name,
            "department": gap.department,
            "years": gap.years_of_experience,
            "current_position": gap.current_position_name,
            "target_position": gap.target_position_name,
        },
        "skill_names": _skill_names(),
        "profile": _serialize(state.profile),
        "gap_before": _serialize(state.gap_before),
        "gap_after": _serialize(state.gap_after),
        "recommendations": _serialize(recommendations),
        "plan_before": _serialize(plan_diff.before),
        "plan_after": _serialize(plan_diff.after),
        "records": _serialize(store.list_records(employee_id)),
    }


@app.post("/api/complete")
def complete_course(req: CompleteRequest) -> dict[str, Any]:
    """记录课程完成(反馈闭环入口),返回等级变化与更新后的状态。"""
    _find_employee(req.employee_id)
    if not 0 <= req.score <= 100:
        raise HTTPException(status_code=422, detail="分数必须在 0-100 之间")
    store = PostgresTrainingStore()
    store.ensure_schema()
    driver = neo4j_driver()
    try:
        driver.verify_connectivity()
        result = record_completion(
            driver, store, req.employee_id, req.course_id, exam_score=req.score
        )
    finally:
        driver.close()
    return _serialize(result)


@app.post("/api/ask")
def ask_knowledge_base(req: AskRequest) -> dict[str, Any]:
    """企业知识库问答(RAG)。"""
    from rag.pipeline import RagPipeline

    pipeline = RagPipeline()
    result = pipeline.query(req.question, top_k=3)
    return _serialize(result)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")
