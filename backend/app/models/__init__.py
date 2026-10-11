"""ORM 模型集合。

导入本包即把所有模型注册到 Base.metadata，alembic 与环境初始化依赖这一点。
"""

from __future__ import annotations

from app.models.profile import Profile
from app.models.user import User

__all__ = ["Profile", "User"]
