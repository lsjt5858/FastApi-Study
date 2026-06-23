"""task-5 / task-7 引入：作者模型。

- AuthorOut: 对外响应模型（过滤 password/email）
- AuthorCreate: 注册时的请求体（task-7 加 email 自动 lower + phone 自定义校验）
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.types import PhoneNumber

# 简化的 email 正则（不引入额外 email-validator 依赖）
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthorOut(BaseModel):
    """作者对外响应模型（不含 password / email / 内部状态）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str | None = None


class AuthorCreate(BaseModel):
    """作者注册请求体（task-7 新增）。

    - email 字段自动 lower
    - phone 用 PhoneNumber 自定义类型（Annotated + AfterValidator）
    """

    model_config = ConfigDict(extra="ignore")

    username: str = Field(min_length=1, max_length=50)
    email: str
    phone: PhoneNumber | None = None
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        v = v.lower()
        if not _EMAIL_RE.match(v):
            raise ValueError(f"Invalid email: {v}")
        return v
