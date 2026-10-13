"""真实数据导入层（tasks.md 第 2 组产出物 → 库表）。

背景：③ 号数据工程的产出物落在仓库 ``data/`` 目录（JSON 文件），
而服务层（app/services/schools.py、majors.py 等）已重写为「查库表」。
本包把 ``data/`` 下的真实数据幂等灌进库表——**数据入库后服务层零改代码即生效**。

与 ``app/services/*_seed.py``（演示数据，数据源在 ``app/data/``）的区别：
- 本包读仓库根目录的 ``data/``（③ 的真实采集产物）；
- seed 读 ``app/data/``（本地演示数据，仅供开发跑通）。

铁律（与 data/README.md「三条铁律」一致）：
1. **来源三要素（source_name / source_url / year）缺一不入库**——跳过并计入报告，绝不补默认值；
2. **幂等**——按业务键 upsert，重复执行结果一致（第二次全为「新增 0、更新 0」）；
3. **禁止编造**——③ 未提供的字段（如 school.type / website / intro）留空，不用推断填充。

用法：
    cd backend && .venv/Scripts/python.exe -m app.services.importers          # 全部
    cd backend && .venv/Scripts/python.exe -m app.services.importers schools  # 指定步骤
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# __file__ = <repo>/backend/app/services/importers/__init__.py
# parents: [0]=importers [1]=services [2]=app [3]=backend [4]=<repo 根>
REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_ROOT = REPO_ROOT / "data"

# 导入步骤的依赖顺序：来源 → 途径字典 → 区域/规则（外键依赖途径）→ 院校 → 一分一段
STEPS = ("sources", "pathways", "pathway_regions", "eligibility", "schools", "score_segment")


def load_json(path: Path) -> Any:
    """读取 UTF-8 JSON 文件。"""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def new_report(table: str) -> dict[str, Any]:
    """新建一份导入报告计数器。

    ``skipped`` 为按原因分类的计数（如 missing_source / pathway_missing），
    汇总见 ``skipped_total``。
    """
    return {
        "table": table,
        "read": 0,
        "created": 0,
        "updated": 0,
        "skipped_total": 0,
        "skipped": {},
    }


def skip(report: dict[str, Any], reason: str) -> None:
    """记录一次跳过（缺来源 / 外键缺失 / 占位骨架等）。"""
    report["skipped_total"] += 1
    report["skipped"][reason] = report["skipped"].get(reason, 0) + 1


def source_triplet_missing(item: dict[str, Any]) -> list[str]:
    """返回缺失的来源字段名（不抛异常；导入器的口径是「跳过」而非「报错」）。"""
    missing: list[str] = []
    if not str(item.get("source_name") or "").strip():
        missing.append("source_name")
    if not str(item.get("source_url") or "").strip():
        missing.append("source_url")
    if not int(item.get("year") or 0):
        missing.append("year")
    return missing
