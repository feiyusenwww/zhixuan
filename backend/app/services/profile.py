"""考生档案业务逻辑。

当前为演示实现：读写均返回固定样例，不做持久化。
真实实现（字段校验、保存、专项资格标记与偏好）见 tasks.md 3.4、3.5。
"""

from __future__ import annotations

from app.schemas.core import ProfileRequest

DEMO_PROFILE: dict[str, object] = {
    "province": "河南",
    "score": 620,
    "subject_type": "物理类",
}


def get_profile() -> dict[str, object]:
    """读取当前考生档案。"""
    return dict(DEMO_PROFILE)


def save_profile(payload: ProfileRequest) -> dict[str, object]:
    """保存考生档案并回传保存后的结果。"""
    return payload.model_dump()
