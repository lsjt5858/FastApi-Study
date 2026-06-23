# 第 13 课 · 后台任务 BackgroundTasks 与定时任务

> 难度：【进阶】为主。
>
> 学完本节，你能用 FastAPI 的 `BackgroundTasks` 把"响应不需要的副作用"挪到响应之后执行、用 APScheduler 在 lifespan 里启动定时任务、区分 BackgroundTasks 与 Celery 的适用场景。

---

## 13.1 【新手】BackgroundTasks 适用场景

接口做完核心工作后，经常有"附属动作"：
- 发邮件
- 写日志/审计
- 推消息队列
- 刷新缓存

这些动作如果**串行同步执行**，会拖慢响应；如果**用 asyncio.create_task** 又不容易测、不容易等。

`BackgroundTasks` 是 Starlette 提供的轻量级方案：
- 路由声明 `background_tasks: BackgroundTasks` 依赖
- 调 `background_tasks.add_task(fn, *args)` 排队
- **响应发出之后**，Starlette 才依次 await 这些任务
- 任意任务抛异常不会影响已发出的响应

---

## 13.2 【新手】add_task + 依赖注入

```python
from fastapi import BackgroundTasks

@app.post("/db/posts", status_code=201)
async def db_create_post(
    payload: PostCreate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    background_tasks: BackgroundTasks,
):
    post = await crud_create_post(db, ...)
    background_tasks.add_task(send_welcome_email, "author@example.com", post.title)
    return post
```

`add_task` 接收：
- 同步函数 → 扔线程池跑
- 异步函数（`async def`）→ 在事件循环里跑

---

## 13.3 【进阶】任务执行时机（响应之后）

执行顺序：

1. 路由 return → FastAPI 序列化响应
2. 中间件链回到最外层
3. **响应发到客户端**
4. **此时 Starlette 才开始跑 BackgroundTasks**

所以路由里 `background_tasks.add_task(...)` 之后立刻读"任务副作用"（如写好的文件 / log），必然看不到。要验证副作用，得在 TestClient 退出（`with TestClient(app) as client:` 结束）之后才能查。

```python
def test_background_task_runs_after_response():
    with TestClient(app) as client:
        r = client.post("/send")
        assert r.json()["queued"] == 0   # 任务还没跑
    # with 块退出后 BackgroundTasks 才完成
    assert len(EmailLog.entries) == 1
```

---

## 13.4 【进阶】任务异常不影响响应

BackgroundTasks 内部 try/except 了所有任务，**单个任务抛异常不会传播给客户端**，响应已经是 200 就还是 200。

```python
def boom():
    raise RuntimeError("kaboom")

@app.post("/x")
async def x(background: BackgroundTasks):
    background.add_task(boom)
    return {"ok": True}   # ← 响应始终 200
```

但异常会被 Starlette log 出来（生产要监控）。

---

## 13.5 【进阶】APScheduler 集成

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

_scheduler = AsyncIOScheduler()

def get_scheduler() -> AsyncIOScheduler:
    return _scheduler

@asynccontextmanager
async def scheduler_lifespan(app):
    sched = get_scheduler()
    sched.add_job(
        lambda: asyncio.ensure_future(compute_hot_posts()),
        trigger="interval", seconds=60,
        id="hot_posts", replace_existing=True,
    )
    sched.start()
    try:
        yield
    finally:
        sched.shutdown(wait=False)

def init_scheduler(app):
    app.router.lifespan_context = scheduler_lifespan
```

`replace_existing=True` 让同 id job 重复注册不抛错（幂等）—— 防止 reload / 多 worker 启动时报错。

---

## 13.6 【进阶】lifespan 取代 on_event

FastAPI 0.93+ 推荐用 `lifespan` 替代 `@app.on_event("startup")`：

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # startup
    init_resources()
    yield
    # shutdown
    cleanup_resources()

app = FastAPI(lifespan=lifespan)
```

好处：
- startup 和 shutdown 写在一起，不会忘清理
- 可以做 try/finally 资源管理
- 支持多个 lifespan 复合（用 `asynccontextmanager` 链）

---

## 13.7 【进阶】Celery / Dramatiq 对比

| 方案 | 适用 | 缺点 |
|---|---|---|
| BackgroundTasks | 单进程、轻量、短任务（<几秒） | 重启进程会丢任务、不能分布式 |
| APScheduler | 单进程定时任务 | 同上 |
| Celery | 分布式、长任务、可重试 | 配置重（broker + worker） |
| Dramatiq | 同 Celery 但更轻 | 生态小 |

> 经验：能用 BackgroundTasks 解决就别上 Celery。一个 50 行的微服务没必要为发个邮件引入 Redis+RabbitMQ+Celery 这一套。

---

## 13.8 思考题

1. BackgroundTasks 在多 worker（uvicorn --workers 4）部署时有什么坑？
2. `replace_existing=True` 不设会怎样？什么场景会重复注册？
3. 为什么 task 用 `lambda: asyncio.ensure_future(compute_hot_posts())` 包一层？直接传 async 函数行不行？

---

## 13.9 本节交付物

| 文件 | 作用 |
|---|---|
| `app/services/email.py` | EmailLog + send_welcome_email |
| `app/services/hot_posts.py` | compute_hot_posts 定时任务 |
| `app/services/scheduler.py` | AsyncIOScheduler + scheduler_lifespan + init_scheduler |
| `app/main.py` | POST /db/posts 加 BackgroundTasks |
| `tests/test_13_background.py` | 9 条测试 |
| `docs/lessons/13-background.md` | 本文 |

---

## 13.10 下一节预告

第 14 课我们引入 **WebSocket 实时评论**：客户端用 ws:// 协议连服务端，新评论推送实时广播给所有连接。
