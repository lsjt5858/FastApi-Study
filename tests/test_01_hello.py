"""task-1 测试：博客骨架与第一个 FastAPI 应用。

按 docs/plans/task-1.md 的 8 条测试点编写，确认以下能力：
1. GET / 返回博客信息
2. GET /health 健康检查
3. GET /posts/{id} 返回单篇
4. GET /posts/9999 返回 404
5. GET /docs 自动文档可访问
6. GET /openapi.json 返回 schema
7. JSON 响应 Content-Type 正确
8. 50 次并发请求稳定
"""

from __future__ import annotations

import threading

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_blog_info() -> None:
    """GET / 返回 name / version / docs_url 三个字段。"""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Blog API"
    assert body["version"] == "0.1.0"
    assert body["docs_url"] == "/docs"


def test_health_endpoint() -> None:
    """GET /health 返回 status=ok。"""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_get_post_by_id() -> None:
    """GET /posts/1 返回第一篇文章。"""
    resp = client.get("/posts/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 1
    assert "title" in body
    assert "content" in body


def test_get_post_not_found() -> None:
    """GET /posts/9999 返回 404。"""
    resp = client.get("/posts/9999")
    assert resp.status_code == 404


def test_docs_ui_accessible() -> None:
    """GET /docs 返回 200 且 text/html。"""
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_openapi_schema() -> None:
    """GET /openapi.json 返回合法 schema，含 paths 字段。"""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema.get("openapi", "").startswith("3.")
    assert "paths" in schema
    # 关键路径必须出现在 schema 中
    paths = schema["paths"]
    assert "/" in paths
    assert "/health" in paths
    assert "/posts/{post_id}" in paths


def test_json_content_type() -> None:
    """所有 JSON 响应 Content-Type=application/json。"""
    for path in ("/", "/health", "/posts/1"):
        resp = client.get(path)
        ct = resp.headers.get("content-type", "")
        assert ct.startswith("application/json"), f"{path} 返回非 JSON: {ct}"


def test_concurrent_requests_stable() -> None:
    """50 次并发请求根路径都返回 200。

    用线程模拟并发（TestClient 基于 sync 接口）。
    """
    results: list[int] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            resp = client.get("/")
            results.append(resp.status_code)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"并发请求出错: {errors[:3]}"
    assert len(results) == 50
    assert all(code == 200 for code in results), f"非 200: {set(results)}"
