"""数据模型共享常量（产品书第 7 章「数据模型与数据字典」）。

集中定义年份、分数、长度等边界，供各事实表的 CHECK 约束与列长度复用，
避免魔法值散落各处（第 7 章「通用要求：枚举字段用常量，禁止魔法值」）。
"""

from __future__ import annotations

# 年份合理区间：与 app/core/dataset.py 的来源校验口径保持一致
YEAR_MIN = 2000
YEAR_MAX = 2100

# 高考分数合理区间（满分为 750 分的省份口径）
SCORE_MIN = 0
SCORE_MAX = 750

# 常用列长度
PROVINCE_MAX_LENGTH = 20
SUBJECT_TYPE_MAX_LENGTH = 20
PATHWAY_ID_MAX_LENGTH = 32
USER_ID_MAX_LENGTH = 64
