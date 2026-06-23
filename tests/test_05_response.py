"""task-5 测试：响应模型 response_model 与状态码。

8 条测试覆盖：
- 响应过滤敏感字段（is_deleted、author.password）
- response_model_exclude / include
- 状态码 201
- 自定义 404 JSON 结构
- Set-Cookie / 自定义 header
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_post_out_excludes_is_deleted() -> None:
    """GET /posts 的响应模型过滤掉 is_deleted 字段。"""
    resp = client.get("/posts")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0
    for post in body:
        assert "is_deleted" not in post, f"is_deleted 不该出现在响应: {post}"


def test_post_out_excludes_author_password() -> None:
    """嵌套 author 字段不含 password。"""
    resp = client.get("/posts")
    assert resp.status_code == 200
    body = resp.json()
    # 至少有一个 post 有 author
    authors = [p["author"] for p in body if p.get("author")]
    assert len(authors) > 0, "测试需要至少一个 post 有 author 字段"
    for author in authors:
        assert "password" not in author, f"author 不该含 password: {author}"


def test_response_model_exclude() -> None:
    """GET /posts/{id}/full 用 exclude 隐藏 metadata。"""
    # 先创建一个带 metadata 的文章
    created = client.post(
        "/posts",
        json={
            "title": "T",
            "content": "C",
            "metadata": {"seo_title": "S", "cover_color": "#fff"},
        },
    )
    assert created.status_code == 201
    new_id = created.json()["id"]

    resp = client.get(f"/posts/{new_id}/full")
    assert resp.status_code == 200
    body = resp.json()
    assert "metadata" not in body
    assert "title" in body  # 其他字段还在


def test_response_model_include() -> None:
    """GET /posts/{id}/brief 用 include 只暴露 id + title。"""
    resp = client.get("/posts/1/brief")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"id", "title"}


def test_create_post_returns_201() -> None:
    """POST /posts 状态码 201。"""
    resp = client.post("/posts", json={"title": "T", "content": "C"})
    assert resp.status_code == 201


def test_404_custom_json_structure() -> None:
    """GET /posts/9999 返回自定义错误结构 {error: {code, message}}。"""
    resp = client.get("/posts/9999")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "POST_NOT_FOUND"
    assert "message" in body["error"]


def test_response_sets_cookie() -> None:
    """POST /posts 响应设置 Set-Cookie。"""
    resp = client.post("/posts", json={"title": "Cookied", "content": "C"})
    assert resp.status_code == 201
    set_cookie = resp.headers.get("set-cookie", "")
    assert "last_create" in set_cookie


def test_response_custom_header() -> None:
    """POST /posts 响应含 X-Blog-Version 头。"""
    resp = client.post("/posts", json={"title": "H", "content": "C"})
    assert resp.status_code == 201
    assert resp.headers.get("X-Blog-Version") is not None
    assert resp.headers["X-Blog-Version"]  # 非空
