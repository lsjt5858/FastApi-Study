# task-10: 异常处理与全局错误捕获

## 目标
为博客定义业务异常体系：PostNotFound/DuplicateSlug/BizError 基类；自定义 exception_handler 返回统一错误结构；改写 422 校验错误；兜底 500。

## 涉及文件
- `app/core/exceptions.py`（异常类 + handlers）
- `app/main.py`（注册 handlers）
- `app/services/errors.py`（错误码常量）
- `docs/lessons/10-exceptions.md`
- `tests/test_10_exceptions.py`

## 验收标准
- [ ] 异常基类 BizError，子类 PostNotFound(404)/DuplicateSlug(409)
- [ ] @app.exception_handler(BizError) 返回 {error:{code, message}}
- [ ] @app.exception_handler(RequestValidationError) 改写 422
- [ ] @app.exception_handler(Exception) 兜底 500 + 日志
- [ ] 错误码体系（POST_NOT_FOUND/DUPLICATE_SLUG/...）
- [ ] HTTPException 仍兼容
- [ ] 异常被中间件记录
- [ ] 8 条测试全绿

## 测试点（至少 8 条）
1. `test_post_not_found_returns_404`：抛 PostNotFound 返回 404
2. `test_duplicate_slug_returns_409`：抛 DuplicateSlug 返回 409
3. `test_validation_error_structure`：422 默认结构被改写
4. `test_unhandled_exception_returns_500`：未捕获异常 500
5. `test_error_code_in_response`：错误码 POST_NOT_FOUND 等出现
6. `test_http_exception_still_compatible`：HTTPException 仍能正常工作
7. `test_exception_logged_via_middleware`：异常被中间件记录（spy）
8. `test_exception_handler_priority`：子类 handler 优先于父类

## 实现要点
```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

class BizError(Exception):
    code: str = "BIZ_ERROR"
    status_code: int = 400
    def __init__(self, message: str | None = None):
        self.message = message or self.code
        super().__init__(self.message)

class PostNotFound(BizError):
    code = "POST_NOT_FOUND"
    status_code = 404

class DuplicateSlug(BizError):
    code = "DUPLICATE_SLUG"
    status_code = 409

def register_exception_handlers(app: FastAPI):
    @app.exception_handler(BizError)
    async def biz_handler(request: Request, exc: BizError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": exc.errors(),
                }
            },
        )

    @app.exception_handler(Exception)
    async def fallback_handler(request: Request, exc: Exception):
        # 实际项目要加 logger.exception
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "..."}},
        )
```
- exception_handler 注册顺序：子类要在父类之前注册才能命中（FastAPI 按精确匹配优先）
- 改写 RequestValidationError 时记得保留 errors() 用于调试

## 教学文档大纲
1. 【新手】HTTPException 用法
2. 【新手】自定义异常 + exception_handler
3. 【新手】统一错误结构（code/message/details）
4. 【进阶】改写 RequestValidationError
5. 【进阶】兜底 Exception handler
6. 【进阶】异常处理器优先级
7. 【进阶】异常与日志/链路追踪
8. 思考题：为什么不要在路由里直接 try/except 吞异常？
