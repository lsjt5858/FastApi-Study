"""task-16：核心 fixture 体系（pytest）。

提供：
- db_factory：工厂，每次调用返回独立内存 sqlite engine
- db_client：用 dependency_overrides 把 app 的 get_async_db 换成内存版
- client：基础同步 TestClient（绑定内存 DB）
- async_client：httpx.AsyncClient + ASGITransport（绑定内存 DB）
- mock_email：替换 send_welcome_email，避免发邮件副作用
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base, get_async_db
from app.main import app


@pytest.fixture()
def db_factory() -> Iterator[Callable[[], object]]:
    """工厂 fixture：每次调用返回一个独立 in-memory engine。

    用法：
        engine_a = db_factory()
        engine_b = db_factory()
    """
    engines: list = []

    def _make():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

        async def _prepare() -> None:
            import app.models  # noqa: F401

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        asyncio.run(_prepare())
        engines.append((engine, TestSessionLocal))
        return engine

    yield _make

    # 清理所有 engine
    for engine, _ in engines:
        asyncio.run(engine.dispose())


def _override_factory(TestSessionLocal) -> Callable:
    """生成 get_async_db 的 override 闭包。"""

    async def _override() -> AsyncIterator[AsyncSession]:
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return _override


@pytest.fixture()
def db_client(db_factory) -> Iterator[TestClient]:
    """用 db_factory 装一个内存 DB，绑定到 app 的 get_async_db 上。"""
    engine = db_factory()
    TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    app.dependency_overrides[get_async_db] = _override_factory(TestSessionLocal)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# 别名：test_16 测试用 client 这个名字
@pytest.fixture()
def client(db_client) -> TestClient:
    """对 db_client 的别名，便于测试代码用 client。"""
    return db_client


@pytest.fixture()
def async_client(db_factory) -> AsyncClient:
    """httpx.AsyncClient + ASGITransport 测异步路径。"""
    engine = db_factory()
    TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    app.dependency_overrides[get_async_db] = _override_factory(TestSessionLocal)
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture()
def mock_email(monkeypatch):
    """用 monkeypatch + unittest.mock 替换 send_welcome_email，返回 Mock 对象。

    不依赖 pytest-mock 第三方包（教学项目想保持依赖最小）。
    """
    from unittest.mock import AsyncMock

    mock = AsyncMock(return_value=None)
    # 替换 app.main 里 import 进来的 send_welcome_email 引用
    import app.main

    monkeypatch.setattr(app.main, "send_welcome_email", mock)
    return mock
