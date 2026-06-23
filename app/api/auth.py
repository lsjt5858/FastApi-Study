"""task-12：认证路由 + JWT 依赖。

- POST /auth/register：注册新作者（密码哈希）
- POST /auth/token：OAuth2PasswordBearer 登录签发 JWT
- GET /me：用 get_current_jwt_author 依赖返回当前作者
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, decode_token
from app.crud.authors import (
    authenticate,
    create_author,
    get_author_by_id,
    get_author_by_username,
)
from app.db import get_async_db
from app.models import Author
from app.schemas.author import AuthorCreate, AuthorOut

router = APIRouter(prefix="/auth", tags=["auth"])

# OAuth2PasswordBearer 让 /docs 出现 Authorize 按钮；tokenUrl 指向登录端点
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=AuthorOut, status_code=201)
async def register(
    payload: AuthorCreate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> Author:
    """注册新作者。username 已存在 -> 409。"""
    existing = await get_author_by_username(db, payload.username)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already taken")
    author = await create_author(db, payload.username, payload.email, payload.password)
    return author


@router.post("/token", response_model=TokenResponse)
async def login(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    username: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
) -> TokenResponse:
    """OAuth2PasswordBearer 登录。

    接收 form-urlencoded 的 username/password。
    成功 -> access_token；失败 -> 401。
    """
    author = await authenticate(db, username, password)
    if author is None:
        raise HTTPException(status_code=401, detail="Bad credentials")
    token = create_access_token(
        subject=str(author.id),
        expires_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        secret=settings.SECRET_KEY.get_secret_value(),
    )
    return TokenResponse(access_token=token)


async def get_current_jwt_author(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> Author:
    """JWT 依赖：从 Authorization: Bearer <token> 解出 author。

    无 token / 伪造 / 过期 -> 401。
    """
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token, settings.SECRET_KEY.get_secret_value())
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    author = await get_author_by_id(db, int(sub))
    if author is None:
        raise HTTPException(status_code=401, detail="Author not found")
    return author
