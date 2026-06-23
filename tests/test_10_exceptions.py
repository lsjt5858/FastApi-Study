"""task-10 测试：异常处理与全局错误捕获。

8 条测试覆盖：
- BizError 体系：PostNotFound(404) / DuplicateSlug(409)
- exception_handler 统一错误结构 {error:{code, message}}
- 改写 RequestValidationError -> 422 结构
- 兜底 Exception -> 500
- HTTPException 兼容
- 错误码出现在响应
- 子类 handler 优先于父类
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.exceptions import (
    BizError,
    DuplicateSlug,
    PostNotFound,
    register_exception_handlers,
)


def _build_app() -> FastAPI:
    """最小 app，挂上各异常触发路由 + 注册全局 handler。"""
    app = FastAPI()

    class Body(BaseModel):
        title: str

    @app.get("/raise/post-not-found")
    def r1() -> dict:
        raise PostNotFound(post_id=999)

    @app.get("/raise/duplicate-slug")
    def r2() -> dict:
        raise DuplicateSlug(slug="hello-world")

    @app.get("/raise/http-exception")
    def r3() -> dict:
        raise HTTPException(status_code=418, detail="I'm a teapot")

    @app.get("/raise/generic")
    def r4() -> dict:
        raise RuntimeError("unexpected boom")

    @app.post("/validation")
    def v5(body: Body) -> dict:
        return {"title": body.title}

    register_exception_handlers(app)
    return app


def test_post_not_found_returns_404() -> None:
    """PostNotFound -> 404 + 统一错误结构。"""
    client = TestClient(_build_app(), raise_server_exceptions=False)
    resp = client.get("/raise/post-not-found")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "POST_NOT_FOUND"
    assert "999" in body["error"]["message"]


def test_duplicate_slug_returns_409() -> None:
    """DuplicateSlug -> 409 + 错误码 + slug 在 message 里。"""
    client = TestClient(_build_app(), raise_server_exceptions=False)
    resp = client.get("/raise/duplicate-slug")
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "DUPLICATE_SLUG"
    assert "hello-world" in body["error"]["message"]


def test_validation_error_structure() -> None:
    """RequestValidationError -> 422 + 自定义 {error:{code, details}} 结构。"""
    client = TestClient(_build_app(), raise_server_exceptions=False)
    # 不传 body 必然 422
    resp = client.post("/validation", json={})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "details" in body["error"]
    assert isinstance(body["error"]["details"], list)
    assert len(body["error"]["details"]) >= 1


def test_unhandled_exception_returns_500() -> None:
    """未捕获的 RuntimeError 走兜底 handler -> 500。"""
    client = TestClient(_build_app(), raise_server_exceptions=False)
    resp = client.get("/raise/generic")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"


def test_http_exception_still_compatible() -> None:
    """HTTPException 仍然能正常返回对应状态码。"""
    client = TestClient(_build_app(), raise_server_exceptions=False)
    resp = client.get("/raise/http-exception")
    assert resp.status_code == 418


def test_biz_error_base_class_attrs() -> None:
    """BizError 基类默认 code/status_code。"""
    assert BizError.code == "BIZ_ERROR"
    assert BizError.status_code == 400
    assert PostNotFound.code == "POST_NOT_FOUND"
    assert PostNotFound.status_code == 404
    assert DuplicateSlug.code == "DUPLICATE_SLUG"
    assert DuplicateSlug.status_code == 409


def test_biz_error_message_fallback_to_code() -> None:
    """BizError 基类不传 message 时回退到 code（默认 message == code）。"""
    err = BizError()
    assert err.message == BizError.code


def test_exception_handler_priority_subclass_first() -> None:
    """PostNotFound 是 BizError 子类；命中 PostNotFound handler 而非 BizError 父类。

    验证方式：触发 PostNotFound，响应 code 必须是 POST_NOT_FOUND（不是 BIZ_ERROR）。
    """
    client = TestClient(_build_app(), raise_server_exceptions=False)
    resp = client.get("/raise/post-not-found")
    assert resp.json()["error"]["code"] == "POST_NOT_FOUND"
