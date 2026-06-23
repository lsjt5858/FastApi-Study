"""task-6 引入：依赖注入函数与类。

依赖注入（DI）的核心思想：把"路由需要的辅助逻辑"提取成可复用、可测试的函数/类，
路由通过 Depends(...) 声明依赖，FastAPI 自动调用并把结果作为参数传入。

本模块提供：
- pagination / PaginationDep：分页参数（函数版 + 类版）
- get_db：yield 风格的资源依赖（task-11 会替换为真实 SQLAlchemy session）
- get_current_author / get_current_active_author：嵌套依赖链示范
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.data import POSTS

# ---------- 分页依赖 ----------


@dataclass
class Pagination:
    """函数式分页依赖的返回类型。"""

    limit: int = 10
    offset: int = 0


def pagination(limit: int = 10, offset: int = 0) -> Pagination:
    """函数式分页依赖。用法：def route(pag: Annotated[Pagination, Depends()])."""
    return Pagination(limit=limit, offset=offset)


@dataclass
class PaginationDep:
    """Class-based 分页依赖。

    与函数版的区别：直接以实例作为参数对象（FastAPI 会用 __init__ 签名注入参数）。
    适合"需要内部状态"的依赖（如缓存计算结果）。
    """

    limit: int = 10
    offset: int = 0


# ---------- 数据库会话（yield 依赖）----------


def get_db() -> dict:
    """模拟数据库会话。

    使用 yield 让 FastAPI 在请求结束后执行清理（finally 块）。
    task-11 会替换为真正的 AsyncSession。
    """
    db = {"session_id": "mock-session", "posts": list(POSTS)}
    try:
        yield db
    finally:
        # 模拟会话清理（关闭连接、释放资源）
        db.clear()


# ---------- 当前作者（嵌套依赖）----------


def get_current_author(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """从 Authorization 头解析当前作者。

    task-6 阶段硬编码：只要带 Bearer token 就返回 alice。
    task-12 会替换为真正的 JWT 解码。
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization")
    # 真实场景：解析 JWT、查 DB
    return {"id": 1, "username": "alice", "is_active": True, "role": "author"}


def get_current_active_author(
    author: Annotated[dict, Depends(get_current_author)],
) -> dict:
    """嵌套依赖：先调用 get_current_author 拿作者，再校验 is_active。

    FastAPI 看到 Depends(get_current_author) 会自动调用前者并把结果注入 author。
    这就是 task-6 演示的"3 层嵌套链"：路由 → get_current_active_author → get_current_author。
    """
    if not author.get("is_active"):
        raise HTTPException(status_code=403, detail="Inactive author")
    return author
