"""task-4 测试：Header / Cookie / Form / 文件上传。

8 条测试覆盖 POST /posts/{post_id}/cover：
- 合法上传
- 文本内容也能读字节
- 缺 token / 缺 Form 字段 / 缺 Cookie
- 文件过大 / 错误类型
- 多文件同时上传
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# 真实 PNG magic bytes（最小可识别 PNG）
PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 32


def test_upload_cover_png_success() -> None:
    """合法 PNG 上传 → 201。"""
    resp = client.post(
        "/posts/1/cover",
        files={"file": ("cover.png", PNG_MAGIC, "image/png")},
        data={"alt_text": "A cover"},
        headers={"X-Upload-Token": "valid-token"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["post_id"] == 1
    assert body["alt_text"] == "A cover"
    assert body["size"] == len(PNG_MAGIC)


def test_upload_cover_text_file_can_read() -> None:
    """content_type=image/png 但内容是文本，接口仍能正确读取字节。"""
    text_content = b"hello world, this is text bytes"
    resp = client.post(
        "/posts/1/cover",
        files={"file": ("cover.png", text_content, "image/png")},
        data={"alt_text": "X"},
        headers={"X-Upload-Token": "valid-token"},
    )
    assert resp.status_code == 201
    assert resp.json()["size"] == len(text_content)


def test_upload_missing_token_returns_401() -> None:
    """缺 X-Upload-Token → 401。"""
    resp = client.post(
        "/posts/1/cover",
        files={"file": ("cover.png", PNG_MAGIC, "image/png")},
        data={"alt_text": "X"},
        # 故意不传 token
    )
    assert resp.status_code == 401


def test_upload_missing_alt_text_returns_422() -> None:
    """缺 Form 字段 alt_text → 422。"""
    resp = client.post(
        "/posts/1/cover",
        files={"file": ("cover.png", PNG_MAGIC, "image/png")},
        # 故意不传 alt_text
        headers={"X-Upload-Token": "valid-token"},
    )
    assert resp.status_code == 422


def test_upload_no_cookie_does_not_fail() -> None:
    """缺 upload_session_id Cookie 也能成功（默认 None）。"""
    resp = client.post(
        "/posts/1/cover",
        files={"file": ("cover.png", PNG_MAGIC, "image/png")},
        data={"alt_text": "X"},
        headers={"X-Upload-Token": "valid-token"},
        # 故意不传 Cookie
    )
    assert resp.status_code == 201
    # 缺 Cookie 时 session_id 应为 None
    assert resp.json()["session_id"] is None


def test_upload_too_large_returns_413() -> None:
    """超过 5MB → 413。"""
    big = b"x" * (5 * 1024 * 1024 + 100)  # 5MB + 100B
    resp = client.post(
        "/posts/1/cover",
        files={"file": ("big.png", big, "image/png")},
        data={"alt_text": "X"},
        headers={"X-Upload-Token": "valid-token"},
    )
    assert resp.status_code == 413


def test_upload_wrong_content_type_returns_415() -> None:
    """content_type=text/plain（非图片）→ 415。"""
    resp = client.post(
        "/posts/1/cover",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"alt_text": "X"},
        headers={"X-Upload-Token": "valid-token"},
    )
    assert resp.status_code == 415


def test_upload_multiple_files_at_once() -> None:
    """一次上传 2 个文件（多 UploadFile）→ 201。"""
    resp = client.post(
        "/posts/1/covers",
        files=[
            ("files", ("a.png", PNG_MAGIC, "image/png")),
            ("files", ("b.jpeg", JPEG_MAGIC, "image/jpeg")),
        ],
        data={"alt_text": "Two covers"},
        headers={"X-Upload-Token": "valid-token"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["count"] == 2
    assert body["post_id"] == 1
