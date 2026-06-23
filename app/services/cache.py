"""task-18：Redis 缓存层。

提供：
- `get_cache()`：懒加载 redis.asyncio 客户端，不可用时返回 None（降级到 DB）
- `cache_get(key)` -> `(hit, value)`：get + json.loads；异常/miss 都返回 (False, None)
- `cache_set(key, value, ttl)`：set + json.dumps；异常吞掉返回 False
- `cache_invalidate_pattern(pattern)`：scan + del；用于 POST/DELETE 主动失效
- `get_single_flight_lock(key)`：每个 cache key 一把 asyncio.Lock，防缓存击穿

设计原则：
- 缓存层任何异常都不应让 HTTP 请求失败，统一降级到 DB
- 单飞：并发同 key 请求只触发一次 DB 回源
- 空值也缓存（防穿透）
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

# 模块级单例：第一次成功 ping 通后缓存住 client，之后所有请求复用
_client: aioredis.Redis | None = None
_init_lock = asyncio.Lock()

# 单飞锁字典：cache_key -> asyncio.Lock
# 防止 N 个并发请求同时打穿到 DB（缓存击穿 / dogpile）
_single_flight_locks: dict[str, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()

# 默认 TTL（秒）
DEFAULT_TTL = 60


async def get_cache() -> aioredis.Redis | None:
    """返回 Redis 客户端单例。

    - 已初始化 → 直接返回
    - 未初始化 → 加锁建连 + ping 验活；失败返回 None
    - 后续调用复用同一连接池
    """
    global _client
    if _client is not None:
        return _client
    async with _init_lock:
        if _client is not None:  # 双检
            return _client
        try:
            client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await client.ping()
            _client = client
            logger.info("Redis connected: %s", settings.REDIS_URL)
            return _client
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis unavailable, caching disabled: %s", exc)
            return None


async def cache_get(key: str) -> tuple[bool, Any]:
    """读取缓存。返回 (hit, value)。

    - Redis 不可用 / miss / 异常 → (False, None)
    - 命中 → (True, parsed_value)
    """
    try:
        client = await get_cache()
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_cache() raised in cache_get: %s", exc)
        return False, None
    if client is None:
        return False, None
    try:
        raw = await client.get(key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache_get(%s) failed: %s", key, exc)
        return False, None
    if raw is None:
        return False, None
    try:
        return True, json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("cache_get(%s) corrupt payload: %s", key, exc)
        return False, None


async def cache_set(key: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
    """写入缓存（带 TTL）。成功 True，否则 False。"""
    try:
        client = await get_cache()
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_cache() raised in cache_set: %s", exc)
        return False
    if client is None:
        return False
    try:
        await client.set(key, json.dumps(value), ex=ttl)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache_set(%s) failed: %s", key, exc)
        return False


async def cache_invalidate_pattern(pattern: str) -> int:
    """按 pattern 批量失效缓存。返回删除条数。

    用 SCAN 而不是 KEYS（避免大库阻塞 Redis）。
    """
    try:
        client = await get_cache()
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_cache() raised in cache_invalidate: %s", exc)
        return 0
    if client is None:
        return 0
    deleted = 0
    try:
        async for key in client.scan_iter(match=pattern, count=100):
            await client.delete(key)
            deleted += 1
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache_invalidate(%s) failed: %s", pattern, exc)
    return deleted


async def get_single_flight_lock(key: str) -> asyncio.Lock:
    """对每个 cache key 维护一把独立的 asyncio.Lock。

    场景：缓存刚过期，N 个并发请求同时发现 miss，会同时打 DB。
    用 Lock 保证只有一个请求回源 DB，其他人在锁后双检命中缓存。
    """
    async with _locks_guard:
        if key not in _single_flight_locks:
            _single_flight_locks[key] = asyncio.Lock()
        return _single_flight_locks[key]
