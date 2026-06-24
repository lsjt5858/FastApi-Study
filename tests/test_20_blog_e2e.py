"""task-20 测试：博客系统端到端（e2e）综合实战。

把前 19 个知识点串起来跑完整用户旅程。8 条核心场景对应 plan：
1. 注册 → 登录
2. 登录后发文章（含 Pydantic 校验 + 自动 slug + 标签去重）
3. 文章 404（POST_NOT_FOUND 结构）
4. 他人可评论（WebSocket 双客户端）
5. 评论触发 WebSocket 广播（多客户端同时收到）
6. 列表缓存命中（首次 miss → 二次 hit）
7. 统计接口聚合数据（views/comments/likes）
8. 管理员 scope 才能删除（无 token → 401，普通 → 403，admin → 204）

第 9 条是贯穿全程的综合旅程，进一步把知识点串起来验证不回归。

fixture：每个测试独立的 in-memory sqlite + fakeredis 缓存。
"""

from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base, get_async_db


@pytest.fixture()
def e2e_client(monkeypatch):
    """综合 e2e fixture：每个测试独立的 in-memory sqlite + fakeredis 缓存。

    - fakeredis 替换 redis 客户端，避免依赖真实 redis-server
    - 重置缓存模块的单例 / 单飞锁，防止跨测试污染
    - dependency_overrides 把 get_async_db 换到内存引擎
    """
    import app.services.cache as cache_mod

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def _fake_get_cache():
        return fake

    monkeypatch.setattr(cache_mod, "get_cache", _fake_get_cache)
    monkeypatch.setattr(cache_mod, "_client", None)
    cache_mod._single_flight_locks.clear()

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


# ----------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------


def _register(client, username="alice", password="pass1234", email=None):
    return client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email or f"{username}@x.com",
            "password": password,
        },
    )


def _login(client, username="alice", password="pass1234"):
    return client.post(
        "/auth/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def _mint_admin_token(subject="admin-1"):
    """生成一个 admin scope 的 JWT。

    task-20 新增：require_admin 依赖校验 scope 字段。
    直接 mint 一个含 scope=admin 的 token，绕开注册流程。
    """
    from app.core.config import settings
    from app.core.security import create_access_token

    return create_access_token(
        subject=subject,
        expires_minutes=60,
        secret=settings.SECRET_KEY.get_secret_value(),
        extra={"scope": "admin"},
    )


def _patch_list_calls(monkeypatch):
    """记录真实 crud_list_posts 被调用了多少次（用于断言缓存命中）。"""
    import app.crud as crud_mod
    import app.main as main_mod

    calls = {"n": 0}
    real = crud_mod.list_posts

    async def _wrapped(db, *, limit=10, offset=0):
        calls["n"] += 1
        return await real(db, limit=limit, offset=offset)

    monkeypatch.setattr(main_mod, "crud_list_posts", _wrapped)
    return calls


# ----------------------------------------------------------------------
# 8 + 1 条 e2e 测试
# ----------------------------------------------------------------------


def test_e2e_register_then_login(e2e_client) -> None:
    """1. 注册 → 登录：注册 201，登录 200 + access_token。"""
    r = _register(e2e_client, username="alice", password="pass1234")
    assert r.status_code == 201, r.text

    login = _login(e2e_client, username="alice", password="pass1234")
    assert login.status_code == 200, login.text
    body = login.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 10


def test_e2e_create_post_after_login(e2e_client) -> None:
    """2. 登录后发文章：title strip / tags 去重小写 / slug 自动生成。"""
    _register(e2e_client, username="bob", password="pass1234")
    token = _login(e2e_client, username="bob", password="pass1234").json()["access_token"]

    r = e2e_client.post(
        "/db/posts",
        json={
            "title": "  My First Post  ",
            "content": "Hello world",
            "tags": ["Python", "python", "FastAPI"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == "My First Post"
    assert body["slug"] == "my-first-post"


def test_e2e_get_unknown_post_404(e2e_client) -> None:
    """3. 文章 404：未知 ID 返回 404 + POST_NOT_FOUND 业务错误结构。"""
    r = e2e_client.get("/db/posts/999999")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == "POST_NOT_FOUND"


def test_e2e_others_can_comment_via_websocket(e2e_client) -> None:
    """4. 他人可评论：A 发评论，B（其他客户端）能收到。"""
    create = e2e_client.post(
        "/db/posts",
        json={"title": "WS Room", "content": "room body"},
    )
    post_id = create.json()["id"]

    with e2e_client.websocket_connect(f"/ws/posts/{post_id}/comments") as ws_a:
        with e2e_client.websocket_connect(f"/ws/posts/{post_id}/comments") as ws_b:
            ws_a.send_json({"type": "comment", "author": "alice", "text": "hi from a"})
            msg_b = ws_b.receive_json()
            assert msg_b["text"] == "hi from a"
            assert msg_b["author"] == "alice"


def test_e2e_comment_broadcasts_to_room(e2e_client) -> None:
    """5. 评论触发 WebSocket 广播：3 个客户端在房间，A 发 → 全收到。"""
    create = e2e_client.post(
        "/db/posts",
        json={"title": "Broadcast", "content": "bc body"},
    )
    post_id = create.json()["id"]

    with e2e_client.websocket_connect(f"/ws/posts/{post_id}/comments") as ws_a:
        with e2e_client.websocket_connect(f"/ws/posts/{post_id}/comments") as ws_b:
            with e2e_client.websocket_connect(f"/ws/posts/{post_id}/comments") as ws_c:
                ws_a.send_json({"type": "comment", "text": "broadcast-test"})
                msg_a = ws_a.receive_json()
                msg_b = ws_b.receive_json()
                msg_c = ws_c.receive_json()
                for m in (msg_a, msg_b, msg_c):
                    assert m["text"] == "broadcast-test"


def test_e2e_list_cache_hit(e2e_client, monkeypatch) -> None:
    """6. 列表缓存命中：首次 miss 查 DB，二次 hit 不查 DB。"""
    calls = _patch_list_calls(monkeypatch)
    e2e_client.post("/db/posts", json={"title": "cached-post", "content": "body"})

    r1 = e2e_client.get("/db/posts")
    assert r1.status_code == 200
    assert calls["n"] == 1, "首次应查 DB"

    r2 = e2e_client.get("/db/posts")
    assert r2.status_code == 200
    assert calls["n"] == 1, "二次应命中缓存"
    assert r1.json() == r2.json()


def test_e2e_stats_aggregate(e2e_client) -> None:
    """7. 统计接口聚合数据：返回 views/comments/likes/elapsed_ms。"""
    r = e2e_client.get("/stats/aggregate/42")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["post_id"] == 42
    for field in ("views", "comments", "likes", "elapsed_ms"):
        assert field in body, f"缺少聚合字段 {field}"


def test_e2e_admin_scope_required_to_delete(e2e_client) -> None:
    """8. 管理员 scope 才能删除：无 token → 401，普通用户 → 403，admin → 204。

    task-20 新增 DELETE /admin/posts/{post_id}：
    - require_admin 依赖解析 Authorization Bearer JWT 的 scope 字段
    - scope 不含 admin → 403；缺 token → 401；admin → 204
    """
    create = e2e_client.post(
        "/db/posts",
        json={"title": "to-delete", "content": "bye"},
    )
    post_id = create.json()["id"]

    # 8a. 无 token → 401
    r0 = e2e_client.delete(f"/admin/posts/{post_id}")
    assert r0.status_code == 401, r0.text

    # 8b. 普通用户 token（无 admin scope）→ 403
    _register(e2e_client, username="carol", password="pass1234")
    user_token = _login(e2e_client, username="carol", password="pass1234").json()["access_token"]
    r1 = e2e_client.delete(
        f"/admin/posts/{post_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r1.status_code == 403, r1.text

    # 8c. admin token → 204
    admin_token = _mint_admin_token()
    r2 = e2e_client.delete(
        f"/admin/posts/{post_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r2.status_code == 204, r2.text

    # 8d. 删完再查 → 404
    r3 = e2e_client.get(f"/db/posts/{post_id}")
    assert r3.status_code == 404


def test_e2e_full_user_journey(e2e_client, monkeypatch) -> None:
    """9. 综合旅程：注册→登录→发文章→缓存命中→统计→WS 评论→admin 删除。

    把前面 8 个场景串成一个连续流程，确保知识点协同工作不回归。
    """
    calls = _patch_list_calls(monkeypatch)

    # ① 注册 + 登录
    _register(e2e_client, username="dave", password="pass1234")
    token = _login(e2e_client, username="dave", password="pass1234").json()["access_token"]
    assert token

    # ② 发文章（带 token）
    create = e2e_client.post(
        "/db/posts",
        json={"title": "Journey Post", "content": "full e2e"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create.status_code == 201
    post_id = create.json()["id"]
    assert create.json()["slug"] == "journey-post"

    # ③ 列表缓存：第一次查 DB，第二次命中
    first = e2e_client.get("/db/posts")
    second = e2e_client.get("/db/posts")
    assert first.status_code == 200
    assert calls["n"] == 1, "二次查询应命中缓存，不回源 DB"
    assert first.json() == second.json()

    # ④ 统计聚合
    stats = e2e_client.get(f"/stats/aggregate/{post_id}").json()
    assert "views" in stats and "likes" in stats

    # ⑤ WebSocket 评论（本人也收到）
    with e2e_client.websocket_connect(f"/ws/posts/{post_id}/comments") as ws:
        ws.send_json({"type": "comment", "author": "dave", "text": "nice post"})
        msg = ws.receive_json()
        assert msg["text"] == "nice post"

    # ⑥ admin 删除
    admin_token = _mint_admin_token()
    r = e2e_client.delete(
        f"/admin/posts/{post_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204

    # ⑦ 删除后缓存应失效（再次 list 会回源，看到 post 已没了）
    post_list = e2e_client.get("/db/posts").json()
    assert all(p["id"] != post_id for p in post_list)
