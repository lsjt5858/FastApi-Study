# task-17: 项目结构与分层架构

## 目标
把博客代码按生产项目重组：`app/api/routers/{posts,users,comments,auth}.py` + `app/core/{config,security,deps}.py` + `app/crud/` + `app/models/` + `app/schemas/` + `app/services/`；用 pydantic-settings 管理 Settings。

## 涉及文件
- `app/core/config.py`（Settings）
- `app/api/routers/posts.py` / `users.py` / `comments.py` / `auth.py` / `stats.py`
- `app/api/__init__.py`（聚合 routers）
- `app/crud/__init__.py`
- `app/models/__init__.py`
- `app/schemas/__init__.py`
- `app/services/__init__.py`
- `app/main.py`（include_router）
- `.env.example`
- `docs/lessons/17-structure.md`
- `tests/test_17_structure.py`

## 验收标准
- [ ] Settings 用 pydantic-settings，含 DATABASE_URL/SECRET_KEY/DEBUG/REDIS_URL
- [ ] 环境变量覆盖默认值
- [ ] SECRET_KEY 不出现在 OpenAPI 中（secret=True）
- [ ] 每个 router 在独立文件，main.py 用 include_router 聚合
- [ ] settings 是单例
- [ ] .env.example 提供模板
- [ ] 跨模块依赖（author→post）正常
- [ ] 8 条测试全绿

## 测试点（至少 8 条）
1. `test_settings_default_loads`：Settings 默认值加载
2. `test_env_var_overrides_setting`：环境变量覆盖
3. `test_secret_key_not_in_openapi`：SECRET_KEY 在 schema 中隐藏
4. `test_routers_registered`：main.py include_router 数量正确
5. `test_cross_module_dependency`：posts router 依赖 authors
6. `test_settings_singleton`：多次实例化返回同一实例
7. `test_env_file_switch`：用 .env.test 切换配置
8. `test_config_type_validation`：传错类型给 DEBUG 抛错

## 实现要点
```python
# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")
    DATABASE_URL: str = "sqlite+aiosqlite:///./blog.db"
    SECRET_KEY: SecretStr = SecretStr("change-me")
    DEBUG: bool = False
    REDIS_URL: str = "redis://localhost:6379/0"

settings = Settings()  # 单例

# app/api/routers/posts.py
from fastapi import APIRouter, Depends
router = APIRouter(prefix="/posts", tags=["posts"])

@router.get("/")
async def list_posts(db = Depends(get_db)): ...

# app/main.py
from fastapi import FastAPI
from app.api.routers import posts, users, comments, auth, stats

app = FastAPI(title="Blog API", version="2.0.0")
for r in (posts, users, comments, auth, stats):
    app.include_router(r.router)
```
- 用 `pydantic-settings` 替代 v1 的 `BaseSettings`（包名已迁移）
- `SecretStr` 在 repr 时隐藏值，避免日志泄露

## 教学文档大纲
1. 【新手】为什么不能把所有代码写 main.py
2. 【新手】分层架构（router / service / crud / model / schema）
3. 【新手】pydantic-settings 基础
4. 【进阶】.env 与多环境
5. 【进阶】SecretStr 与敏感配置
6. 【进阶】单例 vs 依赖注入
7. 【进阶】领域驱动设计（DDD）入门
8. 思考题：Settings 应该是全局单例还是依赖注入？
