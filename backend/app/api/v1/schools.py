"""院校检索接口。

契约：docs/api-contract.md 第 6 节。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.core.response import ok
from app.services import schools as schools_service

router = APIRouter(prefix="/schools", tags=["院校检索"])


@router.get("", summary="院校检索")
def search_schools(
    keyword: str = Query("", description="关键词"),
    province: str = Query("河南", description="省份"),
) -> dict[str, Any]:
    return ok(schools_service.search_schools(keyword, province))
