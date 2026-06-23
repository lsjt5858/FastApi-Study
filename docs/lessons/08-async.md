# 第 8 课 · async/await 异步编程

> 难度：【进阶】为主。
>
> 学完本节，你能用 `asyncio.gather` 并发聚合多个外部服务、用 `return_exceptions=True` 做异常隔离、用 `asyncio.wait_for` 加超时、用 `run_in_executor` 把阻塞任务扔线程池、用 `async def` 依赖（包括 async generator 的 setup/teardown）。

---

## 8.1 【新手】为什么 FastAPI 是异步的

FastAPI 基于 Starlette/AnyIO，整个请求生命周期在一个事件循环（event loop）里跑。一条路由可以声明为 `async def`，里面用 `await` 让出 CPU，让其他请求继续跑。

**关键区别**：

| 写法 | 行为 |
|---|---|
| `def f(): ...`（同步路由） | FastAPI 把它扔进线程池跑，不会阻塞事件循环 |
| `async def f(): ...`（异步路由） | 直接在事件循环里跑；如果里面写 `time.sleep(...)` 或同步 IO，**会阻塞整个 worker** |

> 经验：路由声明 `async def` 之后，**所有 IO 必须用 await 版本**（`asyncio.sleep` / `httpx.AsyncClient` / `asyncpg` 等），不然比同步路由更糟。

---

## 8.2 【进阶】asyncio.gather：并发聚合

`asyncio.gather(*aws)` 把多个 awaitable 并发跑，等所有完成，按提交顺序返回结果列表：

```python
async def aggregate_with_gather(post_id: int):
    start = time.monotonic()
    views, comments, likes = await asyncio.gather(
        fetch_views(post_id),
        fetch_comments(post_id),
        fetch_likes(post_id),
    )
    elapsed_ms = (time.monotonic() - start) * 1000
    return views, comments, likes, elapsed_ms
```

**耗时 = max（每个任务耗时）**，不是 sum。本课演示的接口 `/stats/aggregate/{id}` 实测 ≈ 52ms，而同步版 `/stats/aggregate-sync/{id}` ≈ 150ms（3 倍差距）。

---

## 8.3 【进阶】return_exceptions=True：异常隔离

默认情况下，`gather` 里任何一个任务抛异常，整个 `gather` 就会 raise。如果想让**单个失败不影响整体**，加 `return_exceptions=True`：

```python
return await asyncio.gather(
    fetch_views(post_id),
    fetch_unstable(post_id),  # 永远抛 RuntimeError
    fetch_likes(post_id),
    return_exceptions=True,
)
# 结果：[1234, RuntimeError(...), 789]
```

异常会作为对象（而不是 raise）放进结果列表里。消费者拿到结果后用 `isinstance(r, Exception)` 过滤即可。

---

## 8.4 【进阶】asyncio.wait_for：超时控制

```python
try:
    result = await asyncio.wait_for(slow_coroutine(), timeout=0.5)
except asyncio.TimeoutError:
    # 超时后 slow_coroutine 会被取消
    ...
```

`wait_for` 超时会**取消**被包装的协程，并抛 `asyncio.TimeoutError`。生产里所有外部调用都应该套一层超时，否则一个慢服务能把整个接口拖死。

---

## 8.5 【进阶】async def 依赖

FastAPI 完全支持 `async def` 依赖：

```python
async def get_async_client() -> dict:
    return {"client": "async-httpx-client"}

@app.get("/stats/async-dep")
async def stats_async_dep(client: Annotated[dict, Depends(get_async_client)]):
    return {"client": client["client"]}
```

依赖是 async 还是 sync，对消费方完全透明，FastAPI 会自动选择正确的调度方式。

---

## 8.6 【进阶】async generator 依赖：setup + teardown

这是 task-6 讲过的 yield 依赖的 async 版本：

```python
async def async_resource():
    state = {"entered": True, "exited": False}
    try:
        yield state                       # ← setup 完毕，把 state 交给路由
    finally:
        state["exited"] = True             # ← 路由返回后才执行 teardown
```

**关键陷阱**：`finally` 在响应序列化**之后**才跑，所以路由返回时 `state["exited"]` 还是 `False`。要观察 teardown 是否真的执行了，必须从模块级 side-effect（如 `_CTX_EVENTS` 列表）里读，不能只看响应体。

> 不要把 `@contextlib.asynccontextmanager` 装饰的函数直接当 FastAPI 依赖用。装饰后的对象是 `_AsyncGeneratorContextManager`，FastAPI 不会进入 context。直接写 async generator 函数即可。

---

## 8.7 【进阶】run_in_executor：阻塞任务兜底

如果遇到改不掉的同步阻塞代码（pandas 重计算、同步 SDK），不要在 async 路由里直接调，而是委托线程池：

```python
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, blocking_cpu_task, n)
```

`None` 表示用默认 `ThreadPoolExecutor`。也可以传自定义 executor（CPU 密集场景用 `ProcessPoolExecutor`）。

---

## 8.8 思考题

1. 如果在 async 路由里直接 `time.sleep(1)`，对一个并发 10 的压测会有什么影响？
2. `gather(*aws)` 与 `asyncio.TaskGroup`（3.11+）有什么区别？哪个更适合新代码？
3. async generator 依赖的 `finally` 真的总会跑吗？如果路由抛异常呢？

---

## 8.9 本节交付物

| 文件 | 作用 |
|---|---|
| `app/services/external.py` | 模拟外部服务：fetch_views/comments/likes/unstable + blocking_cpu_task |
| `app/services/stats.py` | `aggregate_with_gather` / `aggregate_with_return_exceptions` |
| `app/main.py` | 新增 `/stats/aggregate`、`/stats/aggregate-sync`、`/stats/async-dep`、`/stats/trigger-background`、`/stats/blocking-via-executor`、`/stats/with-ctx` |
| `tests/test_08_async.py` | 8 条测试 |
| `docs/lessons/08-async.md` | 本文 |

---

## 8.10 下一节预告

第 9 课我们引入 **Middleware 中间件**：CORS、计时中间件、请求 ID 注入，了解 Starlette 的 ASGI 协议在请求进/出两边能做什么。
