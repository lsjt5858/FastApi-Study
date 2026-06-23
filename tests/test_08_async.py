"""task-8 测试：async/await 异步编程。

8 条测试覆盖：
- asyncio.gather 并发
- async vs sync 耗时对比
- 异常隔离 / 超时
- async 依赖 / async context manager
- BackgroundTasks / run_in_executor
"""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.external import blocking_cpu_task
from app.services.stats import aggregate_with_return_exceptions

client = TestClient(app)


def test_aggregate_returns_all_keys() -> None:
    """GET /stats/aggregate/{id} 返回 views/comments/likes。"""
    resp = client.get("/stats/aggregate/1")
    assert resp.status_code == 200
    body = resp.json()
    assert {"views", "comments", "likes", "elapsed_ms"}.issubset(body.keys())
    assert body["views"] > 0
    assert body["comments"] >= 0
    assert body["likes"] >= 0


def test_async_faster_than_sync() -> None:
    """async 接口耗时 ≈ max（≈0.05s）；sync 接口耗时 ≈ sum（≈0.15s）。

    断言 async 显著小于 sync。
    """
    t0 = time.monotonic()
    r_async = client.get("/stats/aggregate/1")
    t_async = time.monotonic() - t0
    assert r_async.status_code == 200

    t0 = time.monotonic()
    r_sync = client.get("/stats/aggregate-sync/1")
    t_sync = time.monotonic() - t0
    assert r_sync.status_code == 200

    # async 至少比 sync 快 2 倍以上（理论值 3 倍）
    assert t_async < t_sync * 0.7, f"async={t_async:.3f}s sync={t_sync:.3f}s"


def test_gather_handles_exception() -> None:
    """aggregate_with_return_exceptions: 一个服务抛异常仍返回其他结果。"""
    results = asyncio.run(aggregate_with_return_exceptions(1))
    assert len(results) == 3
    # 一个是 Exception 实例，另两个是 int
    exceptions = [r for r in results if isinstance(r, Exception)]
    ints = [r for r in results if isinstance(r, int)]
    assert len(exceptions) == 1
    assert len(ints) == 2
    # fetch_unstable 抛的是 RuntimeError
    assert isinstance(exceptions[0], RuntimeError)


async def test_timeout_with_wait_for() -> None:
    """asyncio.wait_for 超时抛 TimeoutError。"""
    await asyncio.wait_for(asyncio.sleep(0.01), timeout=0.05)

    async def slow() -> int:
        await asyncio.sleep(1.0)
        return 1

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow(), timeout=0.05)


def test_async_dependency() -> None:
    """async def get_async_client() 依赖：访问 /stats/async-dep 成功。"""
    resp = client.get("/stats/async-dep")
    assert resp.status_code == 200
    assert resp.json()["client"] == "async-httpx-client"


def test_background_tasks_with_async() -> None:
    """BackgroundTasks 与 async 路由配合。"""
    resp = client.post("/stats/trigger-background")
    assert resp.status_code == 202
    assert resp.json()["scheduled"] is True


def test_blocking_task_via_executor() -> None:
    """阻塞任务通过 run_in_executor 执行。"""
    # 通过接口触发
    resp = client.get("/stats/blocking-via-executor?n=10")
    assert resp.status_code == 200
    assert resp.json()["result"] == 55  # 1+2+...+10
    # 直接调用 blocking_cpu_task
    assert blocking_cpu_task(5) == 15


def test_async_context_manager_dependency() -> None:
    """async context manager 依赖。

    响应序列化在 yield 阶段（teardown 还没跑），所以响应体里 exited 必然是 False；
    要证明 teardown 真的跑了，看模块级 _CTX_EVENTS：应在请求结束后变成 ['entered','exited']。
    """
    from app.main import _CTX_EVENTS

    resp = client.get("/stats/with-ctx")
    assert resp.status_code == 200
    body = resp.json()
    assert body["entered"] is True
    # 响应体内 exited 必然是 False（teardown 在序列化之后）
    assert body["exited"] is False
    # 请求结束后 _CTX_EVENTS 应同时包含 entered 与 exited，证明 teardown 已执行
    assert _CTX_EVENTS == ["entered", "exited"]
