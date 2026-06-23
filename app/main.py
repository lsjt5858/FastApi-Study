"""Blog API — task-2 阶段：路径参数、查询参数与枚举。

在 task-1 骨架基础上扩展：
1. POSTS 数据加 status / published 字段，并扩到 15 条
2. GET /posts（list_posts）支持 limit/offset/published/status 查询参数
3. GET /users/{username} 演示 str 路径参数

后续 task 会继续在此基础上扩展（POST /posts、文件上传、依赖注入等）。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, HTTPException, Query

from app.schemas.enums import PostStatus
from app.schemas.post import PostCreate

app = FastAPI(
    title="Blog API",
    version="0.1.0",
    description="Python FastAPI 从入门到精通（博客渐进式实战）",
)

# task-2 阶段：扩展到 15 条，带 status / published 字段
POSTS: list[dict] = [
    {
        "id": i,
        "title": f"Post {i}",
        "content": f"Content of post {i}.",
        "published": True,
        "status": "published",
    }
    for i in range(1, 13)
] + [
    {"id": 13, "title": "Draft Post", "content": "A draft.", "published": False, "status": "draft"},
    {
        "id": 14,
        "title": "Archived Post",
        "content": "An archived post.",
        "published": False,
        "status": "archived",
    },
    {
        "id": 15,
        "title": "Hidden Post",
        "content": "Unpublished.",
        "published": False,
        "status": "draft",
    },
]

USERS: list[dict] = [
    {"username": "alice", "display_name": "Alice"},
    {"username": "bob", "display_name": "Bob"},
]


@app.get("/")
def root() -> dict:
    """根路径，返回博客基本信息与文档入口。"""
    return {
        "name": app.title,
        "version": app.version,
        "docs_url": "/docs",
    }


@app.get("/health")
def health() -> dict:
    """健康检查端点。"""
    return {"status": "ok"}


@app.get("/posts")
def list_posts(
    limit: Annotated[int, Query(ge=1, le=100, description="每页条数，1~100")] = 10,
    offset: Annotated[int, Query(ge=0, description="偏移量，>=0")] = 0,
    published: Annotated[bool | None, Query(description="按 published 过滤")] = None,
    status: Annotated[PostStatus | None, Query(description="按 status 枚举过滤")] = None,
) -> list[dict]:
    """文章列表：支持分页与按 published / status 过滤。"""
    items = POSTS
    if published is not None:
        items = [p for p in items if p.get("published") == published]
    if status is not None:
        items = [p for p in items if p.get("status") == status.value]
    return items[offset : offset + limit]


@app.get("/posts/{post_id}")
def get_post(post_id: int) -> dict:
    """按 id 获取单篇文章；post_id 必须是 int，否则 422。"""
    for post in POSTS:
        if post["id"] == post_id:
            return post
    raise HTTPException(status_code=404, detail="Post not found")


@app.post("/posts", status_code=201)
def create_post(payload: PostCreate) -> dict:
    """创建文章。task-3 阶段仅写入内存 POSTS。

    后续 task 会：
    - task-5 用 response_model=PostOut 过滤敏感字段
    - task-6 加依赖注入（当前作者）
    - task-11 替换内存 POSTS 为 SQLAlchemy
    """
    new_id = (max(p["id"] for p in POSTS) + 1) if POSTS else 1
    post = {"id": new_id, **payload.model_dump(by_alias=False)}
    POSTS.append(post)
    return post


@app.get("/users/{username}")
def get_user(username: str) -> dict:
    """按 username 获取作者（演示 str 路径参数）。"""
    for u in USERS:
        if u["username"] == username:
            return u
    raise HTTPException(status_code=404, detail="User not found")
