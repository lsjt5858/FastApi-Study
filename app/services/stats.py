"""task-8 引入：异步聚合统计逻辑。

把多个外部服务调用并发起来，对比同步串行的差异。
"""

from __future__ import annotations

import asyncio
import time

from app.services.external import fetch_comments, fetch_likes, fetch_unstable, fetch_views


async def aggregate_with_gather(post_id: int) -> tuple[int, int, int, float]:
    """并发调用 3 个外部服务，返回 (views, comments, likes, elapsed_ms)。"""
    start = time.monotonic()
    views, comments, likes = await asyncio.gather(
        fetch_views(post_id),
        fetch_comments(post_id),
        fetch_likes(post_id),
    )
    elapsed_ms = (time.monotonic() - start) * 1000
    return views, comments, likes, elapsed_ms


async def aggregate_with_return_exceptions(post_id: int) -> list:
    """用 return_exceptions=True 让单个失败不影响整体。

    其中一个调用 fetch_unstable 永远抛异常，
    gather 会把异常作为对象放进结果列表，而不是 raise。
    """
    return await asyncio.gather(
        fetch_views(post_id),
        fetch_unstable(post_id),  # 这一个会失败
        fetch_likes(post_id),
        return_exceptions=True,
    )
