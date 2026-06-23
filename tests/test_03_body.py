"""task-3 测试：请求体与 Pydantic BaseModel。

8 条测试覆盖 POST /posts 的：
- 合法创建
- 缺字段
- 字段越界
- 嵌套模型
- 默认值
- alias 别名
- 未知字段忽略
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_post_success() -> None:
    """合法 JSON 返回 201 + 文章对象。"""
    resp = client.post(
        "/posts",
        json={"title": "New Post", "content": "Hello"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "New Post"
    assert body["content"] == "Hello"
    assert "id" in body


def test_create_post_missing_title() -> None:
    """缺 title → 422。"""
    resp = client.post("/posts", json={"content": "Hello"})
    assert resp.status_code == 422


def test_create_post_title_too_long() -> None:
    """title 长度 > 200 → 422。"""
    resp = client.post(
        "/posts",
        json={"title": "x" * 201, "content": "y"},
    )
    assert resp.status_code == 422


def test_create_post_with_nested_metadata() -> None:
    """metadata 嵌套模型正常解析。"""
    resp = client.post(
        "/posts",
        json={
            "title": "T",
            "content": "C",
            "metadata": {
                "seo_title": "SEO",
                "seo_description": "Desc",
                "cover_color": "#ff0000",
            },
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["metadata"]["seo_title"] == "SEO"
    assert body["metadata"]["cover_color"] == "#ff0000"


def test_create_post_tags_default_empty() -> None:
    """不传 tags → 默认空列表。"""
    resp = client.post("/posts", json={"title": "T", "content": "C"})
    assert resp.status_code == 201
    assert resp.json()["tags"] == []


def test_create_post_published_default_false() -> None:
    """不传 published → 默认 false。"""
    resp = client.post("/posts", json={"title": "T", "content": "C"})
    assert resp.status_code == 201
    assert resp.json()["published"] is False


def test_create_post_with_alias() -> None:
    """用 alias 字段名（keywords）输入也能解析为 tags。"""
    resp = client.post(
        "/posts",
        json={"title": "T", "content": "C", "keywords": ["py", "fastapi"]},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["tags"] == ["py", "fastapi"]


def test_create_post_unknown_field_ignored() -> None:
    """未知字段（extra="ignore"）被静默忽略，不报错。"""
    resp = client.post(
        "/posts",
        json={"title": "T", "content": "C", "unknown_field": "x"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "unknown_field" not in body
