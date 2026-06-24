# task-18: 缓存集成 Redis

## 目标
为博客文章列表加 Redis 缓存：TTL=60s，主动失效，asyncio.Lock 单飞防击穿，空值缓存防穿透，缓存异常降级到 DB。

## 涉及文件
- `app/services/cache.py`（Redis 客户端 + 缓存装饰器）
- `app/api/routers/posts.py`（GET /posts 加缓存）
- `app/main.py`（lifespan 管理 redis 连接）
- `docs/lessons/18-cache.md`
- `tests/test_18_cache.py`

## 验收标准
- [ ] services/cache.py 用 redis-py 异步客户端
- [ ] GET /posts 命中缓存直接返回，否则查 DB 后回填 TTL=60s
- [ ] `POST /db/posts`、`PUT /db/posts/{id}`、`DELETE /db/posts/{id}` 触发缓存失效
- [ ] asyncio.Lock 单飞（并发只查 DB 一次）
- [ ] 空值缓存防穿透（不存在的 filter 也缓存空）
- [ ] 不同分页参数键名隔离
- [ ] Redis 异常降级到 DB 不报错
- [ ] 8 条测试全绿

## 测试点（至少 8 条）
1. `test_first_query_hits_db`：首次查询 DB 被调用
2. `test_second_query_hits_cache`：二次查询 DB 不被调用
3. `test_cache_ttl_expires`：TTL 过期回源
4. `test_cache_invalidated_on_write`：写入触发失效
5. `test_single_flight_under_concurrency`：并发请求只查 DB 一次
6. `test_null_value_cached`：空值缓存防穿透
7. `test_key_namespace_isolated`：不同 limit/offset 键名隔离
8. `test_redis_down_degrades_to_db`：Redis 异常时降级

## 实现要点
```python
# app/services/cache.py
import asyncio
import json
from redis import asyncio as aioredis
from app.core.config import settings

_redis: aioredis.Redis | None = None
_locks: dict[str, asyncio.Lock] = {}

async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL)
    return _redis

async def cached_or_set(key: str, loader, ttl: int = 60):
    redis = await get_redis()
    # 命中
    try:
        cached = await redis.get(key)
        if cached is not None:
            if cached == "__null__":
                return None
            return json.loads(cached)
    except Exception:
        return await loader()  # 降级

    # 单飞
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        # double-check
        cached = await redis.get(key)
        if cached is not None:
            return None if cached == "__null__" else json.loads(cached)
        data = await loader()
        try:
            await redis.set(key, json.dumps(data) if data is not None else "__null__", ex=ttl)
        except Exception:
            pass
        return data

async def invalidate(prefix: str):
    redis = await get_redis()
    try:
        async for k in redis.scan_iter(f"{prefix}*"):
            await redis.delete(k)
    except Exception:
        pass

# app/api/routers/posts.py
@router.get("/")
async def list_posts(
    limit: int = 10, offset: int = 0,
    db = Depends(get_db),
):
    key = f"posts:list:{limit}:{offset}"
    return await cached_or_set(
        key, lambda: crud_posts.list(db, limit, offset), ttl=60
    )

@router.post("/", response_model=PostOut, status_code=201)
async def create_post(...):
    post = await crud_posts.create(...)
    await invalidate("posts:list:")
    return post

@router.put("/{post_id}", response_model=PostOut)
async def update_post(...):
    post = await crud_posts.update(...)
    await invalidate("posts:list:")
    return post
```
- 测试用 `fakeredis` 替代真实 redis（`pip install fakeredis`）
- TTL 单位是秒

## 教学文档大纲
1. 【新手】为什么要缓存
2. 【新手】redis-py 异步基础
3. 【新手】TTL 与缓存键设计
4. 【进阶】缓存击穿与单飞（Lock）
5. 【进阶】缓存穿透与空值缓存
6. 【进阶】缓存雪崩与随机 TTL
7. 【进阶】缓存与一致性（旁路缓存 / 写穿 / 写回）
8. 思考题：缓存该在哪一层做（路由/Service/CRUD）？
