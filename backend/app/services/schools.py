"""院校检索业务逻辑。

正式实现为多条件检索 + 分页与院校画像，见 tasks.md 7.1、7.2。
当前为演示实现：有关键词或省份时返回单条演示院校。
"""

from __future__ import annotations

from app.core.demo import demo_citation


def search_schools(keyword: str = "", province: str = "河南") -> list[dict[str, object]]:
    """按关键词与省份检索院校。"""
    if not keyword and not province:
        return []
    return [
        {
            "school_id": "mock-001",
            "name": "演示院校",
            "province": province,
            "citations": [demo_citation()],
            **demo_citation(),
        }
    ]
