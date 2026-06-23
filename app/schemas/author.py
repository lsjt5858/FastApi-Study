"""task-5 引入：作者对外模型。

AuthorOut 只暴露安全字段，过滤掉 password / email / is_active 等内部状态。
model_config = ConfigDict(from_attributes=True) 让 SQLAlchemy ORM 对象直接转响应。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AuthorOut(BaseModel):
    """作者对外响应模型（不含 password / email / 内部状态）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str | None = None
