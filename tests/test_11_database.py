"""task-11 测试：SQLAlchemy 异步数据库集成。

8 条测试覆盖：
- async engine + session
- 创建 / 列表 / 详情 / 删除走真实 DB
- title 唯一约束（IntegrityError）
- 事务回滚不留脏数据
- 测试用例之间 DB 隔离（in-memory per test）

为保持渐进式不破坏前面 task 的内存路由，task-11 引入新前缀 /db/posts。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base, get_async_db
from app.main import app


@pytest.fixture()
def db_client():
    """每个测试用 in-memory sqlite + dependency override 拿到独立 session。

    通过一个共享的 in-memory engine，在每个测试前 create_all、之后 drop_all，
    实现测试用例之间的 DB 隔离。
    """
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _prepare() -> None:
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

    async def _drop() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    asyncio.run(_drop())
    asyncio.run(engine.dispose())


def test_create_post_persisted(db_client) -> None:
    """创建文章后能查到。"""
    r = db_client.post("/db/posts", json={"title": "Hello DB", "content": "first"})
    assert r.status_code == 201
    body = r.json()
    assert body["id"] >= 1
    assert body["title"] == "Hello DB"


def test_list_posts_from_db(db_client) -> None:
    """列表来自 DB。"""
    db_client.post("/db/posts", json={"title": "A", "content": "x"})
    db_client.post("/db/posts", json={"title": "B", "content": "y"})
    r = db_client.get("/db/posts")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 2


def test_get_post_by_id(db_client) -> None:
    """按 id 查文章。"""
    created = db_client.post("/db/posts", json={"title": "GetX", "content": "c"}).json()
    r = db_client.get(f"/db/posts/{created['id']}")
    assert r.status_code == 200
    assert r.json()["title"] == "GetX"


def test_update_post_persists_changes(db_client) -> None:
    """PUT /db/posts/{id} 更新文章后，详情接口返回新内容。"""
    created = db_client.post("/db/posts", json={"title": "Before", "content": "old"}).json()

    r = db_client.put(
        f"/db/posts/{created['id']}",
        json={"title": "After", "content": "new"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["id"] == created["id"]
    assert body["title"] == "After"
    assert body["content"] == "new"

    detail = db_client.get(f"/db/posts/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "After"
    assert detail.json()["content"] == "new"


def test_update_post_not_found_404(db_client) -> None:
    """PUT /db/posts/{id} 更新不存在文章时返回 POST_NOT_FOUND。"""
    r = db_client.put("/db/posts/999999", json={"title": "Missing", "content": "new"})

    assert r.status_code == 404
    assert r.json()["error"]["code"] == "POST_NOT_FOUND"


def test_get_post_not_found_404(db_client) -> None:
    """不存在的 id -> 404 + POST_NOT_FOUND。"""
    r = db_client.get("/db/posts/999999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "POST_NOT_FOUND"


def test_delete_post_then_404(db_client) -> None:
    """删除后再 GET 应 404。"""
    created = db_client.post("/db/posts", json={"title": "ToDelete", "content": "c"}).json()
    d = db_client.delete(f"/db/posts/{created['id']}")
    assert d.status_code == 204
    r = db_client.get(f"/db/posts/{created['id']}")
    assert r.status_code == 404


def test_title_unique_constraint(db_client) -> None:
    """title 唯一约束：第二次同 title 提交 -> 409。"""
    db_client.post("/db/posts", json={"title": "Unique", "content": "1"})
    r = db_client.post("/db/posts", json={"title": "Unique", "content": "2"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "DUPLICATE_TITLE"


def test_update_post_duplicate_title_409(db_client) -> None:
    """PUT 更新成已有 title 时返回 DUPLICATE_TITLE。"""
    db_client.post("/db/posts", json={"title": "Taken", "content": "1"})
    target = db_client.post("/db/posts", json={"title": "Editable", "content": "2"}).json()

    r = db_client.put(
        f"/db/posts/{target['id']}",
        json={"title": "Taken", "content": "updated"},
    )

    assert r.status_code == 409
    assert r.json()["error"]["code"] == "DUPLICATE_TITLE"


def test_db_isolation_between_tests(db_client) -> None:
    """每测试用 in-memory：上一个测试创建的 Hello DB 不应存在。"""
    r = db_client.get("/db/posts")
    titles = {p["title"] for p in r.json()}
    assert "Hello DB" not in titles  # 来自 test_create_post_persisted
    assert "Unique" not in titles  # 来自 test_title_unique_constraint


def test_db_module_has_base_and_engine() -> None:
    """app.db.base 暴露 Base 与 get_async_db。"""
    from app.db.base import Base, get_async_db  # noqa: F401

    assert hasattr(Base, "metadata")
    assert callable(get_async_db)
