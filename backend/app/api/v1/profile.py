"""考生档案接口。

契约：docs/api-contract.md 第 2 节。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.response import ok
from app.schemas.core import ProfileRequest
from app.services import profile as profile_service

router = APIRouter(prefix="/user", tags=["考生档案"])


@router.get("/profile", summary="读取考生档案")
def get_profile() -> dict[str, Any]:
    return ok(profile_service.get_profile())


@router.put("/profile", summary="保存考生档案")
def update_profile(payload: ProfileRequest) -> dict[str, Any]:
    return ok(profile_service.save_profile(payload))
