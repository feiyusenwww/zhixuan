"""院校专业录取分：放开 school_id/major_id 必填，并补身份列

依据 ``data/建表清单与数据来源对照表.md`` §四-3 / §1.8 与
``data/school_major_score/录取分导入说明.md`` §三。

1) **可空**（③ 明确要求）
   ``school_id``：录取分是 2022–2025、院校库是 2026 招生计划，院校改名等原因
   导致 2,862 行（2.5%）挂不上院校，③ 已置空 + flag，要求 ② 允许 NULL，
   「导入时应保留并打 flag，不要拒绝」。
   ``major_id``：专业库（任务 2.1）未建，③ 首期整列留空。

2) **身份列**（超出产品书第 7 章，由 ② 依据 ③ 的实际产物补充）
   ``group_code`` / ``major_code`` / ``major_name`` / ``exam_system``。
   ③ 的产物里 ``major_id`` 恒空，一行录取分的实际身份是
   「专业组 + 专业」；缺这两列则无法区分同校同年同批次下的不同专业
   （官方样本 ``data/samples/school_major_score.json`` 已含实例：
   河南/2025/本科批/物理类/560 分/101279 位次 出现两行，分别是
   ``major_code=14`` 公共管理类 与 ``major_code=12`` 国际商务），
   幂等键亦无法定义。``exam_system`` 是 ③ §2.3 的硬要求：
   老高考「文理科」与新高考「3+1+2」不得跨制度比较。

⚠️ SQLite 不能 ALTER COLUMN，放宽 NOT NULL 必须 batch 重建表。
本次用 ``copy_from`` 逐字复刻原表结构（含命名约定下的 CHECK / FK / 索引），
不依赖 reflection——Reflection 不会带回 CHECK 约束，会静默丢失年份与分数区间护栏。

⚠️ ``downgrade`` 会**删除**填不满 NOT NULL 的行（即院校改名未挂上的那些），
属有意为之的破坏性回滚，已在此显式说明。

Revision ID: 0009_school_major_score_identity
Revises: 0008_score_segment_batch
Create Date: 2026-10-13 17:55:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.db.base import NAMING_CONVENTION

revision = '0009_school_major_score_identity'
down_revision = '0008_score_segment_batch'
branch_labels = None
depends_on = None

# 复刻 0009 之前的 school_major_score（与 0002 建表结果一致，含约束命名约定）
_OLD_TABLE = sa.Table(
    'school_major_score',
    sa.MetaData(naming_convention=NAMING_CONVENTION),
    sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column('school_id', sa.Integer(), sa.ForeignKey('school.id'), nullable=False),
    sa.Column('major_id', sa.Integer(), sa.ForeignKey('major.id'), nullable=False),
    sa.Column('province', sa.String(length=20), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('batch', sa.String(length=32), nullable=False),
    sa.Column('pathway_id', sa.String(length=32), sa.ForeignKey('pathway.id'), nullable=True),
    sa.Column('subject_type', sa.String(length=20), nullable=False),
    sa.Column('min_score', sa.Integer(), nullable=True),
    sa.Column('min_rank', sa.Integer(), nullable=True),
    sa.Column('avg_score', sa.Integer(), nullable=True),
    sa.Column('plan_count', sa.Integer(), nullable=True),
    sa.Column('source_id', sa.Integer(), sa.ForeignKey('source.id'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint('year BETWEEN 2000 AND 2100', name='year_range'),
    sa.CheckConstraint(
        'min_score IS NULL OR (min_score BETWEEN 0 AND 750)', name='min_score_range'
    ),
    sa.Index('ix_school_major_score_lookup', 'province', 'year', 'batch', 'pathway_id'),
    sa.Index('ix_school_major_score_school_id', 'school_id'),
    sa.Index('ix_school_major_score_major_id', 'major_id'),
)

# 新增的身份列：NOT NULL，SQLite 要求带 server_default
_NEW_COLUMNS = (
    ('group_code', sa.String(length=32), '院校专业组代号（③ 已做括号归一化）'),
    ('major_code', sa.String(length=32), '专业代号；将来据此挂 major_id'),
    ('major_name', sa.String(length=200), '专业名称'),
    ('exam_system', sa.String(length=16), '考试制度：文理科 / 3+1+2'),
)


def upgrade() -> None:
    with op.batch_alter_table('school_major_score', copy_from=_OLD_TABLE) as batch_op:
        batch_op.alter_column('school_id', existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column('major_id', existing_type=sa.Integer(), nullable=True)

    for name, type_, comment in _NEW_COLUMNS:
        op.add_column(
            'school_major_score',
            sa.Column(name, type_, nullable=False, server_default='', comment=comment),
        )

    op.create_index(
        'ix_school_major_score_identity',
        'school_major_score',
        ['school_id', 'province', 'year', 'batch', 'subject_type', 'group_code', 'major_code'],
    )


def downgrade() -> None:
    op.drop_index('ix_school_major_score_identity', table_name='school_major_score')
    for name, _type, _comment in reversed(_NEW_COLUMNS):
        op.drop_column('school_major_score', name)

    # 重建为 NOT NULL 前，必须先清掉无法满足的行（不可避免的有损回滚）
    op.execute("DELETE FROM school_major_score WHERE school_id IS NULL OR major_id IS NULL")

    with op.batch_alter_table('school_major_score', copy_from=_OLD_TABLE) as batch_op:
        batch_op.alter_column('school_id', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('major_id', existing_type=sa.Integer(), nullable=False)
