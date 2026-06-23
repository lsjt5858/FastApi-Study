"""博客项目的内存数据层。

task-1~10 阶段用模块级 list/dict 模拟数据库；
task-11 会替换为 SQLAlchemy，但本模块继续作为初始 seed 数据来源。

放在独立模块（而不是 main.py）的原因：避免与 core/deps.py 形成循环 import。
"""

from __future__ import annotations

# 内部作者（含 password，仅用于演示 AuthorOut 的过滤效果）
INTERNAL_AUTHOR_ALICE: dict = {
    "id": 1,
    "username": "alice",
    "display_name": "Alice",
    "password": "super-secret-hash",  # 内部字段，绝不能出现在响应
    "email": "alice@internal.local",
    "is_active": True,
    "role": "author",
}

POSTS: list[dict] = [
    {
        "id": i,
        "title": f"Post {i}",
        "content": f"Content of post {i}.",
        "published": True,
        "status": "published",
        "tags": ["py"],
        "metadata": None,
        "is_deleted": False,
        "author": INTERNAL_AUTHOR_ALICE if i % 3 == 1 else None,
    }
    for i in range(1, 13)
] + [
    {
        "id": 13,
        "title": "Draft Post",
        "content": "A draft.",
        "published": False,
        "status": "draft",
        "tags": [],
        "metadata": None,
        "is_deleted": False,
        "author": None,
    },
    {
        "id": 14,
        "title": "Archived Post",
        "content": "An archived post.",
        "published": False,
        "status": "archived",
        "tags": [],
        "metadata": None,
        "is_deleted": True,  # 内部状态：归档且软删除
        "author": None,
    },
    {
        "id": 15,
        "title": "Hidden Post",
        "content": "Unpublished.",
        "published": False,
        "status": "draft",
        "tags": [],
        "metadata": None,
        "is_deleted": False,
        "author": None,
    },
]

USERS: list[dict] = [
    {"username": "alice", "display_name": "Alice"},
    {"username": "bob", "display_name": "Bob"},
]
