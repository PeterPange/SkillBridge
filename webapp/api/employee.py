"""员工端 API:我的画像 / 计划 / 推荐 / 进度 / 登记完成。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from webapp.services.employee_service import build_employee_home

router = APIRouter(prefix="/api/employee", tags=["employee"])


class CompleteRequest(BaseModel):
    course_id: str
    score: int


@router.get("/me/{employee_id}/home")
def employee_home(employee_id: str, hours: float = 4.0, weeks: int = 8) -> dict:
    """员工端首页:一次返回全部视图数据(画像/差距/推荐/计划/进度)。"""
    try:
        view = build_employee_home(employee_id, hours=hours, weeks=weeks)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_json(view)


@router.post("/me/{employee_id}/complete")
def complete_course(employee_id: str, req: CompleteRequest) -> dict:
    """员工登记课程完成(报分),返回等级变化与下一步建议(产品语义)。"""
    if not 0 <= req.score <= 100:
        raise HTTPException(status_code=422, detail="分数必须在 0-100 之间")
    from feedback import record_completion
    from feedback.store import PostgresTrainingStore
    from skillbridge.db import neo4j_driver

    store = PostgresTrainingStore()
    store.ensure_schema()
    driver = neo4j_driver()
    try:
        driver.verify_connectivity()
        result = record_completion(
            driver, store, employee_id, req.course_id, exam_score=req.score, source="web"
        )
    finally:
        driver.close()

    changes = [
        {
            "skill": c.skill_name,
            "from_level": c.from_level,
            "to_level": c.to_level,
            "note": "恭喜,技能等级已提升" if c.to_level > c.from_level else "已记录学习经历",
        }
        for c in result.update.changes
    ]
    suggestions = [
        {"course": s.course_name, "reason": s.reason}
        for s in result.update.suggestions
    ]
    return {
        "recorded": True,
        "course_id": req.course_id,
        "score": req.score,
        "passed": req.score >= 70,
        "changes": changes,
        "suggestions": suggestions,
    }


def _to_json(view) -> dict:
    """视图模型 → JSON(保持 dataclass 字段命名)。"""
    import dataclasses

    def convert(obj):
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return {k: convert(v) for k, v in dataclasses.asdict(obj).items()}
        if isinstance(obj, list):
            return [convert(v) for v in obj]
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        return obj

    return convert(view)
