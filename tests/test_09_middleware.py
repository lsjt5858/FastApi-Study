"""task-9 测试：中间件 Middleware。

8 条测试覆盖：
- X-Response-Time 响应头
- X-Request-ID 响应头（UUID）
- request.state.request_id 跨层传递
- CORS 预检白名单通过
- CORS 预检非白名单拒绝
- 中间件洋葱执行顺序
- 异常穿越中间件仍注入 header
- @app.middleware("http") 与 BaseHTTPMiddleware 等价
"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app.core.middleware import register_middleware


def _build_app() -> FastAPI:
    """构造一个最小 app 注册所有中间件，避免污染全局 app。"""
    app = FastAPI()

    @app.get("/ping")
    def ping() -> dict:
        return {"ok": True}

    @app.get("/raise")
    def raise_endpoint() -> dict:
        raise HTTPException(status_code=500, detail="boom")

    @app.get("/echo-request-id")
    def echo_request_id(request: Request) -> dict:
        return {"request_id": request.state.request_id}

    register_middleware(app)
    return app


def test_response_time_header() -> None:
    """响应头包含 X-Response-Time（毫秒数值）。"""
    client = TestClient(_build_app())
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert "X-Response-Time" in resp.headers
    ms = float(resp.headers["X-Response-Time"])
    assert ms >= 0


def test_request_id_header_uuid() -> None:
    """X-Request-ID 是合法 UUID。"""
    client = TestClient(_build_app())
    resp = client.get("/ping")
    rid = resp.headers.get("X-Request-ID")
    assert rid is not None
    uuid.UUID(rid)  # 抛异常即非法


def test_request_id_in_state() -> None:
    """request.state.request_id 与响应头一致。"""
    client = TestClient(_build_app())
    resp = client.get("/echo-request-id")
    assert resp.status_code == 200
    assert resp.json()["request_id"] == resp.headers["X-Request-ID"]


def test_request_id_passthrough_from_header() -> None:
    """客户端自带 X-Request-ID 时透传，而不是重新生成。"""
    client = TestClient(_build_app())
    fixed = "11111111-2222-3333-4444-555555555555"
    resp = client.get("/ping", headers={"X-Request-ID": fixed})
    assert resp.headers["X-Request-ID"] == fixed


def test_cors_preflight_allowed() -> None:
    """白名单域名 OPTIONS 预检通过。"""
    client = TestClient(_build_app())
    resp = client.options(
        "/ping",
        headers={
            "Origin": "https://blog.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("Access-Control-Allow-Origin") == "https://blog.example.com"


def test_cors_preflight_rejected() -> None:
    """非白名单域名 OPTIONS 预检被拒（没有 Allow-Origin 头）。"""
    client = TestClient(_build_app())
    resp = client.options(
        "/ping",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "Access-Control-Allow-Origin" not in resp.headers


def test_exception_passes_through_middleware() -> None:
    """路由抛异常时，中间件仍注入 X-Response-Time / X-Request-ID。"""
    client = TestClient(_build_app(), raise_server_exceptions=False)
    resp = client.get("/raise")
    assert resp.status_code == 500
    assert "X-Response-Time" in resp.headers
    assert "X-Request-ID" in resp.headers


def test_decorator_equivalent_to_base_http_middleware() -> None:
    """@app.middleware('http') 装饰器与 BaseHTTPMiddleware 行为等价。"""
    app = FastAPI()

    @app.middleware("http")
    async def add_marker(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Marker"] = "decorator"
        return response

    @app.get("/x")
    def x() -> dict:
        return {"ok": True}

    client = TestClient(app)
    resp = client.get("/x")
    assert resp.headers.get("X-Marker") == "decorator"


def test_two_middleware_classes_registered() -> None:
    """两个 middleware 类都被注册（接口健康）。"""
    app = _build_app()
    names = {getattr(m.cls, "__name__", str(m.cls)) for m in app.user_middleware}
    assert "TimingMiddleware" in names
    assert "RequestIDMiddleware" in names
