"""资源中心与技能测评 API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from webapp.services import assessment_service, resource_service

router = APIRouter(prefix="/api/employee/me/{employee_id}", tags=["resources", "assessment"])


class AssessmentSubmission(BaseModel):
    answers: list[int]


@router.get("/resources")
def resources(employee_id: str) -> dict:
    """资源中心:视频 / 教材 / 文档 + 按缺口推荐。"""
    return resource_service.resource_library(employee_id)


@router.get("/assessments")
def assessments(employee_id: str) -> dict:
    """可测评技能列表 + 测评历史。"""
    return {
        "skills": assessment_service.assessable_skills(employee_id),
        "history": assessment_service.assessment_history(employee_id),
    }


@router.get("/assessments/{skill_id}/quiz")
def assessment_quiz(employee_id: str, skill_id: str) -> dict:
    """技能测评题目(答案不下发)。"""
    try:
        questions = assessment_service.build_skill_questions(skill_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "skill_id": skill_id,
        "pass_threshold": assessment_service.PASS_THRESHOLD,
        "questions": [
            {"index": q["index"], "question": q["question"], "options": q["options"]}
            for q in questions
        ],
    }


@router.post("/assessments/{skill_id}/submit")
def assessment_submit(employee_id: str, skill_id: str, req: AssessmentSubmission) -> dict:
    """提交测评:判分定级 + 落档 + 联动推荐。"""
    try:
        return assessment_service.grade_assessment(employee_id, skill_id, req.answers)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
