# task-18 · Redis 缓存集成

> 数据库慢，缓存救场。但缓存一旦加错，会比没有更糟——缓存击穿、穿透、雪崩接踵而来。

## 【新手】为什么要缓存

`GET /db/posts` 每次都打数据库：
- 高 QPS 下 DB 连接池打满
- 慢查询拖垮整个服务
- 冷数据（很少变的列表）反复计算

Redis 是 in-memory KV 存储，单实例 QPS 轻松 10w+。把它放在 DB 前面做"读屏障"，DB 压力立刻下来一个数量级。

### Cache-Aside 模式（旁路缓存）

最常用的缓存模式，应用代码显式管理缓存：

```
读请求：
  ┌─ cache.get(key) ─→ HIT ─→ 返回缓存值
  │
  └─ MISS ─→ 查 DB ─→ cache.set(key, value, ttl) ─→ 返回

写请求（POST/PUT/DELETE）：
  └─ 写 DB ─→ cache.invalidate(key)   # 主动失效
```

## 【新手】redis-py 异步客户端

`redis-py` 4.x 之后原生支持 `asyncio`：

```python
import redis.asyncio as aioredis

client = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
await client.set("k", "v", ex=60)   # ex=过期秒数
val = await client.get("k")          # None 表示不存在
await client.delete("k")
async for key in client.scan_iter(match="post:list:*", count=100):
    ...
```

`decode_responses=True` 让返回值是 `str` 而不是 `bytes`，省心。

## 【进阶】缓存三大坑

### 坑 1：缓存击穿（dogpile / thundering herd）

某个热 key 同时过期，瞬间 N 个请求同时 miss → 全部打 DB。

**解法**：单飞锁（single-flight）

```python
async def db_list_posts(...):
    hit, cached = await cache_get(key)
    if hit:
        return cached

    lock = await get_single_flight_lock(key)
    async with lock:
        # 双检：拿锁后再查一次缓存，可能已被前一个请求填上
        hit, cached = await cache_get(key)
        if hit:
            return cached
        items = await db.query(...)
        await cache_set(key, items, ttl=60)
        return items
```

**为什么必须双检**：不双检的话，第 2 个拿到锁的人又会查一次 DB。

### 坑 2：缓存穿透

恶意请求构造**不存在的 key**（比如 `post:list:99999999`），缓存永远 miss，每次打 DB。

**解法**：空值也缓存

```python
items = await db.query(...)
await cache_set(key, items, ttl=60)   # 即使 items==[] 也存
```

短 TTL（60s）防止数据真的出现时被挡太久。

### 坑 3：缓存雪崩

大量 key 同时过期，DB 被瞬间压垮。**解法**：TTL 加随机抖动（`ttl + random(0, 30)`），本 task 暂未实现，思考题里讨论。

## 【进阶】主动失效（写时清缓存）

写操作必须清缓存，否则读到旧数据：

```python
@app.post("/db/posts")
async def create_post(...):
    post = await db_create(...)
    await cache_invalidate_pattern("post:list:*")  # 清所有列表缓存
    return post

@app.delete("/db/posts/{id}")
async def delete_post(...):
    await db_delete(...)
    await cache_invalidate_pattern("post:list:*")
```

为什么用 `pattern` 而不是精确 key？因为同一个资源在不同分页下有多个 key（`post:list:10:0`、`post:list:20:0`、`post:list:10:10`…），写操作影响所有分页，最简单的做法全清。

### 用 SCAN 不用 KEYS

```python
# ❌ 危险：KEYS 会阻塞 Redis 主线程
keys = await client.keys("post:list:*")

# ✅ 安全：SCAN 游标式扫描，单次 O(1)
async for key in client.scan_iter(match="post:list:*", count=100):
    await client.delete(key)
```

生产 Redis 千万级 key 上 `KEYS` 会让服务卡顿数秒。

## 【进阶】优雅降级

Redis 是旁路系统，**绝不能让 Redis 故障拖垮主流程**。所有缓存操作都要 try/except 吞掉异常：

```python
async def cache_get(key):
    try:
        client = await get_cache()
    except Exception:
        return False, None     # 降级到 DB
    if client is None:
        return False, None
    try:
        raw = await client.get(key)
    except Exception:
        logger.warning(...)
        return False, None     # 降级到 DB
    ...
```

测试时模拟 Redis 挂掉：

```python
async def _broken_get_cache():
    raise RuntimeError("redis down")

monkeypatch.setattr(cache_mod, "get_cache", _broken_get_cache)
# 接口仍返回 200，从 DB 拿数据
```

## 【进阶】缓存 Key 设计

```
post:list:{limit}:{offset}      # 列表
post:detail:{id}                # 详情
post:hot:daily                  # 热门（task-13）
user:{id}:posts                 # 用户文章
```

规则：
1. **业务前缀**：`post:` / `user:` / `comment:`，避免冲突
2. **操作类型**：`list` / `detail` / `count`
3. **参数后缀**：分页、过滤参数全部进 key

## 【进阶】fakeredis 做单测

跑单测时不必拉真 Redis——`fakeredis` 是 Redis 协议的纯 Python 实现，足够覆盖缓存逻辑：

```python
import fakeredis.aioredis

@pytest.fixture()
def cache_client(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    async def _fake_get_cache():
        return fake
    monkeypatch.setattr(cache_mod, "get_cache", _fake_get_cache)
    return fake
```

**注意**：fakeredis 验证的是"我们的缓存代码逻辑"，不是"Redis 本身"。生产用真 Redis 时仍有少量行为差异（持久化、主从、Cluster），需要 e2e 测试覆盖。

## 思考题

1. **TTL=60s 时 list 接口能容忍多少数据陈旧？** 如果业务要求强一致，是改 TTL 还是改失效策略？
2. **5 并发同 key 请求，单飞锁生效需要满足什么时序条件？** 如果 `db.query` 是 1ms 完成，单飞还有用吗？
3. **`cache_invalidate_pattern` 先于 `db.commit` 还是后于？** 谁先谁后会有什么问题？
4. **如果想给每个 key 的 TTL 加 ±10s 抖动（防雪崩），代码怎么改？**
5. **`scan_iter` 在大库上 count=100 vs count=10000，哪种更合适？** 提示：网络往返次数 vs 单次阻塞时间。

## 本次改动

- 新增 `app/services/cache.py`：`get_cache / cache_get / cache_set / cache_invalidate_pattern / get_single_flight_lock`
- 更新 `app/main.py`：
  - `GET /db/posts` 加 cache + 单飞锁 + 双检
  - `POST /db/posts` / `DELETE /db/posts/{id}` 触发 `cache_invalidate_pattern`
- 新增 `tests/test_18_cache.py`：8 条覆盖 miss/hit/失效/单飞/穿透/降级/TTL/键隔离
- `pyproject.toml` 依赖加 `redis` + `fakeredis`
