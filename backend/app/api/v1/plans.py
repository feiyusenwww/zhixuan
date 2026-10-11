"""志愿方案接口。

契约：docs/api-contract.md 第 5 节。
响应中 strategy / priority / tiers / quota / shortage / excluded / risks / summary /
data_status / disclaimer 为新增字段，已在 PR 描述中提请补入契约。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.response import ok
from app.schemas.core import PlanRequest
from app.services import plans as plans_service

router = APIRouter(prefix="/plans", tags=["志愿方案"])


@router.post("", summary="生成志愿方案")
def create_plan(payload: PlanRequest) -> dict[str, Any]:
    """生成冲—稳—保方案，标注每档依据并给出风险预警（tasks.md 6.3、6.4、6.5）。"""
    return ok(plans_service.build_plan(payload))
