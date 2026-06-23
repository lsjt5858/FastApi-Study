"""task-4 引入：文件上传服务。

负责：
- 校验 content_type 是否在白名单
- 流式读取 UploadFile，并在超过 MAX_SIZE 时抛 413
- 读取字节数据（task-4 仅返回 in-memory；task-19 部署时会落盘）
"""

from __future__ import annotations

from fastapi import HTTPException, UploadFile

# 允许的图片 MIME 类型
ALLOWED_TYPES: set[str] = {"image/png", "image/jpeg", "image/webp"}

# 单文件最大 5MB
MAX_SIZE: int = 5 * 1024 * 1024


async def validate_and_read(file: UploadFile) -> bytes:
    """校验类型 → 流式读取 → 校验大小，返回完整字节。

    流式读取的意义：能在还没读完时就发现"太大"提前拒绝，避免 OOM。
    """
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported media type")

    total = 0
    chunks: list[bytes] = []
    while chunk := await file.read(64 * 1024):  # 64KB / chunk
        total += len(chunk)
        if total > MAX_SIZE:
            raise HTTPException(status_code=413, detail="File too large")
        chunks.append(chunk)
    return b"".join(chunks)
