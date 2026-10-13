"""真实数据导入层测试（app/services/importers/）。

分两部分：
- **真实数据集成**：直接对仓库 ``data/`` 的 ③ 号产出物执行导入，校验
  「1367 院校 / 916 一分一段 / 91 区域 / 26 途径 / 10 规则 / 12 来源」全部落库、
  幂等二次执行为零新增零更新、外键（区域/规则 → 途径，规则/分段 → 来源）完整；
- **红线与边界（合成小文件）**：缺来源三要素 → 跳过不入库；年份越界 → 跳过；
  文件内重名院校 → 后者跳过；途径缺失的规则/区域 → 跳过；占位骨架不入库；
  规则年份取自来源登记年份；未知步骤报错。

红线（与 data/README.md 一致）：**缺来源绝不入库、绝不补默认值**。

纯脚本，无 pytest 依赖，直接运行：
    cd backend && .venv\\Scripts\\python.exe test_importers.py
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

# 环境变量必须在导入 app.* 之前设置：settings 在首次导入时读取一次
_WORK = Path(tempfile.mkdtemp(prefix="zhixuan_import_test_"))
os.environ["ZHIXUAN_DATABASE_URL"] = f"sqlite:///{(_WORK / 'import.db').as_posix()}"
os.environ["ZHIXUAN_SECRET_KEY"] = "test-secret-key-import-suite-at-least-32b"
os.environ["ZHIXUAN_ENV"] = "test"

from sqlalchemy import func, select  # noqa: E402

from app.db.session import SessionLocal, create_all  # noqa: E402
from app.models.base_data import School, ScoreSegment  # noqa: E402
from app.models.pathway import Pathway, PathwayEligibility, PathwayRegion  # noqa: E402
from app.models.source import Source  # noqa: E402
from app.services.importers import DATA_ROOT, new_report  # noqa: E402
from app.services.importers.__main__ import run_steps  # noqa: E402
from app.services.importers.eligibility import import_eligibility_rules  # noqa: E402
from app.services.importers.pathway_regions import import_pathway_regions  # noqa: E402
from app.services.importers.pathways import import_pathways  # noqa: E402
from app.services.importers.schools import import_schools  # noqa: E402
from app.services.importers.score_segment import import_score_segments  # noqa: E402
from app.services.importers.sources import import_sources  # noqa: E402

create_all()
logging.getLogger("zhixuan").setLevel(logging.CRITICAL)

CHECKS: list[tuple[str, Callable[[], None]]] = []


def check(name: str) -> Callable[[Callable[[], None]], Callable[[], None]]:
    def deco(fn: Callable[[], None]) -> Callable[[], None]:
        CHECKS.append((name, fn))
        return fn

    return deco


def _count(db, model) -> int:  # noqa: ANN001
    return db.scalar(select(func.count()).select_from(model)) or 0


def _write_json(directory: Path, name: str, payload: dict) -> Path:
    path = directory / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


# ============================================================ 真实数据集成


@check("真实数据：全量导入后各表行数与 ③ 交付一致")
def _() -> None:
    with SessionLocal() as db:
        reports = run_steps(db, ["sources", "pathways", "pathway_regions", "eligibility", "schools", "score_segment"])
    by_table = {r["table"]: r for r in reports}
    assert by_table["source"]["created"] == 12, by_table["source"]
    assert by_table["pathway"]["created"] == 26, by_table["pathway"]
    assert by_table["pathway_region"]["created"] == 91, by_table["pathway_region"]
    assert by_table["pathway_eligibility"]["created"] == 10, by_table["pathway_eligibility"]
    assert by_table["school"]["created"] == 1367, by_table["school"]
    assert by_table["score_segment"]["created"] == 916, by_table["score_segment"]


@check("真实数据：幂等——第二次导入零新增零更新")
def _() -> None:
    with SessionLocal() as db:
        reports = run_steps(db, ["sources", "pathways", "pathway_regions", "eligibility", "schools", "score_segment"])
    for report in reports:
        assert report["created"] == 0, report
        assert report["updated"] == 0, report


@check("真实数据：库表行数复核（与文件规模一致）")
def _() -> None:
    with SessionLocal() as db:
        assert _count(db, School) == 1367
        assert _count(db, ScoreSegment) == 916
        assert _count(db, Pathway) == 26
        assert _count(db, PathwayRegion) == 91
        assert _count(db, PathwayEligibility) == 10
        assert _count(db, Source) >= 12  # 分段/院校随行登记的来源也入库


@check("真实数据：院校字段抽查（北京大学 / 北京大学医学部 为两个独立实体）")
def _() -> None:
    with SessionLocal() as db:
        pku = db.scalar(select(School).where(School.name == "北京大学"))
        pku_med = db.scalar(select(School).where(School.name == "北京大学医学部"))
        assert pku is not None and pku_med is not None
        assert pku.id != pku_med.id, "同 code 的独立招生实体不得合并"
        assert pku.province == "北京" and pku.level == "本科"
        assert pku.code == "10001" and pku_med.code == "10001"


@check("真实数据：无代码校区行入库（北京交通大学(威海校区) code 为空）")
def _() -> None:
    with SessionLocal() as db:
        row = db.scalar(select(School).where(School.name == "北京交通大学(威海校区)"))
        assert row is not None
        assert row.code in (None, "")


@check("真实数据：一分一段抽查（历史类最高分 686 累计 7 人）")
def _() -> None:
    with SessionLocal() as db:
        row = db.scalar(
            select(ScoreSegment).where(
                ScoreSegment.province == "河南",
                ScoreSegment.year == 2026,
                ScoreSegment.subject_type == "历史类",
                ScoreSegment.score == 686,
            )
        )
        assert row is not None and row.cumulative_rank == 7
        assert row.source_id is not None


@check("真实数据：外键完整——区域/规则引用的途径全部存在")
def _() -> None:
    with SessionLocal() as db:
        region_pids = {pid for (pid,) in db.execute(select(PathwayRegion.pathway_id).distinct())}
        rule_pids = {pid for (pid,) in db.execute(select(PathwayEligibility.pathway_id).distinct())}
        known = {pid for (pid,) in db.execute(select(Pathway.id))}
        assert region_pids <= known, region_pids - known
        assert rule_pids <= known, rule_pids - known
        assert region_pids == {"national-special", "college-special"}


@check("真实数据：general-batch 规则因途径缺失被跳过（③ 的 id 不一致，已上报）")
def _() -> None:
    with SessionLocal() as db:
        report = import_eligibility_rules(db)
    assert report["created"] == 0
    assert report["skipped"].get("pathway_missing") == 1
    assert report["skipped"].get("placeholder") == 1


@check("真实数据：规则年份取自来源登记年份（非编造）")
def _() -> None:
    with SessionLocal() as db:
        rule = db.scalar(
            select(PathwayEligibility).where(
                PathwayEligibility.pathway_id == "national-special",
                PathwayEligibility.rule_type == "区域",
            )
        )
        assert rule is not None
        assert rule.year == 2019, "SRC-HENAN-SPECIAL-REGION 登记年份为 2019"
        rule2 = db.scalar(
            select(PathwayEligibility).where(
                PathwayEligibility.pathway_id == "national-special",
                PathwayEligibility.rule_type == "成绩",
            )
        )
        assert rule2 is not None and rule2.year == 2025, "SRC-HENAN-EXAM 登记年份为 2025"


@check("真实数据：分段来源自动注册（SRC-HENAN-SCORE-SEG-2026 不在 source-table 内）")
def _() -> None:
    with SessionLocal() as db:
        src = db.scalar(
            select(Source).where(
                Source.source_name == "河南省教育考试院（经河南省阳光高考信息平台发布）",
                Source.year == 2026,
            )
        )
        assert src is not None, "meta 自带三要素的来源应按「随记录登记」入库"


@check("真实数据：strong-foundation 与演示种子共存时按 id upsert（不重复建行）")
def _() -> None:
    # 当前库中 strong-foundation 来自本次导入；再导入一次，行数不变
    with SessionLocal() as db:
        before = _count(db, Pathway)
        report = import_pathways(db)
        after = _count(db, Pathway)
    assert before == after == 26
    assert report["created"] == 0


# ============================================================ 红线与边界（合成文件）


@check("红线：来源缺任一要素 → 跳过且不入库（sources）")
def _() -> None:
    tmp = _WORK / "case1"
    tmp.mkdir(exist_ok=True)
    path = _write_json(
        tmp,
        "source-table.json",
        {
            "sources": [
                {"id": "X1", "source_name": "缺URL", "source_url": "", "year": 2026},
                {"id": "X2", "source_name": "", "source_url": "https://a.cn", "year": 2026},
                {"id": "X3", "source_name": "缺年份", "source_url": "https://b.cn", "year": 0},
            ]
        },
    )
    with SessionLocal() as db:
        before = _count(db, Source)
        report = import_sources(db, path)
        after = _count(db, Source)
    assert report["created"] == 0 and report["skipped"]["missing_source"] == 3
    assert before == after, "缺来源绝不入库"


@check("红线：来源年份越界 → 跳过（year=1800）")
def _() -> None:
    tmp = _WORK / "case2"
    tmp.mkdir(exist_ok=True)
    path = _write_json(
        tmp,
        "source-table.json",
        {"sources": [{"id": "X4", "source_name": "越界", "source_url": "https://c.cn", "year": 1800}]},
    )
    with SessionLocal() as db:
        report = import_sources(db, path)
    assert report["created"] == 0 and report["skipped"]["year_out_of_range"] == 1


@check("红线：院校缺来源 → 跳过且不入库")
def _() -> None:
    tmp = _WORK / "case3"
    tmp.mkdir(exist_ok=True)
    path = _write_json(
        tmp,
        "schools_merged.json",
        {
            "records": [
                {
                    "name": "无来源测试大学",
                    "code": "99999",
                    "province": "河南",
                    "city": "郑州",
                    "level": "本科",
                    "source_name": "",
                    "source_url": "",
                    "year": 2026,
                }
            ]
        },
    )
    with SessionLocal() as db:
        report = import_schools(db, path)
        assert _count(db, School) == 1367, "不得新增"
    assert report["skipped"]["missing_source"] == 1


@check("边界：文件内重名院校 → 后者跳过")
def _() -> None:
    tmp = _WORK / "case4"
    tmp.mkdir(exist_ok=True)
    record = {
        "name": "重名测试大学",
        "code": "88888",
        "province": "河南",
        "level": "本科",
        "source_name": "测试来源",
        "source_url": "https://d.cn",
        "year": 2026,
    }
    dup = dict(record, code="77777")
    path = _write_json(tmp, "schools_merged.json", {"records": [record, dup]})
    with SessionLocal() as db:
        report = import_schools(db, path)
        row = db.scalar(select(School).where(School.name == "重名测试大学"))
    assert report["created"] == 1 and report["skipped"]["duplicate_name_in_file"] == 1
    assert row is not None and row.code == "88888", "保留首条"


@check("边界：区域引用不存在的途径 → 跳过（不造字典行）")
def _() -> None:
    tmp = _WORK / "case5"
    tmp.mkdir(exist_ok=True)
    path = _write_json(
        tmp,
        "pathway-regions.json",
        {
            "regions": [
                {
                    "pathway_id": "ghost-pathway",
                    "province": "河南省",
                    "county_name": "测试县",
                    "county_code": "419999",
                    "source_name": "测试来源",
                    "source_url": "https://e.cn",
                    "year": 2025,
                }
            ]
        },
    )
    with SessionLocal() as db:
        report = import_pathway_regions(db, path)
        assert _count(db, PathwayRegion) == 91
    assert report["skipped"]["pathway_missing"] == 1


@check("边界：分段文件 meta 缺来源 → 整文件跳过")
def _() -> None:
    tmp = _WORK / "case6"
    tmp.mkdir(exist_ok=True)
    _write_json(
        tmp,
        "score_segment_2099_物理类.json",
        {
            "meta": {"province": "河南", "year": 2099, "subject_type": "物理类", "source_name": "", "source_url": ""},
            "segments": [{"province": "河南", "year": 2099, "subject_type": "物理类", "score": 700, "cumulative_rank": 1}],
        },
    )
    with SessionLocal() as db:
        report = import_score_segments(db, tmp)
        assert _count(db, ScoreSegment) == 916
    assert report["skipped"]["missing_source"] == 1


@check("边界：分段字段缺失/分数越界 → 跳过")
def _() -> None:
    tmp = _WORK / "case7"
    tmp.mkdir(exist_ok=True)
    _write_json(
        tmp,
        "score_segment_2099_历史类.json",
        {
            "meta": {
                "province": "河南",
                "year": 2099,
                "subject_type": "历史类",
                "source_name": "测试来源",
                "source_url": "https://f.cn",
            },
            "segments": [
                {"province": "河南", "year": 2099, "subject_type": "历史类", "cumulative_rank": 1},  # 缺 score
                {"province": "河南", "year": 2099, "subject_type": "历史类", "score": 999, "cumulative_rank": 1},  # 越界
            ],
        },
    )
    with SessionLocal() as db:
        report = import_score_segments(db, tmp)
        assert _count(db, ScoreSegment) == 916
    assert report["skipped"]["missing_field"] == 1
    assert report["skipped"]["score_out_of_range"] == 1


@check("边界：未知导入步骤 → 报错")
def _() -> None:
    with SessionLocal() as db:
        try:
            run_steps(db, ["no_such_step"])
        except ValueError as exc:
            assert "未知导入步骤" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("应当抛出 ValueError")


@check("报告结构：new_report 字段齐全")
def _() -> None:
    report = new_report("t")
    assert report == {"table": "t", "read": 0, "created": 0, "updated": 0, "skipped_total": 0, "skipped": {}}


@check("真实数据文件齐备（防止仓库 data/ 被误删导致静默通过）")
def _() -> None:
    assert DATA_ROOT.is_dir(), DATA_ROOT
    for rel in (
        "sources/source-table.json",
        "schools/schools_merged.json",
        "dictionaries/pathways-26.json",
        "dictionaries/pathway-regions.json",
        "dictionaries/pathway-eligibility.json",
        "score_segment/score_segment_2026_历史类.json",
        "score_segment/score_segment_2026_物理类.json",
    ):
        assert (DATA_ROOT / rel).is_file(), rel


def main() -> int:
    passed = failed = 0
    for name, fn in CHECKS:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"[FAIL] {name} -> {type(exc).__name__}: {exc}")
        else:
            passed += 1
            print(f"[ ok ] {name}")
    print(f"\n{passed} passed, {failed} failed, {len(CHECKS)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
