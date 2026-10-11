"""途径、规则、区域名单与志愿方案数据集：加载与来源强制校验。

约定（docs/api-contract.md 统一约定 + tasks.md 2.6）：
所有事实数据必须携带来源三要素 source_name / source_url / year，
缺失则拒绝加载并抛出 DataSourceError —— 宁可接口不可用，也不输出无来源结论。

数据文件位于 backend/app/data/ 下，由数据工程按 tasks.md 2.1、2.2、2.3、2.4、2.5 更新；
本模块只负责加载与校验，不含任何判定逻辑（判定见 app/services/ 下同名业务模块）。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"

CITATION_FIELDS = ("source_name", "source_url", "year")
MIN_YEAR = 2000
MAX_YEAR = 2100


class DataSourceError(RuntimeError):
    """数据集缺失来源三要素或结构非法，拒绝加载。"""


def _read_json(relative_path: str) -> dict[str, Any]:
    path = DATA_ROOT / relative_path
    if not path.is_file():
        raise DataSourceError(f"数据集不存在：{path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataSourceError(f"数据集不是合法 JSON：{path}（{exc}）") from exc
    if not isinstance(payload, dict):
        raise DataSourceError(f"数据集根节点必须是对象：{path}")
    return payload


def validate_citation(record: dict[str, Any], context: str) -> None:
    """校验来源三要素，任一缺失或非法即抛错。"""
    missing = [
        field
        for field in CITATION_FIELDS
        if record.get(field) is None
        or (isinstance(record.get(field), str) and not str(record[field]).strip())
    ]
    if missing:
        raise DataSourceError(f"{context} 缺少来源字段：{', '.join(missing)}")

    year = record.get("year")
    if isinstance(year, bool) or not isinstance(year, int) or not MIN_YEAR <= year <= MAX_YEAR:
        raise DataSourceError(f"{context} 的 year 非法：{year!r}，应为 {MIN_YEAR}-{MAX_YEAR} 的整数")


def citation_of(record: dict[str, Any]) -> dict[str, Any]:
    """抽取来源三要素，用于响应体中的 citations。"""
    return {field: record[field] for field in CITATION_FIELDS}


# --------------------------------------------------------------------------- #
# 升学途径（tasks.md 4.1）
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def load_catalog() -> tuple[dict[str, Any], ...]:
    """加载升学途径目录。"""
    pathways = _read_json("pathways/catalog.json").get("pathways") or []
    seen: set[str] = set()
    for item in pathways:
        pathway_id = str(item.get("id") or "")
        if not pathway_id:
            raise DataSourceError("途径条目缺少 id")
        if pathway_id in seen:
            raise DataSourceError(f"途径 id 重复：{pathway_id}")
        seen.add(pathway_id)
        if not str(item.get("name") or "").strip():
            raise DataSourceError(f"途径 {pathway_id} 缺少 name")
        validate_citation(item, f"途径 {pathway_id}")
    return tuple(pathways)


# --------------------------------------------------------------------------- #
# 专项实施区域（tasks.md 2.3、4.3）
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def load_regions() -> tuple[dict[str, Any], ...]:
    """加载专项计划实施区域名单。"""
    regions = _read_json("pathways/region_quotas.json").get("regions") or []
    for item in regions:
        context = f"区域条目 {item.get('province')}/{item.get('program')}"
        if not str(item.get("province") or "").strip():
            raise DataSourceError(f"{context} 缺少 province")
        if not str(item.get("program") or "").strip():
            raise DataSourceError(f"{context} 缺少 program")
        # 已核验的自名单区域必须有内容，避免"标了已核验却是空名单"导致静默误判
        if item.get("verified") and item.get("scope") == "county_list" and not item.get("counties"):
            raise DataSourceError(f"{context} 标记为已核验（verified=true）但县名单为空")
        validate_citation(item, context)
    return tuple(regions)


# --------------------------------------------------------------------------- #
# 资格判定规则（tasks.md 4.2、8.6）
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def load_rules() -> tuple[dict[str, Any], ...]:
    """加载路径资格判定规则库。"""
    rules = _read_json("pathways/eligibility_rules.json").get("rules") or []
    seen: set[str] = set()
    for rule in rules:
        rule_id = str(rule.get("rule_id") or "")
        if not rule_id:
            raise DataSourceError("规则缺少 rule_id")
        if rule_id in seen:
            raise DataSourceError(f"规则 ID 重复：{rule_id}")
        seen.add(rule_id)
        if not str(rule.get("pathway_id") or "").strip():
            raise DataSourceError(f"规则 {rule_id} 缺少 pathway_id")
        if not str(rule.get("check") or "").strip():
            raise DataSourceError(f"规则 {rule_id} 缺少 check 类型")
        validate_citation(rule, f"规则 {rule_id}")
    return tuple(rules)


# --------------------------------------------------------------------------- #
# 志愿方案：档位定义、风险规则、候选数据（tasks.md 6.3、6.4、6.5）
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def load_strategy_config() -> dict[str, Any]:
    """加载冲—稳—保档位定义，并校验档位区间不重叠。"""
    payload = _read_json("plans/strategies.json")
    strategies = payload.get("strategies") or []
    if not strategies:
        raise DataSourceError("档位定义不能为空")

    for item in strategies:
        label = str(item.get("label") or "")
        context = f"档位 {label or '?'}"
        if not label:
            raise DataSourceError("档位缺少 label")
        for field in ("min_gap", "max_gap"):
            if not isinstance(item.get(field), int):
                raise DataSourceError(f"{context} 的 {field} 必须是整数")
        if item["min_gap"] > item["max_gap"]:
            raise DataSourceError(f"{context} 的 min_gap 大于 max_gap")
        validate_citation(item, context)

    ordered = sorted(strategies, key=lambda item: item["min_gap"])
    for previous, current in zip(ordered, ordered[1:]):
        if current["min_gap"] <= previous["max_gap"]:
            raise DataSourceError(
                f"档位区间重叠：{previous['label']} 与 {current['label']}"
            )
    return payload


@lru_cache(maxsize=1)
def load_risk_rules() -> tuple[dict[str, Any], ...]:
    """加载志愿方案风险预警规则。"""
    rules = _read_json("plans/risk_rules.json").get("rules") or []
    seen: set[str] = set()
    for rule in rules:
        code = str(rule.get("code") or "")
        if not code:
            raise DataSourceError("风险规则缺少 code")
        if code in seen:
            raise DataSourceError(f"风险规则 code 重复：{code}")
        seen.add(code)
        for field in ("check", "level", "title", "detail"):
            if not str(rule.get(field) or "").strip():
                raise DataSourceError(f"风险规则 {code} 缺少 {field}")
        validate_citation(rule, f"风险规则 {code}")
    return tuple(rules)


@lru_cache(maxsize=1)
def load_candidates() -> tuple[dict[str, Any], ...]:
    """加载候选院校专业数据。

    当前为演示数据；接入 tasks.md 2.1、2.2 的真实录取数据后替换本函数实现即可。
    """
    candidates = _read_json("plans/candidates_demo.json").get("candidates") or []
    seen: set[str] = set()
    for item in candidates:
        school_id = str(item.get("school_id") or "")
        if not school_id:
            raise DataSourceError("候选数据缺少 school_id")
        if school_id in seen:
            raise DataSourceError(f"候选数据 school_id 重复：{school_id}")
        seen.add(school_id)
        if not str(item.get("name") or "").strip():
            raise DataSourceError(f"候选 {school_id} 缺少 name")
        if not isinstance(item.get("min_score"), int):
            raise DataSourceError(f"候选 {school_id} 的 min_score 必须是整数")
        validate_citation(item, f"候选 {school_id}")
    return tuple(candidates)


def clear_cache() -> None:
    """清空数据缓存，供管理端重建索引或测试使用。"""
    load_catalog.cache_clear()
    load_regions.cache_clear()
    load_rules.cache_clear()
    load_strategy_config.cache_clear()
    load_risk_rules.cache_clear()
    load_candidates.cache_clear()
