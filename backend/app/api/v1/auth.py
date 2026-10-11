"""认证接口：注册 / 登录。

契约：docs/api-contract.md 第 1 节。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.response import ok
from app.schemas.core import Credentials
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", summary="注册")
def register(payload: Credentials) -> dict[str, Any]:
    return ok(auth_service.register(payload))


@router.post("/login", summary="登录")
def login(payload: Credentials) -> dict[str, Any]:
    return ok(auth_service.login(payload))
