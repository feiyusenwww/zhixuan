"""应用入口。

统一响应包与全局异常处理见 app/core/response.py，契约见 docs/api-contract.md。
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router
from app.core.config import settings
from app.core.response import register_exception_handlers

app = FastAPI(title=settings.app_name, version=settings.version, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(router)
