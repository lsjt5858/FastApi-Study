"""task-18 测试：Redis 缓存集成。

8 条覆盖：
- 首次查 DB（miss）
- 二次查缓存（hit）
- TTL 过期回源
- POST 主动失效
- 并发单飞（asyncio.Lock）
- 空值缓存防穿透
- 不同分页参数键隔离
- Redis 异常降级到 DB

用 fakeredis（FakeAsyncRedis）作为 Redis 协议的内存实现，避免依赖真实 redis-server。
"""

from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base, get_async_db


@pytest.fixture()
def cache_client(monkeypatch):
    """用 fakeredis 替换 cache.py 的 Redis 单例。"""
    import app.services.cache as cache_mod

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def _fake_get_cache():
        return fake

    monkeypatch.setattr(cache_mod, "get_cache", _fake_get_cache)
    # 重置内部单例，避免上一个 fixture 残留
    monkeypatch.setattr(cache_mod, "_client", None)
    return fake


@pytest.fixture()
def db_client(cache_client):
    """每次测试用独立 in-memory sqlite + fakeredis 缓存。"""
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

    from app.main import app

    app.dependency_overrides[get_async_db] = _override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def _create_post(client, title="hello", content="world") -> int:
    r = client.post("/db/posts", json={"title": title, "content": content})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ----------------------------------------------------------------------
# 用 monkeypatch crud_list_posts 的方式观察 DB 调用次数
# ----------------------------------------------------------------------


def _patch_list_calls(monkeypatch):
    """记录真实 crud_list_posts 被调用了多少次。"""
    import app.crud as crud_mod
    from app.main import app  # noqa: F401

    calls = {"n": 0}
    real = crud_mod.list_posts

    async def _wrapped(db, *, limit=10, offset=0):
        calls["n"] += 1
        return await real(db, limit=limit, offset=offset)

    # main.py 里是 `from app.crud import list_posts as crud_list_posts`
    # 所以 patch 的是 app.main 模块里的引用
    import app.main as main_mod

    monkeypatch.setattr(main_mod, "crud_list_posts", _wrapped)
    return calls


def test_first_call_hits_db_second_hits_cache(db_client, monkeypatch) -> None:
    """首次 miss 查 DB；二次 hit 不查 DB。"""
    calls = _patch_list_calls(monkeypatch)
    _create_post(db_client, title="cache-me")

    r1 = db_client.get("/db/posts")
    assert r1.status_code == 200
    assert calls["n"] == 1, "首次应查 DB"

    r2 = db_client.get("/db/posts")
    assert r2.status_code == 200
    assert calls["n"] == 1, "二次应命中缓存，不再查 DB"
    assert r1.json() == r2.json()


def test_invalidate_on_create(db_client, monkeypatch) -> None:
    """POST /db/posts 主动失效缓存：第二次 list 应看到新文章。"""
    calls = _patch_list_calls(monkeypatch)
    _create_post(db_client, title="before")

    db_client.get("/db/posts")
    assert calls["n"] == 1

    _create_post(db_client, title="after")  # 触发缓存失效

    r = db_client.get("/db/posts")
    assert calls["n"] == 2, "POST 后缓存失效，再次 list 应查 DB"
    titles = [p["title"] for p in r.json()]
    assert "before" in titles and "after" in titles


def test_different_pagination_keys_isolated(db_client, monkeypatch) -> None:
    """不同 limit/offset 用不同 cache key，互不影响。"""
    calls = _patch_list_calls(monkeypatch)
    for i in range(5):
        _create_post(db_client, title=f"p{i}")

    db_client.get("/db/posts?limit=2&offset=0")
    assert calls["n"] == 1
    db_client.get("/db/posts?limit=2&offset=0")  # 命中
    assert calls["n"] == 1
    db_client.get("/db/posts?limit=2&offset=2")  # 不同 key，miss
    assert calls["n"] == 2
    db_client.get("/db/posts?limit=2&offset=2")  # 命中
    assert calls["n"] == 2


def test_empty_result_is_cached(db_client, monkeypatch, cache_client) -> None:
    """空列表也缓存（防穿透）。"""
    calls = _patch_list_calls(monkeypatch)

    r1 = db_client.get("/db/posts?limit=10&offset=0")
    assert r1.json() == []
    assert calls["n"] == 1

    r2 = db_client.get("/db/posts?limit=10&offset=0")
    assert r2.json() == []
    assert calls["n"] == 1, "空值应被缓存，不回源"

    # 直接看 fakeredis 里有 key
    async def _scan():
        return [k async for k in cache_client.scan_iter(match="post:list:*")]

    keys = asyncio.run(_scan())
    assert len(keys) == 1


def test_concurrent_single_flight(db_client, monkeypatch, cache_client) -> None:
    """并发 N 个请求只触发 1 次 DB 查询（asyncio.Lock 单飞）。"""
    import app.crud as crud_mod
    import app.main as main_mod

    calls = {"n": 0}
    real = crud_mod.list_posts

    async def _slow(db, *, limit=10, offset=0):
        calls["n"] += 1
        await asyncio.sleep(0.05)  # 拉长窗口，让并发请求同时进来
        return await real(db, limit=limit, offset=offset)

    monkeypatch.setattr(main_mod, "crud_list_posts", _slow)
    _create_post(db_client, title="single-flight")

    # 用 raw TestClient 的异步底层不现实；改成顺序但验证锁存在
    # 用 httpx async client 直连 ASGI 验证并发
    import httpx

    from app.main import app as fastapi_app

    transport = httpx.ASGITransport(app=fastapi_app)

    async def _concurrent():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            tasks = [ac.get("/db/posts?limit=10&offset=0") for _ in range(5)]
            responses = await asyncio.gather(*tasks)
            return responses

    responses = asyncio.run(_concurrent())
    assert all(r.status_code == 200 for r in responses)
    assert calls["n"] == 1, f"5 并发应只查 1 次 DB，实际 {calls['n']}"


def test_redis_unavailable_degrades_to_db(db_client, monkeypatch) -> None:
    """Redis 异常时降级到 DB，不报错。"""
    import app.services.cache as cache_mod

    async def _broken_get_cache():
        raise RuntimeError("redis down")

    # get_cache 抛异常 → cache_get/cache_set 应吞掉并降级
    monkeypatch.setattr(cache_mod, "get_cache", _broken_get_cache)

    calls = _patch_list_calls(monkeypatch)
    _create_post(db_client, title="degrade")

    # 第一次：缓存层抛异常 → 降级查 DB
    r1 = db_client.get("/db/posts")
    assert r1.status_code == 200
    assert calls["n"] == 1

    # 第二次：还是走 DB（缓存全失败）
    r2 = db_client.get("/db/posts")
    assert r2.status_code == 200
    assert calls["n"] == 2


def test_ttl_expiry_re_queries(db_client, monkeypatch, cache_client) -> None:
    """TTL 过期后重新查 DB。"""
    calls = _patch_list_calls(monkeypatch)
    _create_post(db_client, title="ttl")

    db_client.get("/db/posts")
    assert calls["n"] == 1
    db_client.get("/db/posts")
    assert calls["n"] == 1, "TTL 内不回源"

    # 直接清空 fakeredis 模拟 TTL 过期
    await_sync = asyncio.run(cache_client.flushdb())
    assert await_sync is True or await_sync is None

    db_client.get("/db/posts")
    assert calls["n"] == 2, "TTL 过期后应回源"


def test_cache_returns_same_shape_as_db(db_client, monkeypatch) -> None:
    """缓存返回的数据结构与直查 DB 一致。"""
    _create_post(db_client, title="shape-check", content="body")

    direct = db_client.get("/db/posts").json()
    cached = db_client.get("/db/posts").json()

    assert direct == cached
    # 关键字段都在
    assert len(cached) >= 1
    item = cached[0]
    for k in ("id", "title", "content"):
        assert k in item
