"""task-11：Post 的 CRUD 操作。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Post


async def create_post(
    db: AsyncSession, title: str, content: str, author_id: int | None = None
) -> Post:
    """创建文章。title 重复时抛 IntegrityError（由路由捕获转 409）。"""
    post = Post(title=title, content=content, author_id=author_id)
    db.add(post)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise
    return post


async def list_posts(db: AsyncSession, limit: int = 100, offset: int = 0) -> list[Post]:
    """列表分页。"""
    result = await db.execute(select(Post).offset(offset).limit(limit))
    return list(result.scalars().all())


async def get_post(db: AsyncSession, post_id: int) -> Post | None:
    """按 id 查单条。"""
    result = await db.execute(select(Post).where(Post.id == post_id))
    return result.scalar_one_or_none()


async def delete_post(db: AsyncSession, post_id: int) -> bool:
    """删除；返回是否真的删了一条。"""
    post = await get_post(db, post_id)
    if post is None:
        return False
    await db.delete(post)
    await db.flush()
    return True
