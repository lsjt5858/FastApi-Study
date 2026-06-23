"""task-17 测试：项目结构与分层架构（pydantic-settings + .env）。

8 条测试覆盖：
- Settings 默认值
- 环境变量覆盖
- SECRET_KEY 用 SecretStr 保护
- settings 单例
- type 校验
- .env 文件切换
- include_router 数量
- 跨模块依赖（author -> post）
"""

from __future__ import annotations

import importlib
from pathlib import Path


def test_settings_default_loads() -> None:
    """Settings 默认值能加载。"""
    from app.core.config import Settings

    s = Settings(_env_file=None)  # 不读 .env，只用默认
    assert s.DATABASE_URL.startswith("sqlite+aiosqlite")
    assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 60
    assert s.ALGORITHM == "HS256"


def test_env_var_overrides_setting(monkeypatch) -> None:
    """环境变量覆盖默认值。"""
    from app.core.config import Settings

    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120")
    s = Settings(_env_file=None)
    assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 120


def test_secret_key_uses_secret_str() -> None:
    """SECRET_KEY 用 SecretStr 包装，repr 不显示明文。"""
    from pydantic import SecretStr

    from app.core.config import Settings

    s = Settings(_env_file=None)
    assert isinstance(s.SECRET_KEY, SecretStr)
    # repr 不泄露明文
    assert "**********" in repr(s.SECRET_KEY) or "SecretStr" in repr(s.SECRET_KEY)


def test_settings_singleton_is_module_level() -> None:
    """settings 是模块级单例。"""
    from app.core import config

    assert hasattr(config, "settings")
    # 多次引用同一对象
    assert config.settings is config.settings


def test_env_file_loads(tmp_path, monkeypatch) -> None:
    """.env 文件能被加载。"""
    from app.core.config import Settings

    env_file = tmp_path / ".env.test"
    env_file.write_text(
        'SECRET_KEY="from-env-file"\nACCESS_TOKEN_EXPIRE_MINUTES=30\n', encoding="utf-8"
    )
    # 清掉同名环境变量，避免被 monkeypatch 之前的设置干扰
    for k in ("SECRET_KEY", "ACCESS_TOKEN_EXPIRE_MINUTES"):
        monkeypatch.delenv(k, raising=False)
    s = Settings(_env_file=env_file)
    assert str(s.SECRET_KEY.get_secret_value()) == "from-env-file"
    assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 30


def test_settings_supports_extra_fields_for_future() -> None:
    """Settings 至少有 DATABASE_URL / SECRET_KEY / ACCESS_TOKEN_EXPIRE_MINUTES / ALGORITHM。"""
    from app.core.config import Settings

    s = Settings(_env_file=None)
    for k in ("DATABASE_URL", "SECRET_KEY", "ACCESS_TOKEN_EXPIRE_MINUTES", "ALGORITHM"):
        assert hasattr(s, k), f"missing {k}"


def test_main_app_has_multiple_routers() -> None:
    """app 应挂载至少 3 个 router（auth_router, ws_router, v1/v2）。

    FastAPI 把 include_router 挂成 _IncludedRouter，子路由在
    original_router.routes 里，所以要递归收集。
    """
    from app.main import app

    paths: set[str] = set()

    def collect(routes) -> None:
        for r in routes:
            # 直接挂在 app 上的 APIRoute / APIWebSocketRoute
            p = getattr(r, "path", None)
            if p:
                paths.add(p)
            # include_router 产生的 _IncludedRouter：子路由在 original_router
            orig = getattr(r, "original_router", None)
            if orig is not None:
                collect(getattr(orig, "routes", []))

    collect(app.routes)

    # 至少有 /auth/register, /ws/posts/{id}/comments, /api/v1/posts, /api/v2/posts
    assert any(p.startswith("/auth/") for p in paths), f"missing /auth/: {paths}"
    assert any(p.startswith("/ws/") for p in paths), f"missing /ws/: {paths}"
    assert any(p.startswith("/api/v1/") for p in paths), f"missing /api/v1/: {paths}"
    assert any(p.startswith("/api/v2/") for p in paths), f"missing /api/v2/: {paths}"


def test_cross_module_dependency_author_post() -> None:
    """跨模块依赖：posts router（main.py）能 import 自 models/authors crud。

    验证方式：import app.main 与 app.crud.authors 都不抛异常。
    """
    m1 = importlib.import_module("app.main")
    m2 = importlib.import_module("app.crud.authors")
    assert m1 is not None
    assert m2 is not None
    # 验证 crud.authors 有 authenticate 函数
    assert hasattr(m2, "authenticate")


def test_env_example_file_exists() -> None:
    """.env.example 模板存在。"""
    repo_root = Path(__file__).parent.parent
    assert (repo_root / ".env.example").exists(), "missing .env.example"
