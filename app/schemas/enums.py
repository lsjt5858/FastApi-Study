"""task-2 引入：枚举类型。

PostStatus 用 str + Enum 双继承，原因：
1. FastAPI 拿到 URL/JSON 字符串后能直接构造 PostStatus(value)
2. OpenAPI 文档里会显示为枚举 schema，前端能直接看到允许值
"""

from __future__ import annotations

from enum import Enum


class PostStatus(str, Enum):
    """文章状态：草稿 / 已发布 / 已归档。"""

    draft = "draft"
    published = "published"
    archived = "archived"
