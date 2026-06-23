"""task-13：APScheduler AsyncIOScheduler 集成 + lifespan hook。

通过 FastAPI 的 lifespan 协议在 startup 启动 scheduler、shutdown 关闭。
replace_existing=True 保证同 id 重复注册不抛错（幂等）。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.hot_posts import compute_hot_posts

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """获取全局 scheduler 单例。"""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


@asynccontextmanager
async def scheduler_lifespan(app) -> AsyncIterator[None]:  # noqa: ANN001
    """可被 FastAPI lifespan= 引用的 async context manager。

    startup: 注册 hot_posts job 并启动 scheduler。
    shutdown: 关闭 scheduler。
    """
    sched = get_scheduler()
    # 每 60 秒跑一次 compute_hot_posts；replace_existing 保证幂等
    sched.add_job(
        lambda: asyncio.ensure_future(compute_hot_posts()),
        trigger="interval",
        seconds=60,
        id="hot_posts",
        replace_existing=True,
    )
    sched.start()
    try:
        yield
    finally:
        sched.shutdown(wait=False)


def init_scheduler(app) -> None:  # noqa: ANN001
    """把 scheduler_lifespan 挂到 app 上。

    FastAPI < 0.93 用 @app.on_event("startup") / ("shutdown")；
    新版用 lifespan=contextmanager。这里走 lifespan 路径。
    """
    # 复合 lifespan：保留可能存在的旧 lifespan（这里没有，直接设）
    app.router.lifespan_context = scheduler_lifespan
