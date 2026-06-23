"""Blog API — task-2 阶段：路径参数、查询参数与枚举。

在 task-1 骨架基础上扩展：
1. POSTS 数据加 status / published 字段，并扩到 15 条
2. GET /posts（list_posts）支持 limit/offset/published/status 查询参数
3. GET /users/{username} 演示 str 路径参数

后续 task 会继续在此基础上扩展（POST /posts、文件上传、依赖注入等）。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import (
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

from app.core.deps import get_current_active_author, get_db
from app.data import POSTS, USERS
from app.schemas.author import AuthorCreate
from app.schemas.enums import PostStatus
from app.schemas.post import PostCreate, PostOut
from app.services.upload import validate_and_read

app = FastAPI(
    title="Blog API",
    version="0.1.0",
    description="Python FastAPI 从入门到精通（博客渐进式实战）",
)

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
