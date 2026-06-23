"""task-10 引入：业务异常体系 + 全局 exception_handler。

设计：
- BizError 为业务异常基类，子类通过类属性声明 code/status_code
- register_exception_handlers(app) 注册：
    - BizError handler：返回 {error: {code, message}}
    - RequestValidationError handler：改写 422
    - Exception 兜底 handler：500 + INTERNAL_ERROR
- HTTPException 仍走 Starlette 默认（兼容）
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class BizError(Exception):
    """业务异常基类。子类通过类属性覆盖 code/status_code。"""

    code: str = "BIZ_ERROR"
    status_code: int = 400

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.code
        super().__init__(self.message)


class PostNotFound(BizError):
    """文章不存在。"""

    code = "POST_NOT_FOUND"
    status_code = 404

    def __init__(self, post_id: int) -> None:
        super().__init__(f"Post {post_id} not found")
        self.post_id = post_id


class DuplicateSlug(BizError):
    """slug 已存在。"""

    code = "DUPLICATE_SLUG"
    status_code = 409

    def __init__(self, slug: str) -> None:
        super().__init__(f"Slug '{slug}' already exists")
        self.slug = slug


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。

    顺序说明：FastAPI exception_handler 是按精确类型匹配的，
    PostNotFound 不会落入 BizError handler 之外的位置——但所有子类
    会触发注册在 BizError 上的 handler（FastAPI 按 MRO 找最近注册的）。
    """

    @app.exception_handler(BizError)
    async def biz_error_handler(request: Request, exc: BizError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # exc.errors() 在 Pydantic v2 可能携带非 JSON 序列化对象（如 ValueError 实例），
        # 用 jsonable_encoder 转成基本类型再放进响应。
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": jsonable_encoder(exc.errors()),
                }
            },
        )

    @app.exception_handler(Exception)
    async def fallback_handler(request: Request, exc: Exception) -> JSONResponse:
        # 生产里这里应该 logger.exception("unhandled", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error",
                }
            },
        )
