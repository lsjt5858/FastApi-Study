"""task-2 测试：路径参数、查询参数与枚举。

8 条测试覆盖：
1. 默认分页
2. 自定义分页
3. published 过滤
4. status 枚举合法值
5. status 枚举非法值 → 422
6. 路径参数类型校验 → 422
7. str 路径参数
8. 组合查询参数
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import POSTS, app

client = TestClient(app)


def test_list_posts_default_pagination() -> None:
    """GET /posts 默认 limit=10，offset=0；返回前 10 条。"""
    resp = client.get("/posts")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 10  # 默认 limit=10
    # 默认按 id 升序
    assert body[0]["id"] == POSTS[0]["id"]


def test_list_posts_custom_limit_offset() -> None:
    """?limit=5&offset=2 分页生效。"""
    resp = client.get("/posts", params={"limit": 5, "offset": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 5
    # offset=2 跳过前两条，下一组应该是 id=3..7
    ids = [p["id"] for p in body]
    assert ids == [3, 4, 5, 6, 7]


def test_list_posts_filter_published() -> None:
    """?published=true 只回 published=true 的文章。"""
    resp = client.get("/posts", params={"published": "true"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0
    assert all(p["published"] is True for p in body)


def test_list_posts_filter_status_enum_valid() -> None:
    """?status=published 正常返回。"""
    resp = client.get("/posts", params={"status": "published"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0
    assert all(p["status"] == "published" for p in body)


def test_list_posts_filter_status_enum_invalid() -> None:
    """?status=xyz 非法枚举值 → 422。"""
    resp = client.get("/posts", params={"status": "xyz"})
    assert resp.status_code == 422
    body = resp.json()
    # FastAPI 在错误详情里列出允许的枚举值
    detail_text = str(body)
    assert "draft" in detail_text
    assert "published" in detail_text
    assert "archived" in detail_text


def test_get_post_id_must_be_int() -> None:
    """/posts/abc 路径参数类型错误 → 422。"""
    resp = client.get("/posts/abc")
    assert resp.status_code == 422


def test_get_user_by_username_str() -> None:
    """/users/{username} 支持 str 路径参数。"""
    resp = client.get("/users/alice")
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "alice"


def test_combined_query_params() -> None:
    """组合 ?limit=5&offset=0&published=true&status=published 生效。"""
    resp = client.get(
        "/posts",
        params={"limit": 5, "offset": 0, "published": "true", "status": "published"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) <= 5
    assert all(p["published"] is True and p["status"] == "published" for p in body)
