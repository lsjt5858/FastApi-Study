"""task-7 测试：Pydantic 校验器与自定义类型。

8 条测试覆盖：
- field_validator: title strip、tags 去重+小写
- model_validator: slug 自动生成
- Annotated + AfterValidator: 手机号
- computed_field: excerpt
- Optional 跳过校验
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_title_stripped() -> None:
    """title 含前后空格 → 自动去除。"""
    resp = client.post("/posts", json={"title": "  Hello  ", "content": "C"})
    assert resp.status_code == 201
    assert resp.json()["title"] == "Hello"


def test_slug_generated_from_title() -> None:
    """title 'Hello World' → slug 'hello-world'。"""
    resp = client.post("/posts", json={"title": "Hello World", "content": "C"})
    assert resp.status_code == 201
    assert resp.json()["slug"] == "hello-world"


def test_tags_deduplicated() -> None:
    """tags ['py', 'py', 'fastapi'] → ['py', 'fastapi']。"""
    resp = client.post(
        "/posts",
        json={"title": "T", "content": "C", "tags": ["py", "py", "fastapi"]},
    )
    assert resp.status_code == 201
    assert resp.json()["tags"] == ["py", "fastapi"]


def test_tags_lowercased() -> None:
    """tags ['PY'] → ['py']。"""
    resp = client.post(
        "/posts",
        json={"title": "T", "content": "C", "tags": ["PY"]},
    )
    assert resp.status_code == 201
    assert resp.json()["tags"] == ["py"]


def test_email_lowercased() -> None:
    """POST /authors/preview: User@Example.COM → user@example.com。"""
    resp = client.post(
        "/authors/preview",
        json={"username": "Alice", "email": "User@Example.COM", "password": "password123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "user@example.com"


def test_invalid_phone_number() -> None:
    """非法手机号 → 422。"""
    resp = client.post(
        "/authors/preview",
        json={"username": "X", "email": "x@y.com", "phone": "abc123"},
    )
    assert resp.status_code == 422


def test_computed_excerpt() -> None:
    """computed_field excerpt = content 前 50 字。"""
    long_content = "x" * 100
    resp = client.post(
        "/posts",
        json={"title": "T", "content": long_content},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["excerpt"] == "x" * 50
    assert len(body["excerpt"]) == 50


def test_optional_field_skipped() -> None:
    """Optional 字段（phone）为 None 时不触发校验。"""
    resp = client.post(
        "/authors/preview",
        json={"username": "X", "email": "x@y.com", "password": "password123"},  # 不传 phone
    )
    assert resp.status_code == 200
    assert resp.json()["phone"] is None


def test_valid_phone_number_accepted() -> None:
    """合法手机号 → 200。"""
    resp = client.post(
        "/authors/preview",
        json={
            "username": "X",
            "email": "x@y.com",
            "phone": "+8613800138000",
            "password": "password123",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["phone"] == "+8613800138000"
