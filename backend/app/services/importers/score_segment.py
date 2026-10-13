"""一分一段表导入（data/score_segment/score_segment_*.json → score_segment 表）。

③ 号产出河南省 2026 年两份：历史类 454 行、物理类 462 行（扫描件 OCR 解析，
官方只发布无文本层的 PDF，算法与质量边界见 data/score_segment/一分一段解析报告.md）。

注意：
- 每行带 ``confidence``（high / interpolated），score_segment 表无对应列，不入库；
  缺口分数（gap_scores）③ 已标注为缺失，文件中本就不存在这些行，**绝不按 0 补录**。
- 文件 meta 中的来源（SRC-HENAN-SCORE-SEG-2026）不在 source-table.json 内，
  但 meta 自带完整三要素，按「随记录在 source 表中登记」自动注册。
- 业务键：(province, year, subject_type, score)。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base_data import ScoreSegment
from app.models.constants import SCORE_MAX, SCORE_MIN
from app.services import source_guard
from app.services.importers import (
    DATA_ROOT,
    load_json,
    new_report,
    skip,
    source_triplet_missing,
)

DEFAULT_DIR = DATA_ROOT / "score_segment"
FILE_GLOB = "score_segment_*.json"


class _SourceStub:
    def __init__(self, meta: dict[str, Any]) -> None:
        self.source_name = str(meta.get("source_name") or "")
        self.source_url = str(meta.get("source_url") or "")
        self.year = int(meta.get("year") or 0)
        self.source_type = "official"


def _import_one_file(db: Session, path: Path, report: dict[str, Any]) -> None:
    payload = load_json(path)
    meta = payload.get("meta") or {}
    segments = payload.get("segments") or []

    if source_triplet_missing(meta):
        report["read"] += len(segments)
        for _ in segments:
            skip(report, "missing_source")
        return

    source = source_guard.ensure_source(db, _SourceStub(meta))
    for item in segments:
        report["read"] += 1
        try:
            province = str(item["province"]).strip()
            year = int(item["year"])
            subject_type = str(item["subject_type"]).strip()
            score = int(item["score"])
            cumulative_rank = int(item["cumulative_rank"])
        except (KeyError, TypeError, ValueError):
            skip(report, "missing_field")
            continue
        if not (SCORE_MIN <= score <= SCORE_MAX):
            skip(report, "score_out_of_range")
            continue
        if cumulative_rank < 0:
            skip(report, "rank_out_of_range")
            continue

        existing = db.scalar(
            select(ScoreSegment).where(
                ScoreSegment.province == province,
                ScoreSegment.year == year,
                ScoreSegment.subject_type == subject_type,
                ScoreSegment.score == score,
            )
        )
        if existing is None:
            db.add(
                ScoreSegment(
                    province=province,
                    year=year,
                    subject_type=subject_type,
                    score=score,
                    cumulative_rank=cumulative_rank,
                    source_id=source.id,
                )
            )
            report["created"] += 1
        elif existing.cumulative_rank != cumulative_rank:
            existing.cumulative_rank = cumulative_rank
            existing.source_id = source.id
            report["updated"] += 1


def import_score_segments(db: Session, directory: Path = DEFAULT_DIR) -> dict[str, Any]:
    """把目录下全部一分一段文件幂等写入 score_segment 表，返回导入报告。"""
    report = new_report("score_segment")
    files = sorted(directory.glob(FILE_GLOB))
    if not files:
        report["skipped"]["no_files"] = 1
        report["skipped_total"] += 1
        return report
    for path in files:
        _import_one_file(db, path, report)
    db.commit()
    return report
