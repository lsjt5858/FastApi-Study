# task-4: Header / Cookie / Form / 文件上传

## 目标
实现 POST /posts/{post_id}/cover 上传文章封面，同时演示 Header、Cookie、Form、UploadFile 四种"非 JSON"输入。

## 涉及文件
- `app/main.py`（新增封面上传接口）
- `app/services/upload.py`（文件保存/校验逻辑）
- `docs/lessons/04-form-file.md`
- `tests/test_04_form_file.py`

## 验收标准
- [ ] POST /posts/{post_id}/cover 接收 UploadFile（封面）+ Form 字段 alt_text + Header X-Upload-Token + Cookie upload_session_id
- [ ] 缺 X-Upload-Token 返回 401
- [ ] 缺 Form 字段返回 422
- [ ] 文件大小超限返回 413
- [ ] 文件类型不在白名单返回 415
- [ ] 支持大文件分块读取（async iterate chunks）
- [ ] 多文件同时上传（multiple UploadFile）
- [ ] 8 条测试全绿

## 测试点（至少 8 条）
1. `test_upload_cover_png_success`：上传合法 PNG 返回 201
2. `test_upload_cover_text_file_can_read`：上传 .txt 也能读字节
3. `test_upload_missing_token_returns_401`：缺 X-Upload-Token 返回 401
4. `test_upload_missing_alt_text_returns_422`：缺 Form 字段 alt_text 返回 422
5. `test_upload_no_cookie_does_not_fail`：缺 Cookie 不报错（默认 None）
6. `test_upload_too_large_returns_413`：超 5MB 返回 413
7. `test_upload_wrong_content_type_returns_415`：上传 .exe 返回 415
8. `test_upload_multiple_files_at_once`：一次上传 2 个文件

## 实现要点
```python
from fastapi import UploadFile, File, Form, Header, Cookie, HTTPException
from typing import Annotated

ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_SIZE = 5 * 1024 * 1024

@app.post("/posts/{post_id}/cover", status_code=201)
async def upload_cover(
    post_id: int,
    file: UploadFile = File(...),
    alt_text: str = Form(..., min_length=1, max_length=200),
    x_upload_token: Annotated[str, Header()] = None,
    upload_session_id: Annotated[str | None, Cookie()] = None,
):
    if not x_upload_token:
        raise HTTPException(401, "Missing upload token")
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Unsupported media type")
    # 边读边校验大小
    total = 0
    chunks = []
    while chunk := await file.read(64 * 1024):
        total += len(chunk)
        if total > MAX_SIZE:
            raise HTTPException(413, "File too large")
        chunks.append(chunk)
    data = b"".join(chunks)
    # 保存到 services/upload.py 提供的存储路径...
    return {"post_id": post_id, "size": total, "alt_text": alt_text}
```
- 上传接口的 Content-Type 必须是 `multipart/form-data`，TestClient 用 `files=` 和 `data=` 参数
- 大文件用 `async for chunk in file` 流式读取，避免 OOM

## 教学文档大纲
1. 【新手】为什么上传文件不能用 application/json
2. 【新手】UploadFile vs bytes（小文件可以直接 bytes）
3. 【新手】Form 与 Query 的区别
4. 【新手】Header 自动加 X- 前缀的处理
5. 【进阶】Cookie 的安全性（HttpOnly、Secure、SameSite）
6. 【进阶】分块读取大文件
7. 【进阶】Annotated 风格的参数声明
8. 思考题：为什么 Header 参数名 x_upload_token 在 Python 里要小写？
