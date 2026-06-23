# 第 10 课 · 异常处理与全局错误捕获

> 难度：【新手】打底，【进阶】收尾。
>
> 学完本节，你能定义业务异常体系（`BizError` + 子类）、注册 `@app.exception_handler` 返回统一错误结构、改写 Pydantic 422、兜底未捕获异常。

---

## 10.1 【新手】HTTPException：FastAPI 内置异常

```python
from fastapi import HTTPException

@app.get("/users/{username}")
def get_user(username: str):
    if username != "alice":
        raise HTTPException(status_code=404, detail="User not found")
    return {...}
```

响应自动是 `{"detail": "User not found"}`，状态码 404。

**问题**：每个接口自己写"detail"结构，前端解析时痛苦。我们需要**统一错误结构**。

---

## 10.2 【新手】统一错误结构

所有业务错误返回：

```json
{
  "error": {
    "code": "POST_NOT_FOUND",
    "message": "Post 999 not found"
  }
}
```

前端只看 `error.code`，做对应处理（toast / 跳转 / 重试）。

---

## 10.3 【新手】自定义业务异常体系

```python
class BizError(Exception):
    code: str = "BIZ_ERROR"
    status_code: int = 400

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.code
        super().__init__(self.message)

class PostNotFound(BizError):
    code = "POST_NOT_FOUND"
    status_code = 404

    def __init__(self, post_id: int) -> None:
        super().__init__(f"Post {post_id} not found")
        self.post_id = post_id

class DuplicateSlug(BizError):
    code = "DUPLICATE_SLUG"
    status_code = 409
```

设计原则：
- **基类只放公共字段**（code、status_code、message）
- **子类通过类属性覆盖** code/status_code，构造函数接业务参数（post_id、slug）
- **路由直接 raise 子类**，handler 统一序列化

---

## 10.4 【新手】注册 exception_handler

```python
@app.exception_handler(BizError)
async def biz_error_handler(request: Request, exc: BizError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )
```

之后**所有 BizError 子类**（PostNotFound / DuplicateSlug / ...）都会自动走这个 handler。子类的 `code` / `status_code` 各自生效。

---

## 10.5 【进阶】改写 RequestValidationError（422）

FastAPI 默认 422 结构是：

```json
{"detail": [{"type": "...", "loc": [...], "msg": "...", "input": ...}, ...]}
```

如果想统一成 `{error: {code, details}}` 风格：

```python
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    # Pydantic v2 errors() 可能含非 JSON 对象（ValueError 实例），必须用 jsonable_encoder
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
```

> ⚠️ 不要直接 `json.dumps(exc.errors())`，Pydantic v2 的 `ctx` 字段可能挂着 `ValueError` 实例，会抛 `TypeError: Object of type ValueError is not JSON serializable`。

---

## 10.6 【进阶】兜底 Exception handler

```python
@app.exception_handler(Exception)
async def fallback_handler(request, exc):
    # 生产里应该 logger.exception("unhandled", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}},
    )
```

好处：
- 任何意外异常都返回统一 500 结构，不会泄露 stack trace
- 不会让 Event Loop 直接挂掉

**坏处**：Debug 时不容易看到原始异常，记得配 logger 把 stack 写到日志里。

---

## 10.7 【进阶】异常处理器优先级（MRO）

FastAPI 按 **MRO 顺序**（方法解析顺序）找最近注册的 handler：

```python
@app.exception_handler(BizError)
async def biz_handler(...): ...

# PostNotFound 是 BizError 子类
# PostNotFound 没单独注册 handler → 走 BizError 的 handler
# 但 handler 里访问的 exc.code、exc.status_code 来自 PostNotFound 子类的属性
```

所以 PostNotFound 触发时：
- handler 是 `biz_handler`（注册在 BizError 上）
- 但 `exc.code == "POST_NOT_FOUND"`、`exc.status_code == 404`（PostNotFound 子类属性）

如果想给某个子类特殊处理，单独注册：

```python
@app.exception_handler(PostNotFound)
async def post_not_found_handler(request, exc):
    # 这里能拿到 exc.post_id，做更精细响应
    return JSONResponse(...)
```

---

## 10.8 【进阶】异常与中间件的关系

中间件链：

```
请求 -> Timing -> RequestID -> CORS -> 路由（可能抛异常）
                                          ↓
        ← Timing ← RequestID ← CORS ← ServerErrorMiddleware（捕获异常）← ExceptionMiddleware
```

- `ServerErrorMiddleware` 是 Starlette 默认装的，会捕获路由抛出的所有未处理异常
- 异常被 `@app.exception_handler(SomeExc)` 捕获后会转成响应，再回中间件链
- `TimingMiddleware` 的 `await call_next(request)` 拿到的是异常转出来的 500 响应，所以仍能写 `X-Response-Time` 头

---

## 10.9 思考题

1. 为什么不要在路由里 `try/except: pass` 吞异常？
2. `HTTPException` 与自定义 `BizError` 同时存在时，谁优先？为什么 HTTPException 不被 Exception handler 拦截？
3. 如果 422 handler 里直接 `json.dumps(exc.errors())` 会怎样？为什么？

---

## 10.10 本节交付物

| 文件 | 作用 |
|---|---|
| `app/core/exceptions.py` | BizError / PostNotFound / DuplicateSlug / register_exception_handlers |
| `app/main.py` | 启动时 register_exception_handlers(app) |
| `tests/test_10_exceptions.py` | 8 条测试 |
| `docs/lessons/10-exceptions.md` | 本文 |

---

## 10.11 下一节预告

第 11 课我们引入 **SQLAlchemy Async + 数据库**：用 SQLAlchemy 2.x async 替换内存 POSTS，引入 Alembic 迁移基础、async session、模型与 schema 分离。
