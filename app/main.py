"""Blog API — task-1 阶段的最小骨架。

本模块是整个教学项目的入口，后续 task 会在此基础上扩展：
- task-2 加查询参数与枚举
- task-3 加请求体（POST /posts）
- task-4 加文件上传
- ...
- task-11 把 POSTS 换成 SQLAlchemy

现阶段只演示：
1. FastAPI 实例与基本路由
2. 内存数据（POSTS）模拟数据库
3. 自动文档 /docs 与 /openapi.json
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="Blog API",
    version="0.1.0",
    description="Python FastAPI 从入门到精通（博客渐进式实战）",
)

# task-1 阶段用内存 list 模拟数据库；task-11 会替换为 SQLAlchemy 真实数据库
POSTS: list[dict] = [
    {"id": 1, "title": "Hello Blog", "content": "First post. Welcome to the Blog API."},
    {"id": 2, "title": "FastAPI 101", "content": "Why FastAPI is fast and friendly."},
]


@app.get("/")
def root() -> dict:
    """根路径，返回博客基本信息与文档入口。"""
    return {
        "name": app.title,
        "version": app.version,
        "docs_url": "/docs",
    }


@app.get("/health")
def health() -> dict:
    """健康检查端点，供容器 HEALTHCHECK / 负载均衡探活使用。"""
    return {"status": "ok"}


@app.get("/posts/{post_id}")
def get_post(post_id: int) -> dict:
    """按 id 获取单篇文章；不存在则返回 404。"""
    for post in POSTS:
        if post["id"] == post_id:
            return post
    raise HTTPException(status_code=404, detail="Post not found")
