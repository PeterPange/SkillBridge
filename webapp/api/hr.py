"""HR 端 API:团队总览 / 缺口排行 / 成员档案 / 培训效果。"""

from __future__ import annotations

import dataclasses

from fastapi import APIRouter

from webapp.services.hr_service import build_hr_home

router = APIRouter(prefix="/api/hr", tags=["hr"])


@router.get("/home")
def hr_home() -> dict:
    """HR 端首页:团队总览、缺口排行、成员表、培训效果,一次返回。"""
    view = build_hr_home()

    def convert(obj):
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return {k: convert(v) for k, v in dataclasses.asdict(obj).items()}
        if isinstance(obj, list):
            return [convert(v) for v in obj]
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        return obj

    return convert(view)
