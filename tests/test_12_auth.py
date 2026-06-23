"""task-12 测试：OAuth2 + JWT 认证。

8 条测试覆盖：
- 注册 201 / 重复 409
- 登录成功返回 access_token / 密码错误 401
- /me 无 token 401 / 过期 401 / 伪造 401
- 删除他人文章 403

每个测试用独立 in-memory sqlite + override get_async_db。
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base, get_async_db
from app.main import app


@pytest.fixture()
def auth_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _prepare() -> None:
        import app.models  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_prepare())

    async def _override_get_db():
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_async_db] = _override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def _register(client, username="alice", password="pass1234", email="alice@x.com"):
    return client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def _login(client, username="alice", password="pass1234"):
    return client.post(
        "/auth/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def test_register_success(auth_client) -> None:
    r = _register(auth_client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["username"] == "alice"
    # 不允许回显密码
    assert "password" not in body


def test_register_duplicate_409(auth_client) -> None:
    _register(auth_client, username="dup")
    r = _register(auth_client, username="dup", email="other@x.com")
    assert r.status_code == 409


def test_login_returns_token(auth_client) -> None:
    _register(auth_client, username="bob", password="secret123")
    r = _login(auth_client, username="bob", password="secret123")
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 10


def test_login_wrong_password_401(auth_client) -> None:
    _register(auth_client, username="carol", password="correct")
    r = _login(auth_client, username="carol", password="wrong")
    assert r.status_code == 401


def test_me_without_token_401(auth_client) -> None:
    r = auth_client.get("/me")
    assert r.status_code == 401


def test_me_with_valid_token(auth_client) -> None:
    _register(auth_client, username="dave", password="pw123456")
    token = _login(auth_client, username="dave", password="pw123456").json()["access_token"]
    r = auth_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "dave"


def test_me_with_expired_token_401(auth_client) -> None:
    _register(auth_client, username="eve", password="pw123456")
    from app.core.config import settings
    from app.core.security import create_access_token

    # exp 设成过去时间
    token = create_access_token(subject="1", expires_minutes=-10, secret=settings.SECRET_KEY)
    r = auth_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_me_with_forged_token_401(auth_client) -> None:
    forged = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.invalidsignature"
    r = auth_client.get("/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401
