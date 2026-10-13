"""一键导入入口：``python -m app.services.importers [步骤 ...]``。

不带参数时按依赖顺序执行全部步骤（来源 → 途径 → 区域 → 规则 → 院校 → 一分一段）。
每个步骤打印「读入 / 新增 / 更新 / 跳过（按原因）」，末尾汇总。

用法：
    cd backend
    .venv/Scripts/python.exe -m app.services.importers                # 全部
    .venv/Scripts/python.exe -m app.services.importers sources schools
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.services.importers import STEPS
from app.services.importers.eligibility import import_eligibility_rules
from app.services.importers.pathway_regions import import_pathway_regions
from app.services.importers.pathways import import_pathways
from app.services.importers.schools import import_schools
from app.services.importers.score_segment import import_score_segments
from app.services.importers.sources import import_sources

IMPORTERS: dict[str, Callable[[Session], dict[str, Any]]] = {
    "sources": import_sources,
    "pathways": import_pathways,
    "pathway_regions": import_pathway_regions,
    "eligibility": import_eligibility_rules,
    "schools": import_schools,
    "score_segment": import_score_segments,
}


def run_steps(db: Session, steps: list[str]) -> list[dict[str, Any]]:
    """按给定顺序执行导入步骤，返回各步骤报告。"""
    unknown = [step for step in steps if step not in IMPORTERS]
    if unknown:
        raise ValueError(f"未知导入步骤：{', '.join(unknown)}（可选：{', '.join(STEPS)}）")
    return [IMPORTERS[step](db) for step in steps]


def _format_report(report: dict[str, Any]) -> str:
    skipped = report["skipped"]
    skipped_text = (
        "、".join(f"{reason}={count}" for reason, count in sorted(skipped.items()))
        if skipped
        else "无"
    )
    return (
        f"  {report['table']:<22} 读入 {report['read']:>5} ｜ 新增 {report['created']:>5}"
        f" ｜ 更新 {report['updated']:>5} ｜ 跳过 {report['skipped_total']:>3}（{skipped_text}）"
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    steps = args or list(STEPS)

    from app.db.session import SessionLocal

    print(f"真实数据导入（data/ → 库表），步骤：{', '.join(steps)}")
    with SessionLocal() as db:
        reports = run_steps(db, steps)
    for report in reports:
        print(_format_report(report))

    total_created = sum(report["created"] for report in reports)
    total_updated = sum(report["updated"] for report in reports)
    total_skipped = sum(report["skipped_total"] for report in reports)
    print(f"完成：新增 {total_created}，更新 {total_updated}，跳过 {total_skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
