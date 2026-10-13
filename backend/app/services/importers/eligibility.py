"""资格规则导入（data/dictionaries/pathway-eligibility.json → pathway_eligibility 表）。

③ 号产出 **11 条资格规则**（河南 · 国家/高校/地方专项 + 普通批），供资格引擎与管理端消费。

三个已核实的特殊处理（与 ③ 的产出格式一一对应，均在 PR 文档中报备）：

1. **规则行本身无 ``year`` 字段**——year 取自该规则引用的来源记录
   （``source_id`` → source-table.json 中的登记行），保证可追溯、不编造。
   例如引用 SRC-HENAN-SPECIAL-REGION（year=2019，官方名单文件年份）的规则，
   库表 year 即为 2019。
2. **一条规则引用 ``general-batch``**，但该途径不在 ③ 的 26 类字典
   （字典中为 ``normal-batch``）——属 ③ 的 id 不一致问题，
   本模块按「外键缺失跳过」处理并计入报告，不静默造字典行。
3. **``placeholders`` 是占位骨架**（``source_id: null``，meta 明确要求
   「引擎按未提供处理」）——不入库，单独以 ``placeholder`` 计数。

业务键：(pathway_id, province, rule_type, rule_desc)。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pathway import Pathway, PathwayEligibility
from app.services import source_guard
from app.services.importers import (
    DATA_ROOT,
    load_json,
    new_report,
    skip,
)

DEFAULT_PATH = DATA_ROOT / "dictionaries" / "pathway-eligibility.json"
SOURCE_TABLE_PATH = DATA_ROOT / "sources" / "source-table.json"


class _SourceStub:
    def __init__(self, record: dict[str, Any]) -> None:
        self.source_name = str(record.get("source_name") or "")
        self.source_url = str(record.get("source_url") or "")
        self.year = int(record.get("year") or 0)
        self.source_type = str(record.get("source_type") or "").strip() or None


def _source_registry(path: Path = SOURCE_TABLE_PATH) -> dict[str, dict[str, Any]]:
    """把 source-table.json 转成 {登记编号: 来源记录}，供规则按其 source_id 解析。"""
    payload = load_json(path)
    return {str(item["id"]): item for item in (payload.get("sources") or [])}


def import_eligibility_rules(
    db: Session,
    path: Path = DEFAULT_PATH,
    registry: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """把资格规则幂等写入 pathway_eligibility 表，返回导入报告。"""
    report = new_report("pathway_eligibility")
    payload = load_json(path)
    rules = payload.get("rules") or []
    placeholders = payload.get("placeholders") or []
    if registry is None:
        registry = _source_registry()

    for item in rules:
        report["read"] += 1
        pathway_id = str(item.get("pathway_id") or "").strip()
        province = str(item.get("province") or "").strip()
        rule_type = str(item.get("rule_type") or "").strip()
        rule_desc = str(item.get("rule_desc") or "").strip()
        if not (pathway_id and province and rule_type and rule_desc):
            skip(report, "missing_field")
            continue

        if db.get(Pathway, pathway_id) is None:
            skip(report, "pathway_missing")
            continue

        source_code = str(item.get("source_id") or "").strip()
        record = registry.get(source_code)
        if record is None:
            skip(report, "source_unknown")
            continue
        source = source_guard.ensure_source(db, _SourceStub(record))
        year = int(record["year"])  # 规则行无 year，取来源登记年份（见模块 docstring）

        params = item.get("params")
        params = dict(params) if isinstance(params, dict) else {}

        existing = db.scalar(
            select(PathwayEligibility).where(
                PathwayEligibility.pathway_id == pathway_id,
                PathwayEligibility.province == province,
                PathwayEligibility.rule_type == rule_type,
                PathwayEligibility.rule_desc == rule_desc,
            )
        )
        if existing is None:
            db.add(
                PathwayEligibility(
                    pathway_id=pathway_id,
                    province=province,
                    rule_type=rule_type,
                    rule_desc=rule_desc,
                    params=params,
                    year=year,
                    source_id=source.id,
                )
            )
            report["created"] += 1
            continue

        changed = False
        if existing.params != params:
            existing.params = params
            changed = True
        if existing.year != year:
            existing.year = year
            changed = True
        if existing.source_id != source.id:
            existing.source_id = source.id
            changed = True
        if changed:
            report["updated"] += 1

    # 占位骨架不入库，单独计数（meta 约定：引擎按「未提供」处理）
    for _ in placeholders:
        skip(report, "placeholder")

    db.commit()
    return report
