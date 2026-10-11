"""应用配置。

所有可调项集中从环境变量读取，代码里不硬编码地址与密钥。
环境变量样例见 backend/.env.example。
"""

from __future__ import annotations

import os

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    """运行时配置（进程启动时读取一次）。"""

    app_name: str = "智选志愿 API"
    version: str = "0.1.0"
    api_prefix: str = "/api"
    debug: bool = os.getenv("ZHIXUAN_DEBUG", "true").lower() == "true"
    cors_origins: list[str] = _split_csv(
        os.getenv("ZHIXUAN_CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    )


settings = Settings()
