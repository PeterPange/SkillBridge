"""SkillBridge Web 平台入口:app 工厂 + 路由注册。

分层结构(低耦合高内聚):
- services/  业务组合层(纯 Python,算法细节在此吸收)
- api/       薄路由层(参数校验 + 调用服务)
- static/    前端页面(角色选择 / 员工端 / HR 端)
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

# 预热 sentence-transformers:必须在业务模块导入之前完成
# (本地 profile/ 包与标准库 profile 双向遮蔽,详见 matcher 注释)。
from skill_normalization.matcher import _import_sentence_transformers

_import_sentence_transformers()
sys.modules.pop("profile", None)

from webapp.api import employee as employee_api  # noqa: E402
from webapp.api import hr as hr_api  # noqa: E402
from webapp.api import knowledge as knowledge_api  # noqa: E402

_STATIC = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    """构建 FastAPI 应用(工厂模式,便于测试注入)。"""
    app = FastAPI(title="SkillBridge", version="1.0.0")
    app.include_router(employee_api.router)
    app.include_router(hr_api.router)
    app.include_router(knowledge_api.router)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_STATIC / "index.html")

    @app.get("/employee")
    def employee_page() -> FileResponse:
        return FileResponse(_STATIC / "employee.html")

    @app.get("/hr")
    def hr_page() -> FileResponse:
        return FileResponse(_STATIC / "hr.html")

    return app


app = create_app()
