"""专项实施区域导入（data/dictionaries/pathway-regions.json → pathway_region 表）。

③ 号产出 **91 行**「一县一途径」明细（国家专项 38 县 + 高校专项 53 县，含省定 15 县），
county_code 53/53 命中（民政部行政区划代码），已通过一致性校验。

外键依赖：``pathway_id`` 须已存在于 pathway 表（导入顺序见 importers.STEPS，
本步骤在 pathways 之后）；缺失的途径一律跳过并计入报告，不静默造字典行。

业务键：(pathway_id, province, county_name, year)。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pathway import Pathway, PathwayRegion
from app.services import source_guard
from app.services.importers import (
    DATA_ROOT,
    load_json,
    new_report,
    skip,
    source_triplet_missing,
)

DEFAULT_PATH = DATA_ROOT / "dictionaries" / "pathway-regions.json"


class _SourceStub:
    def __init__(self, item: dict[str, Any]) -> None:
        self.source_name = str(item.get("source_name") or "")
        self.source_url = str(item.get("source_url") or "")
        self.year = int(item.get("year") or 0)
        self.source_type: str | None = None


def import_pathway_regions(db: Session, path: Path = DEFAULT_PATH) -> dict[str, Any]:
    """把专项实施区域表幂等写入 pathway_region 表，返回导入报告。"""
    report = new_report("pathway_region")
    payload = load_json(path)
    items = payload.get("regions") or []

    for item in items:
        report["read"] += 1
        pathway_id = str(item.get("pathway_id") or "").strip()
        province = str(item.get("province") or "").strip()
        county_name = str(item.get("county_name") or "").strip()
        if not (pathway_id and province and county_name):
            skip(report, "missing_field")
            continue
        if source_triplet_missing(item):
            skip(report, "missing_source")
            continue

        pathway = db.get(Pathway, pathway_id)
        if pathway is None:
            skip(report, "pathway_missing")
            continue

        source = source_guard.ensure_source(db, _SourceStub(item))
        year = int(item["year"])
        county_code = str(item.get("county_code") or "").strip() or None

        existing = db.scalar(
            select(PathwayRegion).where(
                PathwayRegion.pathway_id == pathway_id,
                PathwayRegion.province == province,
                PathwayRegion.county_name == county_name,
                PathwayRegion.year == year,
            )
        )
        if existing is None:
            db.add(
                PathwayRegion(
                    pathway_id=pathway_id,
                    province=province,
                    county_name=county_name,
                    county_code=county_code,
                    year=year,
                    source_id=source.id,
                )
            )
            report["created"] += 1
            continue

        changed = False
        if existing.county_code != county_code:
            existing.county_code = county_code
            changed = True
        if existing.source_id != source.id:
            existing.source_id = source.id
            changed = True
        if changed:
            report["updated"] += 1

    db.commit()
    return report
