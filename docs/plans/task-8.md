# task-8: 异步编程 async/await

## 目标
为博客加 GET /stats/aggregate 接口：async 并发拉取阅读量、评论数、点赞数；对比同步串行 vs 异步并发的耗时；async 依赖；阻塞任务用 run_in_executor。

## 涉及文件
- `app/services/external.py`（模拟外部服务调用）
- `app/services/stats.py`（async 聚合逻辑）
- `app/main.py`（新增 /stats/aggregate）
- `docs/lessons/08-async.md`
- `tests/test_08_async.py`

## 验收标准
- [ ] GET /stats/aggregate async 并发调用 3 个外部服务
- [ ] 接口返回 {views, comments, likes}
- [ ] 总耗时 ≈ max(三个)，不是 sum
- [ ] 同步版本总耗时 = sum（用作对比演示）
- [ ] asyncio.gather 异常处理
- [ ] 阻塞任务用 run_in_executor 委托线程池
- [ ] async 依赖正常工作
- [ ] 8 条测试全绿

## 测试点（至少 8 条）
1. `test_aggregate_returns_all_keys`：返回 views/comments/likes
2. `test_async_faster_than_sync`：async 耗时 < sync 耗时（time.monotonic 断言）
3. `test_gather_handles_exception`：单个服务异常不影响其他
4. `test_timeout_with_wait_for`：asyncio.wait_for 超时
5. `test_async_dependency`：async def get_async_client() 依赖
6. `test_background_tasks_with_async`：BackgroundTasks 与 async 配合
7. `test_blocking_task_via_executor`：阻塞任务走 run_in_executor
8. `test_async_context_manager_dependency`：async context manager 依赖

## 实现要点
```python
import asyncio
import time
from fastapi import APIRouter

router = APIRouter(prefix="/stats", tags=["stats"])

async def fetch_views(post_id: int) -> int:
    await asyncio.sleep(0.3)  # 模拟网络
    return 1234

async def fetch_comments(post_id: int) -> int:
    await asyncio.sleep(0.3)
    return 56

async def fetch_likes(post_id: int) -> int:
    await asyncio.sleep(0.3)
    return 789

@router.get("/aggregate/{post_id}")
async def aggregate(post_id: int):
    start = time.monotonic()
    views, comments, likes = await asyncio.gather(
        fetch_views(post_id),
        fetch_comments(post_id),
        fetch_likes(post_id),
    )
    return {
        "post_id": post_id,
        "views": views,
        "comments": comments,
        "likes": likes,
        "elapsed_ms": round((time.monotonic() - start) * 1000, 1),
    }

@router.get("/aggregate-sync/{post_id}")
def aggregate_sync(post_id: int):
    """对比：同步串行版本，故意耗时 = sum"""
    import time as _t
    _t.sleep(0.3); views = 1234
    _t.sleep(0.3); comments = 56
    _t.sleep(0.3); likes = 789
    return {"views": views, "comments": comments, "likes": likes}
```
- 测试用 `await asyncclient.get(...)`（httpx.AsyncClient）
- 阻塞任务委托：`await asyncio.get_event_loop().run_in_executor(None, blocking_fn, arg)`

## 教学文档大纲
1. 【新手】同步 vs 异步视觉对比（一张图）
2. 【新手】async def / await 语法
3. 【新手】asyncio.gather 并发
4. 【进阶】事件循环原理（极简版）
5. 【进阶】阻塞任务的危害 + run_in_executor
6. 【进阶】async 依赖、async generator yield 依赖
7. 【进阶】asyncio.wait_for 超时与 cancel
8. 思考题：在 async def 里写 `time.sleep(1)` 会发生什么？
