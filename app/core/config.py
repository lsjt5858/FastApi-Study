"""task-12：全局配置（用 pydantic-settings 自动从环境变量读）。"""

from __future__ import annotations

import os
import secrets

from pydantic import BaseModel


class Settings(BaseModel):
    """应用配置。生产 SECRET_KEY 必须从环境变量注入。"""

    SECRET_KEY: str = os.environ.get("SECRET_KEY", "") or secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"


settings = Settings()
