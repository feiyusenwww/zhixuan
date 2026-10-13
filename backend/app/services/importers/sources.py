"""来源登记表导入（data/sources/source-table.json → source 表）。

③ 号已产出 9 条来源（含可采集性结论）。文件中的字符串 id（如 ``SRC-HENAN-EXAM``）
是③侧的登记编号，库表 ``source`` 以自增整型为主键、按「三要素」唯一，
故本模块不保留该编号，按三要素幂等 upsert。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.constants import YEAR_MAX, YEAR_MIN
from app.models.source import Source
from app.services.importers import (
    DATA_ROOT,
    load_json,
    new_report,
    skip,
    source_triplet_missing,
)

DEFAULT_PATH = DATA_ROOT / "sources" / "source-table.json"


def _parse_fetched_at(value: Any) -> datetime | None:
    """解析 fetched_at（如 ``2026-10-11``）；空或非法一律返回 None，不编造。"""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def import_sources(db: Session, path: Path = DEFAULT_PATH) -> dict[str, Any]:
    """把来源登记表幂等写入 source 表，返回导入报告。"""
    report = new_report("source")
    payload = load_json(path)
    items = payload.get("sources") or []

    for item in items:
        report["read"] += 1
        if source_triplet_missing(item):
            skip(report, "missing_source")
            continue
        year = int(item["year"])
        if not (YEAR_MIN <= year <= YEAR_MAX):
            skip(report, "year_out_of_range")
            continue

        name = str(item["source_name"]).strip()
        url = str(item["source_url"]).strip()
        existing = db.scalar(
            select(Source).where(
                Source.source_name == name,
                Source.source_url == url,
                Source.year == year,
            )
        )
        fetched_at = _parse_fetched_at(item.get("fetched_at"))
        source_type = str(item.get("source_type") or "").strip() or None

        if existing is None:
            db.add(
                Source(
                    source_name=name,
                    source_url=url,
                    year=year,
                    source_type=source_type,
                    fetched_at=fetched_at,
                )
            )
            report["created"] += 1
            continue

        changed = False
        if source_type and existing.source_type != source_type:
            existing.source_type = source_type
            changed = True
        if fetched_at and existing.fetched_at != fetched_at:
            existing.fetched_at = fetched_at
            changed = True
        if changed:
            report["updated"] += 1

    db.commit()
    return report
