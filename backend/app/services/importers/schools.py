"""院校基础库导入（``school``，1367 所「在豫招生」本科院校）。

数据文件：``data/schools/schools_merged.json``（键 ``records``）
业务键：**``name``**，不是 ``code``。

为什么不按国标代码去重
----------------------
实盘 1367 行里有 40 个国标代码被**多个独立招生实体**共用
（「北京大学 / 北京大学医学部」「上海交通大学 / 医学院」「厦门大学 / 马来西亚分校」…），
而全部记录 ``name`` 零重复。若按 ``code`` 去重会误丢 75 行真实数据，
且会把医学部、分校这类独立招生单位合并掉。

``school`` 属产品书 7.1 的基础字典，**表内不含 ``source_id``**；
来源按「随记录在 source 表登记」处理——逐条 ensure_source，但不写入 school 行。

字段缺失留空不推断：``type`` / ``website`` / ``intro`` 在 ③ 的任务 2.5 补齐前全为空。
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base_data import School
from app.services.importers import (
    ImportReport,
    SourceRegistry,
    load_dataset,
    rows_of,
    text_of,
)

_WRITABLE = ("name", "code", "province", "city", "level", "type", "ownership", "website", "intro")


def import_schools(
    db: Session,
    path: Path,
    registry: SourceRegistry,
    *,
    key: str = "records",
) -> ImportReport:
    report = ImportReport(dataset="school")
    payload = load_dataset(path)
    if payload is None:
        report.missing_file = str(path)
        return report

    rows = rows_of(payload, key) or rows_of(payload, "schools")

    for row in rows:
        report.read += 1

        name = text_of(row, "name")
        if not name:
            report.skip("missing_name")
            continue

        province = text_of(row, "province")
        level = text_of(row, "level")
        if not province or not level:
            report.skip("missing_province_or_level")
            continue

        # 来源随记录在 source 表登记（school 表本身无 source_id 列）
        if registry.resolve(row) is None:
            report.skip("unresolvable_source")
            continue

        existing = db.scalar(select(School).where(School.name == name))

        if existing is None:
            entity = School(name=name, province=province, level=level)
            for field in _WRITABLE:
                if field not in {"name", "province", "level"}:
                    setattr(entity, field, text_of(row, field))
            db.add(entity)
            report.created += 1
            continue

        changed = False
        for field in _WRITABLE:
            value = text_of(row, field)
            if value and getattr(existing, field) != value:
                setattr(existing, field, value)
                changed = True

        if changed:
            report.updated += 1
        else:
            report.unchanged += 1

    db.flush()
    report.note(f"数据文件：{path}（业务键 name）")
    return report
