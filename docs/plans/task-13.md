# task-13: 后台任务 BackgroundTasks 与定时任务

## 目标
为博客加异步副作用：POST /posts 成功后 BackgroundTasks 触发"欢迎邮件"（模拟）；APScheduler 定时统计热门文章；startup/shutdown 事件。

## 涉及文件
- `app/services/email.py`（模拟邮件发送）
- `app/services/scheduler.py`（APScheduler 调度器）
- `app/services/hot_posts.py`（定时任务逻辑）
- `app/main.py`（注册 lifespan / BackgroundTasks）
- `docs/lessons/13-background.md`
- `tests/test_13_background.py`

## 验收标准
- [ ] POST /posts 创建后 BackgroundTasks 触发 send_welcome_email
- [ ] 任务在响应发出**之后**才执行
- [ ] 任务异常不影响 HTTP 响应
- [ ] 多任务按顺序执行
- [ ] startup 事件启动 APScheduler
- [ ] shutdown 事件关闭调度器
- [ ] 定时任务被注册（统计热门文章）
- [ ] 8 条测试全绿

## 测试点（至少 8 条）
1. `test_background_task_queued`：BackgroundTasks.add_task 被调用
2. `test_background_task_runs_after_response`：响应后任务执行（用 sleep + spy）
3. `test_task_exception_doesnt_break_response`：任务抛异常不影响 201
4. `test_multiple_tasks_sequential`：多任务顺序执行
5. `test_startup_event_fires`：lifespan startup 触发
6. `test_shutdown_event_fires`：lifespan shutdown 触发
7. `test_scheduler_has_job`：APScheduler 注册了 hot_posts 任务
8. `test_idempotent_task`：重复触发幂等（如去重队列）

## 实现要点
```python
# app/services/email.py
import asyncio

async def send_welcome_email(to: str, post_title: str):
    await asyncio.sleep(0.1)  # 模拟 SMTP
    # 实际写文件或调用外部服务

# app/services/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

def init_scheduler(app):
    @app.on_event("startup")
    async def _start():
        scheduler.add_job(compute_hot_posts, "interval", minutes=1, id="hot_posts")
        scheduler.start()

    @app.on_event("shutdown")
    async def _stop():
        scheduler.shutdown(wait=False)

async def compute_hot_posts():
    """定时统计热门文章，写入 hot_posts 表"""
    ...

# app/main.py
from fastapi import BackgroundTasks

@app.post("/posts", response_model=PostOut, status_code=201)
async def create_post(
    payload: PostCreate,
    background_tasks: BackgroundTasks,
    db = Depends(get_db),
    author = Depends(get_current_active_author),
):
    post = await crud_posts.create(db, payload, author_id=author.id)
    background_tasks.add_task(send_welcome_email, author.email, post.title)
    return post
```
- 用 lifespan（FastAPI 0.93+）替代 on_event（已 deprecated）也可
- 长任务/分布式场景应改用 Celery/Dramatiq

## 教学文档大纲
1. 【新手】BackgroundTasks 适用场景
2. 【新手】add_task + 依赖注入
3. 【进阶】任务执行时机（响应后）
4. 【进阶】同步 vs 异步任务
5. 【进阶】APScheduler 集成
6. 【进阶】startup/shutdown 事件 / lifespan
7. 【进阶】Celery/Dramatiq 对比
8. 思考题：BackgroundTasks 在多 worker 部署时有什么坑？
