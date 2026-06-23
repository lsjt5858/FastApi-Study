# task-9: 中间件 Middleware

## 目标
为博客加三个中间件：①耗时统计 X-Response-Time；②CORS 允许博客前端域名；③请求 ID X-Request-ID（每请求生成 UUID，绑到 request.state）。

## 涉及文件
- `app/core/middleware.py`（自定义中间件）
- `app/main.py`（注册中间件）
- `docs/lessons/09-middleware.md`
- `tests/test_09_middleware.py`

## 验收标准
- [ ] 响应头含 X-Response-Time（毫秒）
- [ ] 响应头含 X-Request-ID（UUID）
- [ ] request.state.request_id 被下游访问
- [ ] CORS OPTIONS 预检通过白名单
- [ ] CORS 非白名单域名被拒
- [ ] 中间件执行顺序可证明（外层→内层→外层）
- [ ] 异常穿越中间件不丢失响应头
- [ ] 8 条测试全绿

## 测试点（至少 8 条）
1. `test_response_time_header`：响应含 X-Response-Time
2. `test_request_id_header_uuid`：X-Request-ID 是合法 UUID
3. `test_request_id_in_state`：request.state.request_id 与响应头一致
4. `test_cors_preflight_allowed`：OPTIONS 白名单域名通过
5. `test_cors_preflight_rejected`：OPTIONS 非白名单域名被拒
6. `test_middleware_order`：通过记录顺序证明中间件嵌套
7. `test_exception_passes_through_middleware`：抛异常时仍注入 header
8. `test_base_http_middleware_vs_decorator`：对比两种写法

## 实现要点
```python
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Response-Time"] = str(elapsed_ms)
        return response

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

def register_middleware(app: FastAPI):
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://blog.example.com", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```
- 中间件执行顺序：**后注册的先执行**（LIFO）
- `@app.middleware("http")` 装饰器写法等价于 BaseHTTPMiddleware，但后者更易扩展

## 教学文档大纲
1. 【新手】中间件是什么（夹心饼干图）
2. 【新手】@app.middleware("http") 装饰器
3. 【新手】BaseHTTPMiddleware 类写法
4. 【新手】CORSMiddleware 配置
5. 【进阶】中间件执行顺序（洋葱模型）
6. 【进阶】修改请求与响应
7. 【进阶】request.state 跨层传递数据
8. 思考题：中间件抛异常时，下游路由还会执行吗？
