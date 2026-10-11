"""数据库引擎与会话（tasks.md 1.4）。

默认 SQLite：本地零安装即可跑通，且与 PostgreSQL 共用同一套 SQLAlchemy 2.0 模型与
Alembic 迁移；切换 PostgreSQL 只需设置 ZHIXUAN_DATABASE_URL（见 backend/.env.example）。

注意：启动时的 ``create_all`` 只负责"补齐缺失的表"，不会修改已存在表的结构。
所有结构变更（加字段、改类型、加索引）都必须写成 alembic 迁移。
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base

_SQLITE_PREFIX = "sqlite:///"


def sqlite_path(url: str) -> Path | None:
    """若为文件型 SQLite，返回其路径；内存库或非 SQLite 返回 None。"""
    if not url.startswith(_SQLITE_PREFIX):
        return None
    raw = url[len(_SQLITE_PREFIX) :]
    if not raw or raw.startswith(":memory:") or raw.startswith("file:"):
        return None
    return Path(raw)


def prepare_database() -> None:
    """SQLite 首次运行时创建数据库文件所在目录。"""
    path = sqlite_path(settings.database_url)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)


prepare_database()

_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：每个请求一个会话，请求结束即释放。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    """创建缺失的表（仅本地起步方便，结构变更请用 alembic）。"""
    from app import models  # noqa: F401  确保模型已注册到 Base.metadata

    Base.metadata.create_all(engine)


def drop_all() -> None:
    """删除全部表（仅测试使用）。"""
    from app import models  # noqa: F401

    Base.metadata.drop_all(engine)
