# 第 9 课 · 中间件 Middleware

> 难度：【新手】打底，少量【进阶】。
>
> 学完本节，你能用 `BaseHTTPMiddleware` / `@app.middleware("http")` 写自定义中间件、配置 `CORSMiddleware` 白名单、用 `request.state` 在中间件与路由之间传数据，并理解 FastAPI/Starlette 的洋葱执行顺序。

---

## 9.1 【新手】中间件是什么（夹心饼干 / 洋葱模型）

每条请求从客户端到路由之间，会穿过一串中间件；响应从路由回到客户端再反向穿一次。

```
client -> [Timing -> RequestID -> CORS] -> 路由
client <- [Timing <- RequestID <- CORS] <- 路由
```

中间件可以做的事：

- 改请求：加头、改 path、改 body
- 改响应：加头（X-Response-Time / X-Request-ID）、压缩、加 cookie
- 提前返回：限流、IP 黑名单
- 透传数据：往 `request.state` 塞一个值，下游路由直接读

---

## 9.2 【新手】@app.middleware("http") 装饰器

最轻量的写法：

```python
@app.middleware("http")
async def add_marker(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Marker"] = "decorator"
    return response
```

`call_next` 把请求传给下一个中间件 / 路由，拿到响应后你可以继续改头。

---

## 9.3 【新手】BaseHTTPMiddleware 类写法

需要可配置、可继承时用类写法：

```python
from starlette.middleware.base import BaseHTTPMiddleware

class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Response-Time"] = str(elapsed_ms)
        return response
```

注册：

```python
app.add_middleware(TimingMiddleware)
```

---

## 9.4 【新手】CORSMiddleware 白名单

CORS（跨域）是浏览器同源策略的兜底；后端必须显式允许前端域名：

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://blog.example.com",      # 生产
        "http://localhost:3000",          # 本地开发
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**白名单的请求**：浏览器 OPTIONS 预检返回 `Access-Control-Allow-Origin: <origin>`。
**非白名单的请求**：要么 400、要么不返回 `Allow-Origin` 头，浏览器就会拒。

> ⚠️ 生产环境不要用 `allow_origins=["*"]` 配 `allow_credentials=True`，浏览器会拒绝。要带 cookie 就必须列具体域名。

---

## 9.5 【进阶】中间件执行顺序（洋葱模型）

FastAPI 中间件是 **LIFO**（后注册的先执行）：

```python
register_middleware(app)
#   app.add_middleware(TimingMiddleware)   # 注册顺序 1
#   app.add_middleware(RequestIDMiddleware) # 注册顺序 2
#   app.add_middleware(CORSMiddleware)      # 注册顺序 3
```

请求处理顺序（实际进洋葱的次序）：

```
CORS -> RequestID -> Timing -> 路由
```

响应回写顺序（从路由回到客户端）：

```
路由 -> Timing 写 X-Response-Time -> RequestID 写 X-Request-ID -> CORS 决定是否加 Allow-Origin
```

记忆口诀：**"先 add 的后跑"**。

---

## 9.6 【进阶】修改请求与响应

```python
@app.middleware("http")
async def rewrite(request: Request, call_next):
    # 改请求：把 X-User 改名
    if "X-User" in request.headers:
        request.scope["headers"].append((b"x-user-lower", request.headers["X-User"].lower().encode()))
    response = await call_next(request)
    # 改响应：加版本
    response.headers["X-API-Version"] = "0.1.0"
    return response
```

> 改请求体（body）比较麻烦：`Request.body()` 会消费流，需要自己包装新的 receive callable。生产里能用 schema 解决就别在中间件改 body。

---

## 9.7 【进阶】request.state 跨层传递数据

`request.state` 是一个 `State` 对象，任意可读写，**整个请求生命周期共享**：

```python
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

# 下游路由直接读
@app.get("/x")
def x(request: Request):
    return {"rid": request.state.request_id}
```

这是中间件给路由"喂"数据的标准方式，比把 request_id 当参数透传到每个函数优雅得多。

---

## 9.8 【进阶】异常穿越中间件

如果路由抛了 `HTTPException` 或未捕获异常，中间件的 `call_next` 之后那段代码（写响应头）仍然会跑 —— **但前提是你把 `call_next` 写在 try 之外**：

```python
async def dispatch(self, request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        raise
    finally:
        # 这里不一定能拿到 response（异常时没有），需要小心
        ...
```

本课的 `TimingMiddleware` 简化版：直接把 `call_next` 放最外层，FastAPI 会自动把异常转成 500 响应再回到中间件链，所以 `response.headers["X-Response-Time"] = ...` 仍然能写上去（测试 `test_exception_passes_through_middleware` 验证）。

---

## 9.9 思考题

1. 如果在 `TimingMiddleware.dispatch` 里 `await call_next(request)` 直接抛了异常（被某个上游 try 兜住），`X-Response-Time` 还会写吗？为什么？
2. `BaseHTTPMiddleware` 与纯 ASGI middleware（实现 `async def __call__(self, scope, receive, send)`）有什么区别？哪个性能更高？
3. CORS 的 `OPTIONS` 预检请求会进到你的路由吗？为什么？

---

## 9.10 本节交付物

| 文件 | 作用 |
|---|---|
| `app/core/middleware.py` | `TimingMiddleware` / `RequestIDMiddleware` / `register_middleware` |
| `app/main.py` | 启动时调用 `register_middleware(app)` |
| `tests/test_09_middleware.py` | 9 条测试 |
| `docs/lessons/09-middleware.md` | 本文 |

---

## 9.11 下一节预告

第 10 课我们引入 **Exception Handlers 异常处理**：自定义 `BizError`、`PostNotFoundError`，注册全局异常处理器返回统一错误结构，对比 `HTTPException` 与自定义异常的差别。
