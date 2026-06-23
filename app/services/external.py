"""task-8 引入：模拟外部服务调用。

每个 fetch_* 函数模拟一次"耗时网络请求"，便于对比同步 vs 异步性能。
"""

from __future__ import annotations

import asyncio

# 模拟单个外部服务的延迟（秒）；保持小数字让测试快
EXTERNAL_LATENCY: float = 0.05


async def fetch_views(post_id: int) -> int:
    """模拟：拉取阅读量。"""
    await asyncio.sleep(EXTERNAL_LATENCY)
    return 1234


async def fetch_comments(post_id: int) -> int:
    """模拟：拉取评论数。"""
    await asyncio.sleep(EXTERNAL_LATENCY)
    return 56


async def fetch_likes(post_id: int) -> int:
    """模拟：拉取点赞数。"""
    await asyncio.sleep(EXTERNAL_LATENCY)
    return 789


async def fetch_unstable(post_id: int) -> int:
    """模拟：一个不稳定的服务，永远抛异常（用于演示 return_exceptions=True）。"""
    await asyncio.sleep(EXTERNAL_LATENCY)
    raise RuntimeError(f"unstable service failed for post {post_id}")


def blocking_cpu_task(n: int) -> int:
    """CPU 密集型任务：返回 1+2+...+n。

    在 async 路由里直接调它会阻塞事件循环，应该用 run_in_executor 委托线程池。
    """
    return n * (n + 1) // 2
