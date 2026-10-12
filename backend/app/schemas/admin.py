"""管理端请求模型（产品书 6.6；tasks.md 8.1、8.2、8.6）。

按模块分节，字段名一律 snake_case，与产品书第 6 章保持一致。
所有模型均为新增，不影响既有 C 端接口的入参。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# 途径优先级与数据状态（产品书 6.6.6；与 app/models/pathway.py 的注释口径一致）
PathwayPriority = Literal["P0", "P1", "P2"]
PathwayDataStatus = Literal["ready", "planned"]
# 资格规则类型（产品书 7.2 pathway_eligibility.rule_type）
RuleType = Literal["户籍", "学籍", "区域", "成绩"]

SOURCE_NAME_MAX_LENGTH = 200
SOURCE_URL_MAX_LENGTH = 500


class AdminCredentials(BaseModel):
    """管理端登录凭据（产品书 6.6.1）。"""

    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=128)


class SourceInput(BaseModel):
    """来源三要素（产品书第 7 章：缺一拒收）。

    路径与规则维护用它承载「强制附官方来源」（tasks.md 8.6）；
    校验在服务层完成，缺失时返回 4001 而非 1001，便于前端标红提示。
    """

    source_name: str = Field(default="", max_length=SOURCE_NAME_MAX_LENGTH)
    source_url: str = Field(default="", max_length=SOURCE_URL_MAX_LENGTH)
    year: int = Field(default=0, description="数据所属年份")
    source_type: str | None = Field(default=None, max_length=32, description="official / school / media …")


class DocCreateRequest(BaseModel):
    """语料导入（产品书 6.6.2；tasks.md 8.2）。

    来源三要素按产品书 6.6 的写法**平铺**在顶层（含 ``source_name`` / ``source_url`` / ``year``）。
    ``chunks`` 可选：仅落库切片正文，向量化与索引重建属 8.3 / ④ 号职责。
    """

    title: str = Field(min_length=1, max_length=200)
    source_name: str = Field(default="", max_length=SOURCE_NAME_MAX_LENGTH)
    source_url: str = Field(default="", max_length=SOURCE_URL_MAX_LENGTH)
    year: int = Field(default=0, description="数据所属年份")
    doc_type: str = Field(default="", max_length=32, description="章程 / 公告 / 政策…")
    province: str = Field(default="", max_length=20)
    pathway_id: str | None = Field(default=None, max_length=32)
    content: str = Field(default="", description="语料正文")
    source_type: str | None = Field(default=None, max_length=32)
    chunks: list[str] = Field(default_factory=list, description="可选切片正文，向量化由 8.3 负责")


class PathwayWriteRequest(BaseModel):
    """升学途径字典写入（产品书 6.6.6；tasks.md 8.6）。"""

    name: str = Field(min_length=1, max_length=100)
    category: str = Field(default="", max_length=32)
    batch: str = Field(default="", max_length=32)
    target_group: str = Field(default="", max_length=50)
    apply_time: str = Field(default="", max_length=100)
    description: str = Field(default="")
    priority: PathwayPriority = "P2"
    data_status: PathwayDataStatus = "planned"
    year: int = Field(default=0, description="数据所属年份")
    source: SourceInput = Field(default_factory=SourceInput)


class PathwayRuleWriteRequest(BaseModel):
    """途径资格规则写入（产品书 6.6.7；tasks.md 8.6）。

    规则必须附官方来源：``source`` 三要素缺一即返回 4001，规则不入库。
    """

    pathway_id: str = Field(min_length=1, max_length=32)
    province: str = Field(default="", max_length=20, description="适用省份，空表示通用")
    rule_type: RuleType
    rule_desc: str = Field(default="", description="规则条文，前端可展开")
    params: dict[str, Any] = Field(default_factory=dict, description="规则参数")
    year: int = Field(default=0, description="数据所属年份")
    source: SourceInput = Field(default_factory=SourceInput)


# 审核动作（产品书 6.6.10）：通过 / 修正 / 驳回
ReviewAction = Literal["approve", "correct", "reject"]


class ReviewDecisionRequest(BaseModel):
    """人工审核决策（产品书 6.6.10 POST /review/tasks/{id}；tasks.md 8.5）。

    - ``approve``：认可原答案；
    - ``correct``：提交修正答案，**必须**带 ``corrected_answer``（缺失由服务层返回 1001），
      修正内容沉淀回知识库（缺来源时不沉淀，见 services/review.py）；
    - ``reject``：驳回，原答案不作为结论，任务留痕可追踪。
    """

    action: ReviewAction
    corrected_answer: str = Field(default="", description="修正后的答案，action=correct 时必填")
    comment: str = Field(default="", max_length=500, description="审核备注，随留痕保存")
