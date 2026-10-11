"""认证业务逻辑。

当前为演示实现：不落库、密码不校验。
真实实现（注册/登录/JWT/密码加盐哈希/失败限流）见 tasks.md 3.1、3.2。
"""

from __future__ import annotations

from app.schemas.core import Credentials

DEMO_USER_ID = "u_demo"
DEMO_ACCESS_TOKEN = "mock-token"


def register(payload: Credentials) -> dict[str, object]:
    """注册并返回会话信息。"""
    return {
        "user_id": DEMO_USER_ID,
        "username": payload.username,
        "access_token": DEMO_ACCESS_TOKEN,
    }


def login(payload: Credentials) -> dict[str, object]:
    """登录并返回会话信息。"""
    return {
        "user_id": DEMO_USER_ID,
        "username": payload.username,
        "access_token": DEMO_ACCESS_TOKEN,
    }
