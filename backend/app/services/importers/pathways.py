"""途径字典导入（data/dictionaries/pathways-26.json → pathway 表）。

③ 号产出 **26 类升学途径**（对齐产品书 2.4）。与演示种子（pathway_seed 的 10 条）
的关系：③ 的 id 命名（如 ``national-special``）与 catalog.json（如 ``national-plan``）
**不一致**，仅 ``strong-foundation`` 一个重合——重合行做 upsert 更新，其余为新增。
「两套 id 是否统一」属队长裁决项，本模块只按 ③ 的字典落地，不改用户端读文件的现状。

data_status 映射（③ 的三态 → 库表两态，与 pathway_seed 口径一致）：
    verified → ready；pending / schema_only → planned
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.pathway import Pathway
from app.services import source_guard
from app.services.importers import (
    DATA_ROOT,
    load_json,
    new_report,
    skip,
    source_triplet_missing,
)

DEFAULT_PATH = DATA_ROOT / "dictionaries" / "pathways-26.json"

# ③ 的三态 → 库表两态（ready / planned）
_DATA_STATUS_MAP = {"verified": "ready", "pending": "planned", "schema_only": "planned"}

_WRITABLE = (
    "name",
    "category",
    "batch",
    "target_group",
    "apply_time",
    "description",
    "priority",
    "data_status",
    "year",
)


class _SourceStub:
    def __init__(self, item: dict[str, Any]) -> None:
        self.source_name = str(item.get("source_name") or "")
        self.source_url = str(item.get("source_url") or "")
        self.year = int(item.get("year") or 0)
        self.source_type: str | None = None


def _map_status(value: Any) -> str:
    return _DATA_STATUS_MAP.get(str(value or "").strip(), "planned")


def import_pathways(db: Session, path: Path = DEFAULT_PATH) -> dict[str, Any]:
    """把 26 类途径字典幂等写入 pathway 表，返回导入报告。"""
    report = new_report("pathway")
    payload = load_json(path)
    items = payload.get("pathways") or []

    for item in items:
        report["read"] += 1
        pathway_id = str(item.get("id") or "").strip()
        if not pathway_id:
            skip(report, "missing_id")
            continue
        if source_triplet_missing(item):
            skip(report, "missing_source")
            continue

        source = source_guard.ensure_source(db, _SourceStub(item))
        values = {
            "name": str(item.get("name") or pathway_id).strip(),
            "category": str(item.get("category") or "").strip(),
            "batch": str(item.get("batch") or "").strip(),
            "target_group": str(item.get("target_group") or "").strip(),
            "apply_time": str(item.get("apply_time") or "").strip(),
            "description": str(item.get("description") or "").strip(),
            "priority": str(item.get("priority") or "P2").strip(),
            "data_status": _map_status(item.get("data_status")),
            "year": int(item["year"]),
        }

        existing = db.get(Pathway, pathway_id)
        if existing is None:
            db.add(Pathway(id=pathway_id, source_id=source.id, **values))
            report["created"] += 1
            continue

        changed = False
        for field in _WRITABLE:
            if getattr(existing, field) != values[field]:
                setattr(existing, field, values[field])
                changed = True
        if existing.source_id != source.id:
            existing.source_id = source.id
            changed = True
        if changed:
            report["updated"] += 1

    db.commit()
    return report
