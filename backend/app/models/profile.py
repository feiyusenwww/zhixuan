"""考生档案表（tasks.md 3.4、3.5）。

- 一个用户一份档案：user_id 既是主键也是外键，随用户注销级联删除；
- special_marks：考生自行标记的专项资格，取值须为途径 id，写入时校验（services/profile.py）；
- preferences：偏好字段（倾向、排序策略、偏好专业、偏好城市、是否服从调剂），
  /api/plans 在请求未显式提供这些字段时沿用档案里的值（tasks.md 3.5「据此调整」）；
- 所有字段都有默认值：未填写的项以"未知 / 空"呈现，判定引擎据此输出"待核验"而非臆测。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class Profile(Base):
    """考生档案。"""

    __tablename__ = "profiles"

    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    province: Mapped[str] = mapped_column(String(20), default="河南")
    score: Mapped[int] = mapped_column(Integer, default=0)
    subject_type: Mapped[str] = mapped_column(String(20), default="物理类")

    # 户籍与学籍（资格判定输入，tasks.md 4.2）
    household_type: Mapped[str] = mapped_column(String(8), default="未知")
    household_county: Mapped[str] = mapped_column(String(50), default="")
    enrollment_county: Mapped[str] = mapped_column(String(50), default="")
    household_years: Mapped[int] = mapped_column(Integer, default=0)
    enrollment_years: Mapped[int] = mapped_column(Integer, default=0)
    parent_household_local: Mapped[bool | None] = mapped_column(Boolean, default=None)

    # 专项资格标记与偏好（tasks.md 3.5）
    special_marks: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
