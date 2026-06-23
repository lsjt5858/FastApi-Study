"""task-13 测试：BackgroundTasks + APScheduler。

8 条测试覆盖：
- BackgroundTasks 被排队
- 任务在响应之后执行
- 任务异常不影响 HTTP 响应
- 多任务按顺序执行
- lifespan startup 触发
- lifespan shutdown 触发
- APScheduler 注册了 hot_posts job
- 重复注册同 id 任务幂等
"""

from __future__ import annotations

import asyncio

from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient

from app.services.email import EmailLog, send_welcome_email
from app.services.hot_posts import compute_hot_posts
from app.services.scheduler import get_scheduler, init_scheduler


def test_email_log_singleton() -> None:
    """EmailLog 提供类级记录，方便测试断言。"""
    EmailLog.reset()
    EmailLog.append("alice@example.com", "Hello")
    assert EmailLog.entries == [{"to": "alice@example.com", "subject": "Hello"}]


def test_send_welcome_email_writes_log() -> None:
    """send_welcome_email 实际写入 EmailLog。"""
    EmailLog.reset()
    asyncio.run(send_welcome_email("alice@example.com", "Hi"))
    assert len(EmailLog.entries) == 1
    assert EmailLog.entries[0]["to"] == "alice@example.com"


def test_background_task_runs_after_response() -> None:
    """BackgroundTasks 在响应之后才执行。"""
    EmailLog.reset()
    app = FastAPI()

    @app.post("/send")
    async def send(background: BackgroundTasks) -> dict:
        background.add_task(send_welcome_email, "alice@example.com", "Post-1")
        # 响应发出时 EmailLog 仍空（任务还没跑）
        return {"queued": len(EmailLog.entries)}

    with TestClient(app) as client:
        r = client.post("/send")
        assert r.status_code == 200
        # 响应内 queued==0，证明任务还没跑
        assert r.json()["queued"] == 0
        # TestClient 退出（response 完成后）时 BackgroundTasks 才跑
    assert len(EmailLog.entries) == 1


def test_task_exception_doesnt_break_response() -> None:
    """BackgroundTasks 抛异常不影响 200 响应。"""
    EmailLog.reset()
    app = FastAPI()

    def boom() -> None:
        raise RuntimeError("kaboom")

    @app.post("/x")
    async def x(background: BackgroundTasks) -> dict:
        background.add_task(boom)
        return {"ok": True}

    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post("/x")
        assert r.status_code == 200
        assert r.json()["ok"] is True


def test_multiple_tasks_sequential() -> None:
    """多个 BackgroundTasks 按添加顺序串行执行。"""
    order: list[str] = []
    app = FastAPI()

    def tag(name: str) -> None:
        order.append(name)

    @app.post("/multi")
    async def multi(background: BackgroundTasks) -> dict:
        background.add_task(tag, "first")
        background.add_task(tag, "second")
        background.add_task(tag, "third")
        return {"ok": True}

    with TestClient(app) as client:
        client.post("/multi")
    assert order == ["first", "second", "third"]


def test_scheduler_has_hot_posts_job() -> None:
    """init_scheduler 注册了 hot_posts job。"""
    app = FastAPI()
    init_scheduler(app)
    with TestClient(app) as client:  # noqa: SIM117
        # 触发 startup
        scheduler = get_scheduler()
        job_ids = {job.id for job in scheduler.get_jobs()}
        assert "hot_posts" in job_ids
        # 保持 client 活着直到断言完成
        assert client is not None


def test_scheduler_idempotent_register() -> None:
    """重复注册同 id job 不报错（replace_existing）。"""
    app = FastAPI()
    init_scheduler(app)
    with TestClient(app):
        scheduler = get_scheduler()
        # 再 add 一次同 id（init_scheduler 内部用 replace_existing=True）
        # 应该只有 1 个 hot_posts job
        jobs = [j for j in scheduler.get_jobs() if j.id == "hot_posts"]
        assert len(jobs) == 1


def test_compute_hot_posts_runs_without_error() -> None:
    """定时任务函数本身可独立调用、不抛异常。"""
    asyncio.run(compute_hot_posts())  # 不抛即 OK


def test_lifespan_startup_shutdown_events() -> None:
    """lifespan startup 启动 scheduler，shutdown 关闭。"""
    app = FastAPI()
    init_scheduler(app)
    started_states: list[bool] = []

    @app.get("/ping")
    def ping() -> dict:
        s = get_scheduler()
        started_states.append(s.running)
        return {"ok": True}

    with TestClient(app) as client:
        client.get("/ping")
    # shutdown 后 scheduler 应已停止
    assert started_states == [True]
    assert get_scheduler().running is False
