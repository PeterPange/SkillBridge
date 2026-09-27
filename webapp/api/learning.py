"""站内学习 API:课程内容 / 单元进度 / 结业测验 / 自动记录。"""

from __future__ import annotations

import dataclasses

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from webapp.services.learning_service import (
    build_course_learning,
    build_quiz,
    grade_quiz,
    mark_unit_complete,
)

router = APIRouter(prefix="/api/employee/me/{employee_id}/courses", tags=["learning"])


class QuizSubmission(BaseModel):
    answers: list[int]


def _to_json(obj) -> dict:
    def convert(value):
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            return {k: convert(v) for k, v in dataclasses.asdict(value).items()}
        if isinstance(value, list):
            return [convert(v) for v in value]
        if isinstance(value, dict):
            return {k: convert(v) for k, v in value.items()}
        return value

    return convert(obj)


@router.get("/{course_id}")
def course_learning(employee_id: str, course_id: str) -> dict:
    """站内学习视图:单元内容 + 我的进度 + 测验解锁状态。"""
    try:
        view = build_course_learning(employee_id, course_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _to_json(view)


@router.post("/{course_id}/units/{unit_index}/complete")
def unit_complete(employee_id: str, course_id: str, unit_index: int) -> dict:
    """标记单元完成(自动进度,无需手填)。"""
    try:
        return mark_unit_complete(employee_id, course_id, unit_index)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{course_id}/quiz")
def quiz(employee_id: str, course_id: str) -> dict:
    """结业测验题目(答案保留在服务端)。"""
    try:
        questions = build_quiz(course_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "course_id": course_id,
        "pass_threshold": 70,
        "questions": [
            {
                "index": q["index"],
                "question": q["question"],
                "options": q["options"],
            }
            for q in questions  # answer_index 不下发
        ],
    }


@router.post("/{course_id}/quiz/submit")
def quiz_submit(employee_id: str, course_id: str, req: QuizSubmission) -> dict:
    """提交答卷:判卷 + 达标自动登记(触发画像/差距/课表重算)。"""
    try:
        return grade_quiz(employee_id, course_id, req.answers)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
