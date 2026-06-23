"""task-15：API 版本化路由（v1 / v2）。

v1 与 v2 共用同一份内存 POSTS 数据；v2 响应多了 publishedAt 字段（演示版本演进）。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.data import POSTS

v1_router = APIRouter(prefix="/api/v1", tags=["posts"])
v2_router = APIRouter(prefix="/api/v2", tags=["posts"])


def _post_to_v1(p: dict) -> dict:
    return {
        "id": p["id"],
        "title": p["title"],
        "content": p.get("content", ""),
    }


def _post_to_v2(p: dict) -> dict:
    return {
        "id": p["id"],
        "title": p["title"],
        "content": p.get("content", ""),
        "publishedAt": p.get("publishedAt", "2026-01-01T00:00:00Z"),
    }


@v1_router.get("/posts")
def v1_list_posts() -> list[dict]:
    return [_post_to_v1(p) for p in POSTS]


@v1_router.get("/posts/{post_id}")
def v1_get_post(post_id: int) -> dict:
    for p in POSTS:
        if p["id"] == post_id:
            return _post_to_v1(p)
    return {}


@v2_router.get("/posts")
def v2_list_posts() -> list[dict]:
    return [_post_to_v2(p) for p in POSTS]


@v2_router.get("/posts/{post_id}")
def v2_get_post(post_id: int) -> dict:
    for p in POSTS:
        if p["id"] == post_id:
            return _post_to_v2(p)
    return {}
