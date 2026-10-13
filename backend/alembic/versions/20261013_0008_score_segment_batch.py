"""一分一段补 batch 列：老高考「一条连续曲线被批次线切段」，批次不可合并

依据 ``data/建表清单与数据来源对照表.md`` §1.7（③ 数据工程的口径发现）：

> 老高考一分一段是**一条连续曲线被批次线切段**。已验证 2024 河南理科：
> 本科一批 709→511（累计 10→130,195）；本科二批 510→396（累计 131,720→329,573，连续）；
> 专科批 395→100（累计 331,325→573,517）。⇒ ``batch`` 不可合并，合并会丢批次线信息。

原 ``score_segment`` 表缺 ``batch`` 列，按 ③ 的口径导入会丢字段，
故由 ② 补列（建表与迁移归 ②，产品书 M0-3）。

注：SQLite 下新增 NOT NULL 列必须带 ``server_default``；
本条只加列、不改索引，既有 ``ix_score_segment_lookup`` 保持不变。

Revision ID: 0008_score_segment_batch
Revises: 0007_rule_datasets
Create Date: 2026-10-13 16:40:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0008_score_segment_batch'
down_revision = '0007_rule_datasets'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'score_segment',
        sa.Column(
            'batch',
            sa.String(length=32),
            nullable=False,
            server_default='',
            comment='录取批次；老高考一分一段按批次线切段，不可合并',
        ),
    )


def downgrade() -> None:
    op.drop_column('score_segment', 'batch')
