"""task-12 / task-17：全局配置（pydantic-settings）。

用 BaseSettings 自动从环境变量 + .env 读取；敏感字段用 SecretStr。
"""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。

    生产 SECRET_KEY 必须从环境变量注入；开发期有默认值。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite+aiosqlite:///./blog.db"
    SECRET_KEY: SecretStr = SecretStr("dev-only-not-for-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"
    DEBUG: bool = False
    REDIS_URL: str = "redis://localhost:6379/0"


settings = Settings()
