"""院校库导入（data/schools/schools_merged.json → school 表）。

③ 号产出 **1367 所在豫招生本科院校**（在豫招生计划系统 + 教育部全国高校名单双源合并，
按国标代码匹配 1316、按名称匹配 20）。字段状态见文件 meta.field_status：
- 已填：name / code / province / city / level；
- 部分填：ownership；
- 待补：type / website / intro（③ 明确「严禁编造」，本模块**留空不推断**）。

业务键：``name``（经实盘核查，1367 行 **name 零重复**）。
不能用 ``code``：③ 的合并结果中 40 个国标代码被 2+ 个**独立招生实体**共用
（如 北京大学 10001 / 北京大学医学部 10001、厦门大学 / 厦门大学(马来西亚分校)），
且部分校区行无代码（如 北京交通大学(威海校区)）——按 code 去重会把这些实体误删。

school 表按产品书 7.1 属基础字典、不含 source_id 列；
来源按「随记录在 source 表中登记」处理——逐条 ensure_source，但不写入 school 行。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base_data import School
from app.services import source_guard
from app.services.importers import (
    DATA_ROOT,
    load_json,
    new_report,
    skip,
    source_triplet_missing,
)

DEFAULT_PATH = DATA_ROOT / "schools" / "schools_merged.json"

# 允许 upsert 的字段（code 是业务键，不回写；id 是文件内行号，不入库）
_WRITABLE = ("name", "province", "city", "level", "type", "ownership", "website", "intro")


def _text(item: dict[str, Any], field: str) -> str:
    return str(item.get(field) or "").strip()


class _SourceStub:
    """把记录适配成 ensure_source 需要的来源三要素结构。"""

    def __init__(self, item: dict[str, Any]) -> None:
        self.source_name = str(item.get("source_name") or "")
        self.source_url = str(item.get("source_url") or "")
        self.year = int(item.get("year") or 0)
        self.source_type: str | None = None


def import_schools(db: Session, path: Path = DEFAULT_PATH) -> dict[str, Any]:
    """把院校库幂等写入 school 表，返回导入报告。"""
    report = new_report("school")
    payload = load_json(path)
    records = payload.get("records") or []

    seen_names: set[str] = set()
    for item in records:
        report["read"] += 1
        if source_triplet_missing(item):
            skip(report, "missing_source")
            continue

        code = _text(item, "code")
        name = _text(item, "name")
        if not name:
            skip(report, "missing_name")
            continue
        if name in seen_names:
            skip(report, "duplicate_name_in_file")
            continue
        seen_names.add(name)

        # 来源随记录在 source 表登记（school 表本身无 source_id 列）
        source_guard.ensure_source(db, _SourceStub(item))

        existing = db.scalar(select(School).where(School.name == name))

        if existing is None:
            db.add(
                School(
                    name=name,
                    code=code or None,
                    province=_text(item, "province"),
                    city=_text(item, "city"),
                    level=_text(item, "level"),
                    type=_text(item, "type"),
                    ownership=_text(item, "ownership"),
                    website=_text(item, "website"),
                    intro=_text(item, "intro"),
                )
            )
            report["created"] += 1
            continue

        changed = False
        for field in _WRITABLE:
            value = _text(item, field)
            if value and getattr(existing, field) != value:
                setattr(existing, field, value)
                changed = True
        # 同名但缺代码的旧行，补登国标代码
        if code and not existing.code:
            existing.code = code
            changed = True
        if changed:
            report["updated"] += 1

    db.commit()
    return report
