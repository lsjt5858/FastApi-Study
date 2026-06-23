"""Blog API — task-2 阶段：路径参数、查询参数与枚举。

在 task-1 骨架基础上扩展：
1. POSTS 数据加 status / published 字段，并扩到 15 条
2. GET /posts（list_posts）支持 limit/offset/published/status 查询参数
3. GET /users/{username} 演示 str 路径参数

后续 task 会继续在此基础上扩展（POST /posts、文件上传、依赖注入等）。
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import (
    BackgroundTasks,
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_jwt_author
from app.api.auth import router as auth_router
from app.core.deps import get_current_active_author, get_db
from app.core.exceptions import PostNotFound
from app.crud import create_post as crud_create_post
from app.crud import delete_post as crud_delete_post
from app.crud import get_post as crud_get_post
from app.crud import list_posts as crud_list_posts
from app.data import POSTS, USERS
from app.db import get_async_db
from app.models import Post
from app.schemas.author import AuthorCreate, AuthorOut
from app.schemas.enums import PostStatus
from app.schemas.post import PostCreate, PostOut
from app.services.external import blocking_cpu_task
from app.services.stats import aggregate_with_gather
from app.services.upload import validate_and_read

app = FastAPI(
    title="Blog API",
    version="0.1.0",
    description="Python FastAPI 从入门到精通（博客渐进式实战）",
)

# task-9：注册中间件（Timing / RequestID / CORS）
# 在 app 装配阶段调用 register_middleware，让中间件参与到所有路由的请求/响应处理
from app.core.middleware import register_middleware  # noqa: E402

register_middleware(app)

# task-10：注册全局异常处理器（BizError / RequestValidationError / Exception 兜底）
from app.core.exceptions import register_exception_handlers  # noqa: E402

register_exception_handlers(app)

# task-12：挂载认证路由（/auth/register, /auth/token）
app.include_router(auth_router)


# task-12：/me 端点（JWT 依赖）
@app.get("/me", response_model=AuthorOut)
async def me(
    author: Annotated[dict, Depends(get_current_jwt_author)],
) -> dict:
    """返回当前 JWT 持有者。无 token / 过期 / 伪造 -> 401。"""
    return {"id": author.id, "username": author.username, "display_name": None}


# 数据层在 app.data，main.py 通过 import 引用（避免与 core/deps.py 循环 import）


@app.get("/")
def root() -> dict:
    """根路径，返回博客基本信息与文档入口。"""
    return {
        "name": app.title,
        "version": app.version,
        "docs_url": "/docs",
    }


@app.get("/health")
def health() -> dict:
    """健康检查端点。"""
    return {"status": "ok"}


@app.get("/posts", response_model=list[PostOut])
def list_posts(
    limit: Annotated[int, Query(ge=1, le=100, description="每页条数，1~100")] = 10,
    offset: Annotated[int, Query(ge=0, description="偏移量，>=0")] = 0,
    published: Annotated[bool | None, Query(description="按 published 过滤")] = None,
    status: Annotated[PostStatus | None, Query(description="按 status 枚举过滤")] = None,
) -> list[dict]:
    """文章列表：支持分页与按 published / status 过滤。

    response_model=list[PostOut] 自动过滤 is_deleted / author.password 等敏感字段。
    """
    items = POSTS
    if published is not None:
        items = [p for p in items if p.get("published") == published]
    if status is not None:
        items = [p for p in items if p.get("status") == status.value]
    return items[offset : offset + limit]


@app.get("/posts/{post_id}", response_model=PostOut)
def get_post(post_id: int) -> dict:
    """按 id 获取单篇文章；不存在返回自定义 404 结构。"""
    for post in POSTS:
        if post["id"] == post_id:
            return post
    return JSONResponse(
        status_code=404,
        content={"error": {"code": "POST_NOT_FOUND", "message": f"Post {post_id} not found"}},
    )


@app.get("/posts/{post_id}/brief", response_model=PostOut, response_model_include={"id", "title"})
def get_post_brief(post_id: int) -> dict:
    """演示 response_model_include：只暴露 id 与 title。"""
    for post in POSTS:
        if post["id"] == post_id:
            return post
    return JSONResponse(
        status_code=404,
        content={"error": {"code": "POST_NOT_FOUND", "message": "Not found"}},
    )


@app.get("/posts/{post_id}/full", response_model=PostOut, response_model_exclude={"metadata"})
def get_post_full(post_id: int) -> dict:
    """演示 response_model_exclude：隐藏 metadata，其他保留。"""
    for post in POSTS:
        if post["id"] == post_id:
            return post
    return JSONResponse(
        status_code=404,
        content={"error": {"code": "POST_NOT_FOUND", "message": "Not found"}},
    )


@app.post("/posts", response_model=PostOut, status_code=201)
def create_post(
    payload: PostCreate,
    response: Response,
    db: Annotated[dict, Depends(get_db)],
) -> dict:
    """创建文章。

    task-6 新增：依赖注入 get_db（演示 yield 依赖）。
    task-6 暂不要求 Authorization（在 DELETE 上演示权限）。

    - response_model=PostOut: 返回时过滤敏感字段
    - response.set_cookie: 演示在响应里下发 Cookie
    - response.headers['X-Blog-Version']: 演示自定义响应头
    """
    new_id = (max(p["id"] for p in POSTS) + 1) if POSTS else 1
    post = {
        "id": new_id,
        **payload.model_dump(by_alias=False),
        "is_deleted": False,
        "author": None,
    }
    POSTS.append(post)
    response.headers["X-Blog-Version"] = app.version
    response.set_cookie(
        key="last_create",
        value=payload.title[:32],
        httponly=True,
        samesite="lax",
    )
    return post


@app.delete("/posts/{post_id}", status_code=204)
def delete_post(
    post_id: int,
    author: Annotated[dict, Depends(get_current_active_author)],
) -> None:
    """删除文章。

    task-6 新增：依赖注入 get_current_active_author 演示"必须当前作者"。
    缺 token → 401（get_current_author 抛）。
    token 非激活 → 403（get_current_active_author 抛）。
    """
    for i, p in enumerate(POSTS):
        if p["id"] == post_id:
            POSTS.pop(i)
            return None
    return JSONResponse(
        status_code=404,
        content={"error": {"code": "POST_NOT_FOUND", "message": "Not found"}},
    )


@app.post("/authors/preview")
def preview_author(payload: AuthorCreate) -> dict:
    """task-7 新增：演示 AuthorCreate 校验（email lower / phone 自定义类型）。

    task-12 会替换为真正的 /auth/register 接口。
    """
    return {
        "username": payload.username,
        "email": payload.email,
        "phone": payload.phone,
    }


@app.get("/users/{username}")
def get_user(username: str) -> dict:
    """按 username 获取作者（演示 str 路径参数）。"""
    for u in USERS:
        if u["username"] == username:
            return u
    raise HTTPException(status_code=404, detail="User not found")


@app.post("/posts/{post_id}/cover", status_code=201)
async def upload_cover(
    post_id: int,
    file: UploadFile,
    alt_text: Annotated[str, Form(min_length=1, max_length=200)],
    x_upload_token: Annotated[str | None, Header()] = None,
    upload_session_id: Annotated[str | None, Cookie()] = None,
) -> dict:
    """上传单篇封面。

    演示四种"非 JSON"输入：
    - UploadFile: multipart 里的二进制
    - Form: multipart 里的纯文本字段
    - Header: 请求头（Python 参数名小写，自动映射 X-Upload-Token）
    - Cookie: Cookie 头里的某项
    """
    if not x_upload_token:
        raise HTTPException(status_code=401, detail="Missing upload token")
    data = await validate_and_read(file)
    return {
        "post_id": post_id,
        "size": len(data),
        "alt_text": alt_text,
        "session_id": upload_session_id,
        "filename": file.filename,
    }


@app.post("/posts/{post_id}/covers", status_code=201)
async def upload_covers(
    post_id: int,
    files: Annotated[list[UploadFile], File()],
    alt_text: Annotated[str, Form(min_length=1, max_length=200)],
    x_upload_token: Annotated[str | None, Header()] = None,
) -> dict:
    """一次上传多张封面。"""
    if not x_upload_token:
        raise HTTPException(status_code=401, detail="Missing upload token")
    sizes = []
    for f in files:
        data = await validate_and_read(f)
        sizes.append({"filename": f.filename, "size": len(data)})
    return {"post_id": post_id, "count": len(files), "files": sizes, "alt_text": alt_text}


# ---------- task-8：异步统计聚合 ----------


async def get_async_client() -> dict:
    """async 依赖演示：在 async 函数里返回模拟的 httpx client。"""
    return {"client": "async-httpx-client", "id": id(object())}


# 模块级事件日志：观察 async generator 依赖的 setup/teardown 时序
# （route 在 yield 阶段返回响应时，teardown 还没跑；只能在请求结束后从外部观察）
_CTX_EVENTS: list[str] = []


async def async_resource():
    """async generator 依赖：FastAPI 直接支持 async generator（yield 自动转 finally 清理）。

    注意：contextlib.asynccontextmanager 装饰出的对象是 _AsyncGeneratorContextManager，
    不能直接当 FastAPI 依赖用（Depends 不会进入 context）。
    FastAPI 原生支持 async generator 函数：yield 前面是 setup，yield 之后是 teardown。
    teardown 在响应序列化之后执行，所以 route 返回时 exited 仍是 False；
    要观察 teardown，需读取模块级 _CTX_EVENTS。
    """
    _CTX_EVENTS.clear()
    _CTX_EVENTS.append("entered")
    state = {"entered": True, "exited": False}
    try:
        yield state
    finally:
        state["exited"] = True
        _CTX_EVENTS.append("exited")


@app.get("/stats/aggregate/{post_id}")
async def stats_aggregate(post_id: int) -> dict:
    """async 并发聚合 3 个外部服务，演示 asyncio.gather。"""
    views, comments, likes, elapsed_ms = await aggregate_with_gather(post_id)
    return {
        "post_id": post_id,
        "views": views,
        "comments": comments,
        "likes": likes,
        "elapsed_ms": round(elapsed_ms, 1),
    }


@app.get("/stats/aggregate-sync/{post_id}")
def stats_aggregate_sync(post_id: int) -> dict:
    """对比演示：同步串行版本，总耗时 = sum（每个 sleep 累加）。

    在生产 async 应用里写这种接口会阻塞整个 worker。
    """
    import time as _t

    _t.sleep(0.05)
    views = 1234
    _t.sleep(0.05)
    comments = 56
    _t.sleep(0.05)
    likes = 789
    return {"post_id": post_id, "views": views, "comments": comments, "likes": likes}


@app.get("/stats/async-dep")
async def stats_async_dep(client: Annotated[dict, Depends(get_async_client)]) -> dict:
    """演示 async 依赖。"""
    return {"client": client["client"]}


@app.post("/stats/trigger-background", status_code=202)
async def stats_trigger_background(background_tasks: BackgroundTasks) -> dict:
    """演示 BackgroundTasks 与 async 路由配合。"""
    background_tasks.add_task(lambda: None)  # 占位任务
    return {"scheduled": True}


@app.get("/stats/blocking-via-executor")
async def stats_blocking_via_executor(n: int = 10) -> dict:
    """演示：阻塞任务用 run_in_executor 委托线程池。"""
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, blocking_cpu_task, n)
    return {"n": n, "result": result}


@app.get("/stats/with-ctx")
async def stats_with_ctx(
    state: Annotated[dict, Depends(async_resource)],
) -> dict:
    """演示：async context manager 依赖。

    响应序列化时 teardown 还没跑，所以响应里 exited 必然是 False；
    要观察 teardown 是否真的执行了，看模块级 _CTX_EVENTS（测试在请求结束后断言它）。
    """
    return {"entered": state["entered"], "exited": state["exited"]}


# ---------- task-11：SQLAlchemy 异步 DB 路由（/db/posts 前缀，渐进式新增） ----------


@app.post("/db/posts", response_model=PostOut, status_code=201)
async def db_create_post(
    payload: PostCreate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> dict:
    """创建文章（DB 持久化）。title 重复 -> IntegrityError -> 409。"""
    from sqlalchemy.exc import IntegrityError

    try:
        post = await crud_create_post(db, title=payload.title, content=payload.content)
    except IntegrityError as exc:
        raise BizDuplicate from exc
    return _post_to_dict(post)


@app.get("/db/posts", response_model=list[PostOut])
async def db_list_posts(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict]:
    """列表（DB）。"""
    items = await crud_list_posts(db, limit=limit, offset=offset)
    return [_post_to_dict(p) for p in items]


@app.get("/db/posts/{post_id}", response_model=PostOut)
async def db_get_post(
    post_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> dict:
    """详情（DB）。不存在 -> 404 POST_NOT_FOUND。"""
    post = await crud_get_post(db, post_id)
    if post is None:
        raise PostNotFound(post_id=post_id)
    return _post_to_dict(post)


@app.delete("/db/posts/{post_id}", status_code=204)
async def db_delete_post(
    post_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> None:
    """删除（DB）。不存在 -> 404 POST_NOT_FOUND。"""
    deleted = await crud_delete_post(db, post_id)
    if not deleted:
        raise PostNotFound(post_id=post_id)
    return None


def _post_to_dict(post: Post) -> dict:
    """ORM model -> dict（response_model=PostOut 会二次校验）。"""
    return {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "tags": [],
        "slug": "",
    }


class BizDuplicate(Exception):
    """title 重复（task-11 路由内联捕获，转 409）。"""

    code = "DUPLICATE_TITLE"
    status_code = 409


@app.exception_handler(BizDuplicate)
async def _biz_duplicate_handler(request, exc: BizDuplicate) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": "Post title already exists"}},
    )
