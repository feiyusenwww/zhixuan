"""考生档案业务逻辑（tasks.md 3.4、3.5）。

- 读写：一个用户一份档案，首次读取时自动建立（get_or_create）；
- 校验：分数区间由 Pydantic 拦截（>750 或负数 → 1001）；专项标记必须是已知途径（写入口校验）；
- 局部更新：按「请求显式提供的字段」合并，未提供的字段保持原值，
  避免前端只 PUT 三字段时把户籍信息清空；
- merge_saved：用已保存档案补全请求中未提供的字段，供资格自检与方案生成使用（3.5）。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import dataset
from app.core.response import BizCode, BizError
from app.db.base import utcnow
from app.models.profile import Profile

# 可写入档案的字段（tasks.md 3.4）
PROFILE_FIELDS: tuple[str, ...] = (
    "province",
    "score",
    "subject_type",
    "household_type",
    "household_county",
    "enrollment_county",
    "household_years",
    "enrollment_years",
    "parent_household_local",
)

# 偏好字段（tasks.md 3.5），与 POST /api/plans 的请求字段同名
PREFERENCE_FIELDS: tuple[str, ...] = (
    "strategy",
    "priority",
    "preferred_majors",
    "preferred_provinces",
    "major_adjust",
)

# 资格自检时可用档案补全的字段（含专项标记）
ELIGIBILITY_FIELDS: tuple[str, ...] = PROFILE_FIELDS + ("special_marks",)

DEFAULT_PREFERENCES: dict[str, Any] = {
    "strategy": "稳",
    "priority": "院校优先",
    "preferred_majors": [],
    "preferred_provinces": [],
    "major_adjust": True,
}

_EMPTY_PROFILE: dict[str, Any] = {
    "province": "河南",
    "score": 0,
    "subject_type": "物理类",
    "household_type": "未知",
    "household_county": "",
    "enrollment_county": "",
    "household_years": 0,
    "enrollment_years": 0,
    "parent_household_local": None,
    "special_marks": [],
}


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def profile_dict(profile: Profile | None) -> dict[str, Any]:
    """档案的对外表示（补充字段见 PR 描述，需队长补入契约）。"""
    if profile is None:
        data = {**_EMPTY_PROFILE, "special_marks": []}
        data["preferences"] = dict(DEFAULT_PREFERENCES)
        data["updated_at"] = None
        return data

    data: dict[str, Any] = {field: getattr(profile, field) for field in PROFILE_FIELDS}
    data["special_marks"] = list(profile.special_marks or [])
    data["preferences"] = {**DEFAULT_PREFERENCES, **(profile.preferences or {})}
    data["updated_at"] = _iso(profile.updated_at)
    return data


def get_or_create(db: Session, user_id: str) -> dict[str, Any]:
    """读取档案；不存在则建立一份空档案（首次进入档案页即可用）。"""
    profile = db.get(Profile, user_id)
    if profile is None:
        profile = Profile(user_id=user_id)
        db.add(profile)
        db.commit()
    return profile_dict(profile)


def get_saved(db: Session, user_id: str) -> dict[str, Any]:
    """读取已保存档案（不建立），供"补全请求"使用。"""
    return profile_dict(db.get(Profile, user_id))


def validate_marks(marks: Sequence[str]) -> list[str]:
    """专项标记必须是已知途径：接受途径 id 或中文名称，统一存为 id。"""
    catalog = dataset.load_catalog()
    by_id = {str(item["id"]): str(item["id"]) for item in catalog}
    by_name = {str(item["name"]): str(item["id"]) for item in catalog}

    result: list[str] = []
    unknown: list[str] = []
    for raw in marks:
        key = str(raw).strip()
        if not key:
            continue
        resolved = by_id.get(key) or by_name.get(key)
        if resolved is None:
            unknown.append(key)
        elif resolved not in result:
            result.append(resolved)

    if unknown:
        raise BizError(
            "专项标记取值不合法："
            + "、".join(unknown)
            + "；可用取值见 GET /api/pathways 的 id 与 name",
            BizCode.PARAM_ERROR,
        )
    return result


def save(db: Session, user_id: str, payload: BaseModel) -> dict[str, Any]:
    """保存档案：只更新请求中显式提供的字段。"""
    profile = db.get(Profile, user_id)
    if profile is None:
        profile = Profile(user_id=user_id)
        db.add(profile)

    provided = payload.model_dump(exclude_unset=True)
    provided.pop("preferences", None)
    fields_set = set(payload.model_fields_set or set())

    # 嵌套模型需要单独取"显式提供的子字段"，否则会把未提交的偏好项重置为默认值
    nested_preferences: dict[str, Any] = {}
    if "preferences" in fields_set:
        nested_preferences = payload.preferences.model_dump(exclude_unset=True)

    for field in PROFILE_FIELDS:
        if field in provided:
            setattr(profile, field, provided[field])

    if "special_marks" in provided:
        profile.special_marks = validate_marks(provided["special_marks"])

    if nested_preferences:
        profile.preferences = {**(profile.preferences or {}), **nested_preferences}

    profile.updated_at = utcnow()
    db.commit()
    return profile_dict(profile)


def meaningful(value: Any) -> bool:
    """判断已保存的值是否可用于补全请求：空串 / 空列表 / 0 / None 视为未填写。"""
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, (str, list, tuple, set, dict)):
        return len(value) > 0
    return True


def merge_saved(
    payload: BaseModel,
    saved: Mapping[str, Any] | None,
    fields: Sequence[str],
) -> dict[str, Any]:
    """用已保存档案补全请求中「未显式提供」的字段（tasks.md 3.5）。

    客户端显式传值一律以客户端为准，只在字段缺席时回退到档案。
    """
    merged = payload.model_dump()
    if not saved:
        return merged
    provided = set(payload.model_fields_set or set())
    for field in fields:
        if field in provided:
            continue
        value = saved.get(field)
        if meaningful(value):
            merged[field] = value
    return merged


def saved_preferences(saved: Mapping[str, Any] | None) -> dict[str, Any]:
    """取出档案中的偏好字段，用于补全方案生成请求。"""
    if not saved:
        return {}
    preferences = saved.get("preferences") or {}
    return {key: preferences[key] for key in PREFERENCE_FIELDS if key in preferences}
