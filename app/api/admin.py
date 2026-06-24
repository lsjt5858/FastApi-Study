"""task-20：管理员 scope 路由（综合实战）。

演示 **scope-based 授权**：JWT 的 `scope` 字段标识持有人权限范围。
- `scope="admin"` → 可以删除任意文章
- `scope="user"`（默认） → 拒绝

端点：
- DELETE /admin/posts/{post_id}：删除文章（仅 admin）

与 task-12 的"作者校验"互补：
- task-12 关注"你是不是这篇文章的作者"（resource ownership）
- task-20 关注"你是不是管理员"（global capability）
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import PostNotFound
from app.core.security import decode_token
from app.crud import delete_post as crud_delete_post
from app.db import get_async_db

router = APIRouter(prefix="/admin", tags=["admin"])


async def require_admin(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """要求请求携带合法 JWT 且 `scope` 字段含 `admin`。

    - 缺 Authorization 头 / 不是 Bearer → 401
    - token 解析失败（伪造 / 过期） → 401（decode_token 抛）
    - scope 不含 admin → 403
    - 通过 → 返回 payload（路由可继续用 sub 等字段）
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token, settings.SECRET_KEY.get_secret_value())

    # scope 字段支持两种格式：空格分隔字符串（OAuth2 风格）或列表
    raw_scope = payload.get("scope", "")
    if isinstance(raw_scope, str):
        scopes = raw_scope.split()
    else:
        scopes = list(raw_scope)

    if "admin" not in scopes:
        raise HTTPException(status_code=403, detail="Admin scope required")
    return payload


@router.delete("/posts/{post_id}", status_code=204)
async def admin_delete_post(
    post_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    _: Annotated[dict, Depends(require_admin)],
) -> None:
    """管理员删除文章。

    - require_admin 已过滤 401/403
    - 文章不存在 → 404 POST_NOT_FOUND（统一错误结构）
    - 删除成功后失效列表缓存（task-18 引入的 cache-aside 主动失效模式）

    测试见 tests/test_20_blog_e2e.py::test_e2e_admin_scope_required_to_delete。
    """
    from app.services.cache import cache_invalidate_pattern

    deleted = await crud_delete_post(db, post_id)
    if not deleted:
        raise PostNotFound(post_id=post_id)
    await cache_invalidate_pattern("post:list:*")
    return None
