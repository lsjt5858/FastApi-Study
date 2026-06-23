"""task-12：密码哈希 + JWT 工具。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext

# bcrypt 哈希（自动处理 salt）
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(plain: str) -> str:
    """密码哈希。"""
    return pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码。"""
    try:
        return pwd_ctx.verify(plain, hashed)
    except Exception:
        return False


def create_access_token(
    subject: str,
    expires_minutes: int = 60,
    secret: str = "",
    extra: dict | None = None,
) -> str:
    """签发 JWT。exp 用 UTC 时间。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str, secret: str) -> dict:
    """解 token；签名错/过期/格式错都抛 401。"""
    try:
        return jwt.decode(token, secret, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
