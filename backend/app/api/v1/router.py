"""v1 路由汇总。

模块划分与 docs/api-contract.md 一致，各模块接口定义在同名文件内：
    health   健康检查
    auth     认证（注册/登录）
    profile  考生档案
    pathways 升学途径与资格自检
    qa       可溯源问答
    plans    志愿方案
    schools  院校检索
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, health, pathways, plans, profile, qa, schools
from app.core.config import settings

router = APIRouter(prefix=settings.api_prefix)

router.include_router(health.router)
router.include_router(auth.router)
router.include_router(profile.router)
router.include_router(pathways.router)
router.include_router(qa.router)
router.include_router(plans.router)
router.include_router(schools.router)
