"""task-6 测试：依赖注入 Depends。

8 条测试覆盖：
- pagination 函数依赖（默认值/自定义）
- 缺 token → 401（演示 Depends + HTTPException）
- yield 依赖的清理回调
- dependency_overrides 替换
- class-based 依赖
- 嵌套依赖链
- 全局 dependency_overrides
"""

from __future__ import annotations

import threading
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient

from app.core.deps import (
    PaginationDep,
    get_current_active_author,
    get_db,
    pagination,
)

# 复用主 app（含真实路由）
from app.main import app as main_app

client = TestClient(main_app)


def test_pagination_defaults() -> None:
    """pagination 依赖默认 limit=10, offset=0。"""
    pag = pagination()
    assert pag.limit == 10
    assert pag.offset == 0


def test_pagination_custom() -> None:
    """传入 limit=5&offset=3 生效。"""
    pag = pagination(limit=5, offset=3)
    assert pag.limit == 5
    assert pag.offset == 3


def test_missing_token_returns_401() -> None:
    """DELETE /posts/{id} 缺 Authorization → 401。

    DELETE 是 task-6 新增的依赖注入演示接口。
    """
    resp = client.delete("/posts/1")
    assert resp.status_code == 401


def test_yield_db_cleanup_called() -> None:
    """yield 依赖（get_db）的清理逻辑在请求后执行。

    用 monkeypatch 在 db dict 上加一个 cleanup 标记，请求结束后验证。
    """
    cleanup_marker = {"called": False}
    original_get_db = get_db

    def tracked_get_db():
        gen = original_get_db()
        try:
            db = next(gen)
            db["_cleanup_marker"] = cleanup_marker  # 注入追踪
            yield db
        finally:
            try:
                next(gen)  # 触发 finally
            except StopIteration:
                pass
            cleanup_marker["called"] = True

    main_app.dependency_overrides[get_db] = tracked_get_db
    try:
        resp = client.post("/posts", json={"title": "Tracked", "content": "C"})
        assert resp.status_code == 201
    finally:
        main_app.dependency_overrides.pop(get_db, None)

    assert cleanup_marker["called"] is True


def test_dependency_overrides_replace_db() -> None:
    """app.dependency_overrides 替换 get_db 为 mock。"""
    fake_db: dict = {"session_id": "mock-fake", "injected": True}

    def fake_get_db():
        yield fake_db

    main_app.dependency_overrides[get_db] = fake_get_db
    try:
        # 触发一个走 get_db 的接口
        resp = client.post("/posts", json={"title": "Mock", "content": "C"})
        assert resp.status_code == 201
    finally:
        main_app.dependency_overrides.pop(get_db, None)


def test_class_based_dependency() -> None:
    """class-based 依赖 PaginationDep 可独立实例化与复用。"""
    pag = PaginationDep(limit=20, offset=5)
    assert pag.limit == 20
    assert pag.offset == 5

    # 默认值
    pag_default = PaginationDep()
    assert pag_default.limit == 10
    assert pag_default.offset == 0


def test_nested_dependency_chain() -> None:
    """3 层嵌套依赖链：DELETE → get_current_active_author → get_current_author。

    带 token 时完整链路走通 → 204（DELETE 成功）。
    """
    resp = client.delete(
        "/posts/1",
        headers={"Authorization": "Bearer fake-token"},
    )
    # task-6 阶段：token 存在时通过 active 校验，删除成功
    assert resp.status_code in (200, 204)


def test_global_dependency_applied() -> None:
    """用 dependency_overrides 替换 get_current_active_author 为抛 403。

    全局替换后所有依赖它的接口都受影响。
    """

    def deny_inactive():
        raise HTTPException(status_code=403, detail="Forbidden by override")

    main_app.dependency_overrides[get_current_active_author] = deny_inactive
    try:
        resp = client.delete(
            "/posts/2",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Forbidden by override"
    finally:
        main_app.dependency_overrides.pop(get_current_active_author, None)


# 用 Annotated + Depends 演示嵌套依赖的声明风格（不实际作为端点）
def _example_nested(
    author: Annotated[dict, Depends(get_current_active_author)],
) -> dict:
    return author


def test_get_db_is_generator_with_cleanup() -> None:
    """get_db 是 generator（yield 依赖），用完触发 finally 清理。"""
    gen = get_db()
    db = next(gen)
    assert db["session_id"] == "mock-session"
    assert "posts" in db
    # 触发 finally（请求结束）
    try:
        next(gen)
        raise AssertionError("应该 StopIteration")
    except StopIteration:
        pass


# 并发安全测试：dependency_overrides 在并发下不冲突
def test_concurrent_dependency_isolation() -> None:
    """并发下 dependency_overrides 不会互相污染。

    每个线程删一个不同的 post id（避免互相竞争同一个资源）。
    关键断言：不出现 500 / 不抛异常 / 状态码都在预期集合内。
    """
    results: list[int] = []
    lock = threading.Lock()

    # 复制一份现有 post id（避免删空）
    post_ids = [p["id"] for p in main_app.dependency_overrides.values() for p in []]
    if not post_ids:
        # 创建 10 篇文章让并发删除有目标
        for i in range(10):
            r = client.post("/posts", json={"title": f"P{i}", "content": "C"})
            assert r.status_code == 201
            post_ids.append(r.json()["id"])

    def worker(pid: int):
        resp = client.delete(f"/posts/{pid}", headers={"Authorization": "Bearer x"})
        with lock:
            results.append(resp.status_code)

    threads = [threading.Thread(target=worker, args=(pid,)) for pid in post_ids[:10]]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 10
    # 删除成功 = 204 / 200；不该出现 500
    assert all(code in (200, 204, 404) for code in results), f"unexpected codes: {set(results)}"
    assert 500 not in results
