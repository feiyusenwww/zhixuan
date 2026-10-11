"""升学途径目录、路径资格自检与专项实施区域判定接口。

契约：docs/api-contract.md 第 3 节。
本文件中的 /region-check 与 /{pathway_id} 为新增接口，
已在 PR 描述中提请队长补入契约（契约变更流程见 api-contract.md 末节）。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.core.response import BizError, ok
from app.schemas.core import EligibilityRequest
from app.services import eligibility as eligibility_service
from app.services import pathways as pathways_service

router = APIRouter(prefix="/pathways", tags=["升学途径"])


@router.get("", summary="升学途径目录")
def list_pathways(
    category: str | None = Query(default=None, description="按分类过滤，如 专项计划"),
    priority: str | None = Query(default=None, description="按优先级过滤：P0 / P1 / P2"),
    status: str | None = Query(default=None, description="按状态过滤，如 数据规划中"),
) -> dict[str, Any]:
    return ok(
        pathways_service.list_pathways(category=category, priority=priority, status=status)
    )


@router.get("/region-check", summary="专项实施区域判定")
def region_check(
    province: str = Query(default="河南", description="省份"),
    county: str = Query(default="", description="县名"),
) -> dict[str, Any]:
    """按省份与县名返回所属专项实施范围（tasks.md 4.3）。"""
    return ok(eligibility_service.check_region(province, county))


@router.post("/eligibility-check", summary="路径资格自检")
def eligibility_check(payload: EligibilityRequest) -> dict[str, Any]:
    """游客可用（tasks.md 4.5）。判定由确定性规则引擎完成，不含模型参与（design.md D6）。"""
    return ok(eligibility_service.evaluate(payload))


@router.get("/{pathway_id}", summary="升学途径详情")
def get_pathway(pathway_id: str) -> dict[str, Any]:
    detail = pathways_service.get_pathway(pathway_id)
    if detail is None:
        raise BizError(f"途径不存在：{pathway_id}")
    return ok(detail)
