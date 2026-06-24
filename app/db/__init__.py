"""task-11 引入：SQLAlchemy 2.0 异步数据库基础设施。

设计：
- Base = DeclarativeBase，所有 model 继承它
- engine = async engine（由 settings.DATABASE_URL 决定）
- AsyncSessionLocal = async_sessionmaker
- get_async_db() = async generator 依赖（yield AsyncSession + 事务管理）
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL


class Base(DeclarativeBase):
    """所有 ORM model 的公共基类。"""

    pass


# echo=False：关闭 SQL 日志；test 用 in-memory 覆盖这个 engine。
# 连接串从 Settings 读取，Docker / CI / 本地 .env 可以切换 SQLite 或 PostgreSQL。
engine = create_async_engine(DATABASE_URL, echo=False, future=True)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_async_db() -> AsyncSession:
    """FastAPI 依赖：yield 一个 AsyncSession，请求结束自动 commit / rollback。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """开发时用：建表。生产环境用 alembic 迁移。

    必须先 import app.models 让 SQLAlchemy 把 model 注册到 Base.metadata。
    """
    import app.models  # noqa: F401  保证 model 注册到 metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
