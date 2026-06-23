# 第 1 课 · 项目骨架与第一个 FastAPI 应用

> 难度：【新手】为主，末尾含【进阶】延伸。
>
> 学完本节，你能用 5 分钟跑起一个博客 API 骨架，访问自动文档 `/docs`，并理解 FastAPI 的核心组成。

---

## 1.1 【新手】FastAPI 是什么

**FastAPI** 是一个基于 Python 的现代 Web 框架，用来构建 HTTP API（即"后端接口"）。

它由 Sebastián Ramírez（tiangolo）于 2018 年开源，截至 2026 年已是 Python Web 框架里活跃度最高的几个之一。

**为什么选 FastAPI？**

| 特性 | 说明 |
|---|---|
| 快（性能） | 基于 Starlette（ASGI），单机吞吐量级与 Node.js / Go 相当 |
| 快（开发） | 类型注解 → 自动校验、自动文档、自动 IDE 提示三件套 |
| 标准 | 完全兼容 OpenAPI 3 / JSON Schema |
| 异步原生 | `async def` 一等公民 |
| 类型友好 | 底层 Pydantic，Python 类型注解即接口契约 |

---

## 1.2 【新手】安装

需要 Python 3.10+。在项目目录里：

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install "fastapi[standard]"    # 含 uvicorn、httptools 等高性能依赖
```

> 本教学项目用 `pyproject.toml` 锁定依赖，执行 `pip install -e ".[dev]"` 即可。

---

## 1.3 【新手】最小代码示例

**`app/main.py`**：

```python
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Blog API", version="0.1.0")

POSTS = [
    {"id": 1, "title": "Hello Blog", "content": "First post."},
    {"id": 2, "title": "FastAPI 101", "content": "Why FastAPI."},
]

@app.get("/")
def root():
    return {"name": app.title, "version": app.version, "docs_url": "/docs"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/posts/{post_id}")
def get_post(post_id: int):
    for post in POSTS:
        if post["id"] == post_id:
            return post
    raise HTTPException(status_code=404, detail="Post not found")
```

**三件事看懂它**：

1. `app = FastAPI(...)` —— 创建一个 ASGI 应用实例
2. `@app.get("/path")` —— 装饰器声明路由：访问 `GET /path` 就执行这个函数
3. `post_id: int` —— Python 类型注解会被 FastAPI 用来做**自动类型校验**（task-2 会展开）

---

## 1.4 【新手】启动与访问

```bash
uvicorn app.main:app --reload
```

含义：用 `uvicorn`（一个 ASGI 服务器）启动 `app/main.py` 文件里的 `app` 对象，`--reload` 表示代码改动自动重启。

打开浏览器：

| 地址 | 看到什么 |
|---|---|
| http://127.0.0.1:8000/ | JSON 响应 `{"name":"Blog API",...}` |
| http://127.0.0.1:8000/health | `{"status":"ok"}` |
| http://127.0.0.1:8000/posts/1 | 第一篇文章 |
| http://127.0.0.1:8000/posts/9999 | `{"detail":"Post not found"}` + 404 |
| http://127.0.0.1:8000/docs | **Swagger UI 自动文档**（点击就能试调用） |
| http://127.0.0.1:8000/openapi.json | 原始 OpenAPI 3 JSON |

> **关键认知**：你没有写一行"生成文档"的代码，`/docs` 和 `/openapi.json` 是 FastAPI 根据你的类型注解**免费送**的。

---

## 1.5 【进阶】ASGI vs WSGI

| 概念 | 全称 | 调用模型 | 代表框架 |
|---|---|---|---|
| WSGI | Web Server Gateway Interface | 同步，一个请求一个线程 | Django、Flask（原生） |
| ASGI | Asynchronous Server Gateway Interface | 异步，事件循环 + await | FastAPI、Starlette、Litestar |

FastAPI 跑在 ASGI 服务器上（uvicorn / hypercorn / daphne），所以 `async def` 路由是原生支持的。这是它能做 WebSocket（task-14）和长连接的根基。

---

## 1.6 【进阶】FastAPI 的"三层蛋糕"

```
┌──────────────────────────────────┐
│  FastAPI                         │ ← 路由装饰器、依赖注入、自动文档
├──────────────────────────────────┤
│  Starlette                       │ ← ASGI 应用、中间件、WebSocket、TestClient
├──────────────────────────────────┤
│  Pydantic                        │ ← 数据校验、序列化、类型转换
└──────────────────────────────────┘
```

- 你写的 `def get_post(post_id: int)` → Pydantic 把 URL 里的 `"1"` 转成 `int` 并校验
- 返回的 `dict` → Starlette 把它序列化为 JSON 响应
- 全程 → FastAPI 同时把这一切登记到 OpenAPI schema

后续每个 task 本质上是在这三层里"开新功能开关"。

---

## 1.7 思考题

1. 如果把 `get_post(post_id: int)` 改成 `get_post(post_id: str)`，访问 `/posts/1` 还会 200 吗？为什么？
2. 如果把 `raise HTTPException(404, ...)` 改成 `return {"error": "not found"}`，HTTP 状态码会变成什么？前端怎么区分"成功"和"失败"？
3. `/docs` 是怎么从你的 Python 代码"自动生成"的？如果一个路由没写任何类型注解，文档里会显示什么？

---

## 1.8 本节交付物

| 文件 | 作用 |
|---|---|
| `app/__init__.py` | 让 `app/` 成为 Python 包 |
| `app/main.py` | FastAPI 实例 + 3 个路由 |
| `tests/test_01_hello.py` | 8 条 pytest 测试，全绿 |
| `docs/lessons/01-hello.md` | 本文（教学文档） |

---

## 1.9 下一节预告

第 2 课我们会把 `GET /posts` 扩展为支持 `?limit=10&offset=0&published=true&status=published` 的"分页 + 过滤"接口，引入 **Enum 枚举** 与 **查询参数校验**。
