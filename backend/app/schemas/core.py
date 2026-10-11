"""接口请求/响应公共模型。

约定：字段 snake_case（docs/api-contract.md 统一约定）。
本文件为后端共享文件，新增字段一律以"可选 + 有默认值"的方式追加，避免破坏既有调用方。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# 户籍类型：'未知' 表示用户未填写，判定结果将落为"待核验"而非确定结论
HouseholdType = Literal["农村", "城镇", "未知"]


class ProfileRequest(BaseModel):
    """考生档案（契约 2. 考生档案）。"""

    province: str = "河南"
    score: int = Field(ge=0, le=750)
    subject_type: str = "物理类"


class EligibilityRequest(ProfileRequest):
    """路径资格自检请求（tasks.md 4.2）。

    在档案三字段基础上追加户籍与学籍条件，全部为可选：
    - 未填写时按"未知"处理，对应结论为"待核验"，不臆测为符合或不符合；
    - 因此仅携带 province/score/subject_type 的旧请求依然可用（游客自检 4.5）。
    """

    household_type: HouseholdType = "未知"
    household_county: str = Field(default="", max_length=50)
    enrollment_county: str = Field(default="", max_length=50)
    household_years: int = Field(default=0, ge=0, le=30, description="本人当地连续户籍年限，0 表示未知")
    enrollment_years: int = Field(default=0, ge=0, le=30, description="户籍所在县高中连续学籍年限，0 表示未知")
    parent_household_local: bool | None = Field(default=None, description="父母或法定监护人是否具有当地户籍")
    registered: bool = Field(default=True, description="是否已完成当年高考报名并通过报名资格审核")


class Citation(BaseModel):
    """来源三要素（缺一不得展示）。"""

    source_name: str
    source_url: str
    year: int


class Credentials(BaseModel):
    """注册/登录凭据。"""

    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class PlanRequest(BaseModel):
    """志愿方案生成请求（契约 5. 志愿方案）。

    除 profile 与 strategy 外均为新增可选字段，只传原有字段同样可用（tasks.md 6.3、6.4、6.5）。
    """

    profile: ProfileRequest
    strategy: Literal["冲", "稳", "保"] = "稳"
    priority: Literal["院校优先", "专业优先", "城市优先"] = Field(
        default="院校优先", description="排序策略（tasks.md 6.4）"
    )
    preferred_majors: list[str] = Field(default_factory=list, description="偏好专业，用于专业优先排序")
    preferred_provinces: list[str] = Field(
        default_factory=list, description="偏好省份或城市，用于城市优先排序"
    )
    limit: int = Field(default=9, ge=1, le=96, description="方案志愿总数，按倾向配额等比缩放")
    major_adjust: bool = Field(default=True, description="是否服从专业调剂")
    batch_line: int | None = Field(default=None, description="批次控制线，未提供时不判定贴近批次线风险")
