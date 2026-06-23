# task-1: 项目骨架与第一个 FastAPI 应用

## 目标
搭建博客项目骨架，让学习者 5 分钟内启动并访问自动文档 /docs，理解 FastAPI = 路由 + Pydantic + ASGI。

## 涉及文件
- `app/__init__.py`（空文件）
- `app/main.py`（FastAPI 实例 + 3 个路由）
- `docs/lessons/01-hello.md`（教学文档）
- `tests/__init__.py`（空文件）
- `tests/test_01_hello.py`（8 条测试）
- `pyproject.toml` 或 `requirements.txt`（依赖锁定）

## 验收标准
- [ ] `uvicorn app.main:app --reload` 能启动
- [ ] GET / 返回 `{name:"Blog API", version:"0.1.0", docs_url:"/docs"}`
- [ ] GET /health 返回 `{status:"ok"}`
- [ ] GET /posts/{post_id} 从内存 POSTS 返回单篇
- [ ] GET /posts/9999 返回 404
- [ ] GET /docs 与 GET /openapi.json 都 200
- [ ] 8 条测试全绿
- [ ] 后续 task 复用 app/main.py 骨架

## 测试点（至少 8 条）
1. `test_root_returns_blog_info`：GET / 返回 name 字段
2. `test_health_endpoint`：GET /health 200 + status=ok
3. `test_get_post_by_id`：GET /posts/1 返回第一篇文章
4. `test_get_post_not_found`：GET /posts/9999 返回 404
5. `test_docs_ui_accessible`：GET /docs 返回 200 + text/html
6. `test_openapi_schema`：GET /openapi.json 包含 paths 字段
7. `test_json_content_type`：所有 JSON 响应 Content-Type=application/json
8. `test_concurrent_requests_stable`：50 次并发请求根路径都 200

## 实现要点
```python
# app/main.py
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Blog API", version="0.1.0")

POSTS = [
    {"id": 1, "title": "Hello Blog", "content": "First post"},
    {"id": 2, "title": "FastAPI 101", "content": "Why FastAPI"},
]

@app.get("/")
def root():
    return {"name": app.title, "version": app.version, "docs_url": "/docs"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/posts/{post_id}")
def get_post(post_id: int):
    for p in POSTS:
        if p["id"] == post_id:
            return p
    raise HTTPException(status_code=404, detail="Post not found")
```
- 用 `fastapi.testclient.TestClient` 跑测试，避免依赖外部进程
- 内存 POSTS 用模块级 list 模拟，task-11 再换 SQLAlchemy

## 教学文档大纲（docs/lessons/01-hello.md）
1. 【新手】FastAPI 是什么 / 为什么选它
2. 【新手】安装：`pip install "fastapi[standard]"` + uvicorn
3. 【新手】最小代码示例（贴 main.py）
4. 【新手】启动命令 + 访问 127.0.0.1:8000 与 /docs
5. 【进阶】ASGI 与 WSGI 区别
6. 【进阶】FastAPI 内部如何基于 Starlette + Pydantic
7. 思考题：如果把 post_id 改成 str 会怎样？
