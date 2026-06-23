"""task-9 引入：自定义中间件 + CORS。

提供两个 BaseHTTPMiddleware 子类：
- TimingMiddleware：在响应头写 X-Response-Time（毫秒）
- RequestIDMiddleware：生成或透传 X-Request-ID，绑到 request.state.request_id

以及 register_middleware(app) 统一注册到 FastAPI。
"""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# 允许跨域的博客前端域名（生产 + 本地开发）
ALLOWED_ORIGINS: list[str] = [
    "https://blog.example.com",
    "http://localhost:3000",
]


class TimingMiddleware(BaseHTTPMiddleware):
    """测量请求耗时，写入 X-Response-Time（毫秒，保留 2 位小数）。"""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Response-Time"] = str(elapsed_ms)
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """每请求生成 UUID 作为 X-Request-ID；客户端自带则透传。

    request.state.request_id 给下游路由 / 日志用。
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def register_middleware(app: FastAPI) -> None:
    """统一注册中间件。

    FastAPI 中间件执行顺序：**后注册的先执行**（洋葱模型 LIFO）。
    因此下面注册顺序的洋葱结构（从外到内）：
        Timing -> RequestID -> CORS -> 路由
    即请求进来先碰到 CORS（最里层防护），响应出去时 Timing 最后写头。
    """
    # 注册顺序：先 Timing，后 RequestID，最后 CORS
    # 由于 LIFO，请求处理顺序为：CORS -> RequestID -> Timing -> 路由
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
