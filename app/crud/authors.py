"""task-12：Author CRUD + 认证辅助。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models import Author


async def get_author_by_username(db: AsyncSession, username: str) -> Author | None:
    """按 username 查作者。"""
    result = await db.execute(select(Author).where(Author.username == username))
    return result.scalar_one_or_none()


async def get_author_by_id(db: AsyncSession, author_id: int) -> Author | None:
    """按 id 查作者。"""
    result = await db.execute(select(Author).where(Author.id == author_id))
    return result.scalar_one_or_none()


async def create_author(db: AsyncSession, username: str, email: str, password: str) -> Author:
    """创建作者；密码哈希存储。"""
    author = Author(
        username=username,
        email=email,
        hashed_password=hash_password(password),
    )
    db.add(author)
    await db.flush()
    return author


async def authenticate(db: AsyncSession, username: str, password: str) -> Author | None:
    """用户名/密码验证。返回 author 或 None。"""
    author = await get_author_by_username(db, username)
    if author is None:
        return None
    if not verify_password(password, author.hashed_password):
        return None
    return author
