"""task-13：定时统计热门文章。

实际场景应查 DB 按 views/comments 排序写入 hot_posts 表。
本课用一个轻量函数演示可被 APScheduler 周期调起。
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def compute_hot_posts() -> dict:
    """定时任务：计算热门文章。

    生产代码会查 DB（select(Post).order_by(Post.views.desc()).limit(10)）。
    这里用 asyncio.sleep 模拟 IO，并打日志便于观测。
    """
    await asyncio.sleep(0.01)
    logger.info("compute_hot_posts: refreshed")
    return {"status": "ok", "top_count": 10}
