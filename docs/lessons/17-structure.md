# task-17 · 项目结构与分层架构

> 把"能跑"的代码升级成"能维护"的项目：pydantic-settings 管配置、按职责分层、env 驱动。

## 【新手】为什么需要分层

前 16 个 task 我们一路往 `app/main.py` 里塞路由、依赖、模型。能跑，但：

- 配置散落各处：数据库 URL 写死在 `app/db.py`，SECRET_KEY 在 `auth.py`……
- 文件越长越难找：`main.py` 突破 500 行
- 测试时要 mock 不同地方

生产项目的通用解法：

1. **配置集中**：所有配置走 `pydantic-settings`，从环境变量 / `.env` 注入
2. **目录分层**：按职责切分 `api / core / crud / models / schemas / services`
3. **聚合 router**：每个模块自己声明 router，`main.py` 只负责 `include_router`

## 【新手】pydantic-settings 是什么

`pydantic-settings` 是 Pydantic 官方的配置库，继承自 `BaseModel`，多了三件事：

1. 自动从环境变量读值（变量名 = 字段名，大小写敏感可配）
2. 自动从 `.env` 文件读值
3. 用 `SecretStr` 保护敏感字段，`repr` 不泄露明文

### 最小例子

```python
# app/core/config.py
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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


settings = Settings()  # 模块级单例，import 即装配
```

### 优先级

```
环境变量 > .env 文件 > 代码默认值
```

所以生产部署只要 `docker run -e SECRET_KEY=xxx ...`，代码零改动。

### `SecretStr` 防泄露

```python
>>> settings.SECRET_KEY
SecretStr('**********')
>>> settings.SECRET_KEY.get_secret_value()
'真实密钥'
```

`repr` 看不到明文，日志、错误堆栈里也不会泄露。**只有真的要用时才调 `.get_secret_value()`**。

## 【进阶】目录分层

```
app/
├── main.py              # 应用入口：lifespan、middleware、include_router
├── api/                 # HTTP / WS 接口层（路由）
│   ├── auth.py          #   注册 / 登录 / JWT
│   ├── ws_comments.py   #   WebSocket 评论
│   └── versioned.py     #   v1 / v2 版本化路由
├── core/                # 基础设施层
│   ├── config.py        #   Settings
│   ├── security.py      #   密码哈希 / JWT 编解码
│   ├── deps.py          #   通用 Depends
│   ├── middleware.py    #   中间件
│   ├── exceptions.py    #   业务异常 + handler
│   └── ws_manager.py    #   WebSocket 房间管理
├── crud/                # 数据访问层（DB 增删改查）
│   ├── posts.py
│   └── authors.py
├── models/              # ORM 模型
├── schemas/             # Pydantic 入参 / 出参模型
├── services/            # 业务服务（外部调用、聚合、定时任务）
└── db.py                # 引擎 / session 工厂
```

**分层规则**：依赖只能向下，不能横穿：

```
api → crud → models
↓       ↓
schemas  db
↓
core
```

`api/auth.py` 不能直接 import `api/versioned.py`。同层之间通过 schema 或 service 解耦。

## 【进阶】include_router 聚合

每个 `api/*.py` 自己声明 `router = APIRouter(prefix=..., tags=[...])`，定义路由；`main.py` 只负责挂载：

```python
# main.py
from app.api.auth import router as auth_router
from app.api.ws_comments import router as ws_router
from app.api.versioned import v1_router, v2_router

app.include_router(auth_router)
app.include_router(ws_router)
app.include_router(v1_router, prefix="/api/v1")
app.include_router(v2_router, prefix="/api/v2")
```

`include_router` 后，FastAPI 内部用 `_IncludedRouter` 包装：**注意 `app.routes` 不会直接展开子路由**，要递归 `original_router.routes` 或查 `/openapi.json`。

```python
# 递归收集路径的正确写法
def collect_paths(routes):
    paths = set()
    for r in routes:
        if hasattr(r, "path"):
            paths.add(r.path)
        if hasattr(r, "original_router"):
            paths |= collect_paths(r.original_router.routes)
    return paths
```

## 【进阶】`.env.example` 模板

仓库根目录放一个 `.env.example`，列出所有可配置项但用占位值；团队同事 `cp .env.example .env` 即可起步：

```ini
DATABASE_URL="sqlite+aiosqlite:///./blog.db"
SECRET_KEY="change-me-with-a-long-random-string"
ACCESS_TOKEN_EXPIRE_MINUTES=60
DEBUG=false
REDIS_URL="redis://localhost:6379/0"
```

**规则**：
- `.env.example` 进 git（模板，无敏感数据）
- `.env` 进 `.gitignore`（真实密钥，绝不进 git）

## 【进阶】测试中如何覆盖 Settings

不要去改环境变量再 reload 模块——太脏。直接构造新的 `Settings` 实例：

```python
def test_env_var_overrides_setting(monkeypatch):
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120")
    s = Settings(_env_file=None)  # 显式不读 .env，只看环境变量 + 默认
    assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 120

def test_env_file_loads(tmp_path, monkeypatch):
    env = tmp_path / ".env.test"
    env.write_text('SECRET_KEY="from-env-file"\nACCESS_TOKEN_EXPIRE_MINUTES=30')
    for k in ("SECRET_KEY", "ACCESS_TOKEN_EXPIRE_MINUTES"):
        monkeypatch.delenv(k, raising=False)  # 清掉真实环境变量
    s = Settings(_env_file=env)
    assert str(s.SECRET_KEY.get_secret_value()) == "from-env-file"
```

注意 `_env_file=None` / `_env_file=<path>` 是 pydantic-settings 内置参数，等价于关掉/覆盖 .env 加载。

## 思考题

1. **为什么 `Settings` 用模块级单例（`settings = Settings()`）而不是函数返回？** 提示：FastAPI `Depends` 缓存机制 + 单测可覆盖。
2. **`SECRET_KEY: SecretStr` 而不是 `str`，到底挡住了什么攻击面？** 提示：日志、APM、错误堆栈、Sentry。
3. **`api/auth.py` 想发邮件，应该 import `services/email.py` 还是直接调用 SMTP？** 提示：分层与可替换性。
4. **`.env` 文件里的 `DATABASE_URL` 改了但程序没生效，可能是什么原因？** 提示：`case_sensitive=True`、变量名拼写、shell 已有同名 export。

## 本次改动

- 新增 `app/core/config.py`：`Settings(BaseSettings)` + `SecretStr`
- 更新 `app/api/auth.py`：JWT 签名/验证改用 `settings.SECRET_KEY.get_secret_value()`
- 更新 `tests/test_12_auth.py::test_me_with_expired_token_401`：同步 SecretStr 取值
- 新增 `tests/test_17_structure.py`：9 条测试覆盖 Settings + 结构
- 新增 `.env.example`：配置模板
