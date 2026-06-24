# Python FastAPI 从入门到精通：博客渐进式实战

这是一套以“博客 API”为主线的 FastAPI 教学项目。项目通过 20 个 task 逐步叠加能力：从最小 API、参数校验、请求体和文件上传，到数据库、JWT、WebSocket、缓存、测试、Docker 部署和端到端综合实战。

最终形态不是一个一次性 demo，而是一个可以本地运行、可以自动化测试、可以容器化部署的迷你博客后端样本。

## 功能概览

- 文章 API：内存版 `/posts` 与数据库版 `/db/posts`
- 作者认证：注册、登录、JWT 签发与解析
- 权限控制：普通 JWT 认证与 admin scope 授权示例
- 数据校验：Pydantic v2 请求模型、响应模型、字段校验、computed field
- 数据库：SQLAlchemy 2.0 async ORM + SQLite 教学默认配置
- 缓存：Redis cache-aside、TTL、缓存失效、单飞锁防击穿
- 异步能力：`asyncio.gather` 并发聚合、线程池隔离阻塞任务
- WebSocket：文章评论房间、广播、心跳消息
- 工程化：中间件、统一异常、版本化 API、测试 fixture、Docker 多阶段构建
- 教学资料：`docs/lessons` 中有 20 篇配套章节

## 技术栈

| 分类 | 技术 |
| --- | --- |
| Web 框架 | FastAPI, Starlette, Uvicorn |
| 数据模型 | Pydantic v2, pydantic-settings |
| 数据库 | SQLAlchemy 2.0 async ORM, SQLite, aiosqlite |
| 认证安全 | python-jose, passlib, bcrypt, OAuth2 Bearer Token |
| 文件与表单 | python-multipart, UploadFile, Form, Header, Cookie |
| 缓存 | redis-py asyncio, fakeredis |
| 异步任务 | BackgroundTasks, APScheduler |
| 测试 | pytest, httpx, pytest-asyncio, pytest-cov |
| 代码质量 | Ruff |
| 部署 | Docker, Docker Compose, Gunicorn, UvicornWorker |

## 学习路线

```text
入门基础   task 1-4   应用骨架 / 路径参数 / 查询参数 / 请求体 / 文件上传
核心进阶   task 5-8   响应模型 / 依赖注入 / Pydantic 校验 / 异步并发
工程化     task 9-12  中间件 / 统一异常 / 数据库 / JWT 认证
高级特性   task 13-16 后台任务 / WebSocket / OpenAPI / 测试体系
项目实战   task 17-20 项目结构 / Redis 缓存 / Docker 部署 / 综合 e2e
```

配套文档在 `docs/lessons/`，任务计划在 `docs/plans/`，进度数据在 `progress.json`。

## 目录结构

```text
FastAPI/
├── app/
│   ├── api/              # auth / admin / versioned / websocket 路由
│   ├── core/             # 配置、安全、依赖、中间件、异常、WS manager
│   ├── crud/             # 数据访问层
│   ├── db/               # SQLAlchemy async engine/session/Base/init_db
│   ├── models/           # ORM 模型：Author / Post
│   ├── schemas/          # Pydantic 请求与响应模型
│   ├── services/         # 缓存、邮件、统计、上传、调度等服务
│   ├── data.py           # 教学用内存数据
│   └── main.py           # FastAPI app 入口与路由装配
├── docs/
│   ├── lessons/          # 20 篇教学文档
│   └── plans/            # 每个 task 的实现计划
├── tests/                # pytest 测试套件
├── Dockerfile            # 多阶段镜像构建
├── docker-compose.yml    # postgres + redis + blog 编排示例
├── pyproject.toml        # 项目依赖与工具配置
├── verify-deploy.sh      # Docker 部署自检脚本
└── README.md
```

## 环境要求

- Python 3.10+
- pip 23+
- Docker 24+，仅容器化运行或部署自检时需要
- 可选：Redis 7，本地测试缓存真实服务时需要；没有 Redis 时缓存层会降级

下文统一使用 `python` 命令。如果你的系统只有 `python3`，把命令里的 `python` 替换成 `python3` 即可。

## 快速开始

### 1. 创建虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### 2. 安装依赖

推荐安装开发与缓存相关依赖，这样可以直接运行完整测试：

```bash
pip install -e ".[dev,cache]"
```

如果只想启动基础 API：

```bash
pip install -e .
```

依赖组合说明：

| 命令 | 适用场景 |
| --- | --- |
| `pip install -e .` | 基础运行，适合学习入门接口 |
| `pip install -e ".[dev]"` | 增加 pytest、httpx、ruff 等开发工具 |
| `pip install -e ".[db]"` | 增加 asyncpg，用于 PostgreSQL 异步连接 |
| `pip install -e ".[cache]"` | 增加 redis、fakeredis，用于缓存章节 |
| `pip install -e ".[deploy]"` | 增加 gunicorn、asyncpg、redis，用于生产式运行 |
| `pip install -e ".[dev,cache]"` | 推荐组合，可以跑绝大多数本地测试 |

注意：`/db/posts` 的缓存路径会在运行时导入 `redis` 包；如果要完整体验数据库版列表缓存，请安装 `.[cache]`。

### 3. 初始化数据库表

本项目默认使用本地 SQLite 文件 `blog.db`。首次调用 `/auth/*` 或 `/db/posts` 前，需要创建表结构：

```bash
python - <<'PY'
import asyncio
from app.db import init_db

asyncio.run(init_db())
PY
```

执行后会在项目根目录生成或更新 `blog.db`。

### 4. 可选：启动本地 Redis

缓存章节可以在没有 Redis 服务时降级到 DB。如果想体验真实 Redis 缓存，可以用 Docker 启一个本地 Redis：

```bash
docker run -d --rm --name blog-redis -p 6379:6379 redis:7-alpine
```

停止本地 Redis：

```bash
docker stop blog-redis
```

### 5. 启动开发服务

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动后访问：

- API 文档：http://127.0.0.1:8000/docs
- ReDoc 文档：http://127.0.0.1:8000/redoc
- 健康检查：http://127.0.0.1:8000/health

## 常用命令

```bash
# 运行全部测试
pytest

# 失败即停，适合调试
pytest -x

# 跑综合 e2e
pytest tests/test_20_blog_e2e.py -q

# 覆盖率
pytest --cov=app

# 代码检查
ruff check .

# 自动格式化
ruff format .

# 本地模拟生产服务，需要额外安装 gunicorn
gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 4 --bind 0.0.0.0:8000

# 查看课程完成进度
python check_progress.py
```

本地直接运行 `gunicorn` 前需要先安装：

```bash
pip install gunicorn
```

Docker 镜像中已经在构建阶段安装了 `gunicorn`。

## 接口速查

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/` | 应用基本信息 |
| `GET` | `/health` | 健康检查 |
| `GET` | `/posts` | 内存版文章列表，支持分页和过滤 |
| `POST` | `/posts` | 创建内存版文章 |
| `GET` | `/posts/{post_id}` | 查询内存版文章详情 |
| `GET` | `/posts/{post_id}/brief` | 演示 `response_model_include` |
| `GET` | `/posts/{post_id}/full` | 演示 `response_model_exclude` |
| `GET` | `/posts/old` | 已废弃接口，演示 OpenAPI deprecated |
| `DELETE` | `/posts/{post_id}` | 删除内存版文章，演示依赖注入鉴权 |
| `GET` | `/users/{username}` | 查询教学内存用户 |
| `POST` | `/authors/preview` | 预览作者校验结果 |
| `POST` | `/posts/{post_id}/cover` | 单文件上传 |
| `POST` | `/posts/{post_id}/covers` | 多文件上传 |
| `POST` | `/auth/register` | 注册作者，需要先初始化 DB |
| `POST` | `/auth/token` | 登录并签发 JWT，表单提交 |
| `GET` | `/me` | 读取当前 JWT 用户 |
| `POST` | `/db/posts` | 数据库版文章创建 |
| `GET` | `/db/posts` | 数据库版文章列表，带 Redis 缓存示例 |
| `GET` | `/db/posts/{post_id}` | 数据库版文章详情 |
| `PUT` | `/db/posts/{post_id}` | 数据库版文章更新 |
| `DELETE` | `/db/posts/{post_id}` | 数据库版文章删除 |
| `DELETE` | `/admin/posts/{post_id}` | admin scope 删除文章 |
| `GET` | `/stats/aggregate/{post_id}` | 异步并发聚合统计 |
| `GET` | `/stats/aggregate-sync/{post_id}` | 同步串行统计，对比 async 性能 |
| `GET` | `/stats/async-dep` | 演示 async dependency |
| `POST` | `/stats/trigger-background` | 演示 BackgroundTasks |
| `GET` | `/stats/blocking-via-executor` | 演示阻塞任务放入线程池 |
| `GET` | `/stats/with-ctx` | 演示 async generator 依赖清理 |
| `GET` | `/api/v1/posts` | v1 版本文章列表 |
| `GET` | `/api/v2/posts` | v2 版本文章列表 |
| `WS` | `/ws/posts/{post_id}/comments` | WebSocket 评论房间 |

## 请求示例

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

创建内存版文章：

```bash
curl -X POST http://127.0.0.1:8000/posts \
  -H "Content-Type: application/json" \
  -d '{"title":"FastAPI 入门","content":"Hello FastAPI","tags":["Python","fastapi"]}'
```

注册作者：

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","email":"alice@example.com","password":"pass1234"}'
```

登录获取 token：

```bash
curl -X POST http://127.0.0.1:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice&password=pass1234"
```

创建数据库版文章：

```bash
curl -X POST http://127.0.0.1:8000/db/posts \
  -H "Content-Type: application/json" \
  -d '{"title":"DB Post","content":"Persisted by SQLAlchemy","tags":["FastAPI","DB"]}'
```

上传封面文件：

```bash
curl -X POST http://127.0.0.1:8000/posts/1/cover \
  -H "X-Upload-Token: valid-token" \
  -F "alt_text=A cover image" \
  -F "file=@./cover.png;type=image/png"
```

在浏览器控制台测试 WebSocket：

```javascript
const ws = new WebSocket("ws://127.0.0.1:8000/ws/posts/1/comments");
ws.onmessage = (event) => console.log("message:", event.data);
ws.onopen = () => {
  ws.send(JSON.stringify({ type: "comment", author: "alice", text: "hello websocket" }));
};
```

生成 admin token 并调用管理员删除接口：

```bash
ADMIN_TOKEN=$(python - <<'PY'
from app.core.config import settings
from app.core.security import create_access_token

print(create_access_token(
    subject="admin-1",
    secret=settings.SECRET_KEY.get_secret_value(),
    extra={"scope": "admin"},
))
PY
)

curl -X DELETE http://127.0.0.1:8000/admin/posts/1 \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

## Docker 运行

构建并启动完整编排：

```bash
docker compose up --build
```

后台启动：

```bash
docker compose up -d --build
docker compose logs -f blog
```

停止并移除容器：

```bash
docker compose down
```

部署自检：

```bash
chmod +x verify-deploy.sh
./verify-deploy.sh
```

Dockerfile 使用多阶段构建：builder 阶段安装依赖，runtime 阶段只保留运行所需文件。容器内使用 `gunicorn + uvicorn.workers.UvicornWorker`，默认 4 个 worker，并通过 `/health` 做 HEALTHCHECK。

当前 `docker-compose.yml` 同时启动 PostgreSQL、Redis 和 blog 服务，用于演示完整部署编排。Compose 会注入 `DATABASE_URL=postgresql+asyncpg://...`、`REDIS_URL=redis://redis:6379/0`，并通过 `INIT_DB_ON_STARTUP=true` 让容器启动命令先执行 `python -m app.db.init_startup`，在教学部署场景下自动创建表结构，然后再启动 Gunicorn。

## 配置说明

配置模型位于 `app/core/config.py`，支持从环境变量和 `.env` 读取：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite+aiosqlite:///./blog.db` | 应用数据库连接 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 缓存连接 |
| `SECRET_KEY` | `dev-only-not-for-production` | JWT 签名密钥 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | token 过期时间 |
| `ALGORITHM` | `HS256` | JWT 算法 |
| `DEBUG` | `false` | 调试开关 |
| `INIT_DB_ON_STARTUP` | `false` | 启动时是否自动创建数据库表 |

本地默认使用 SQLite，Docker Compose 使用 PostgreSQL。`INIT_DB_ON_STARTUP=true` 适合教学部署和 demo 环境；生产环境建议关闭它，并使用 Alembic 做数据库迁移。手动触发同一套初始化逻辑可以运行：

```bash
python -m app.db.init_startup
```

`.env` 示例：

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./blog.db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=replace-me-in-local-dev
ACCESS_TOKEN_EXPIRE_MINUTES=60
DEBUG=true
INIT_DB_ON_STARTUP=false
```

不要把 `.env` 提交到仓库或打进镜像，`.dockerignore` 已经默认排除了它。

## 测试策略

测试集中在 `tests/`，每个 task 都有对应测试文件。数据库相关测试使用 in-memory SQLite 和 FastAPI dependency override，避免污染本地 `blog.db`。缓存相关测试使用 fakeredis，验证协议行为但不依赖真实 Redis 服务。

重点测试：

- `tests/test_11_database.py`：SQLAlchemy async CRUD
- `tests/test_12_auth.py`：注册、登录、JWT
- `tests/test_14_websocket.py`：WebSocket 评论广播
- `tests/test_18_cache.py`：Redis 缓存、TTL、单飞锁
- `tests/test_19_deploy.py`：Docker 构建与容器健康检查
- `tests/test_20_blog_e2e.py`：完整用户旅程

`test_19_deploy.py` 会真实调用 Docker，运行时间更长，并要求本机 Docker daemon 可用。

## 核心知识点

### FastAPI 分层

- `app/main.py` 负责 app 创建、路由装配、中间件和异常处理器注册
- `app/api/*` 负责 HTTP 和 WebSocket 协议层
- `app/schemas/*` 负责输入输出模型和数据校验
- `app/crud/*` 负责数据库访问
- `app/services/*` 负责缓存、统计、邮件、上传、调度等业务服务
- `app/core/*` 负责配置、安全、依赖、中间件、异常等基础能力

### 数据校验

项目使用 Pydantic v2 演示：

- `Field(min_length=..., max_length=...)`
- `field_validator`
- `model_validator`
- `computed_field`
- `validation_alias`
- `response_model` 输出过滤

### 依赖注入

项目通过 `Depends` 演示：

- 普通依赖：模拟 DB session 和当前用户
- yield 依赖：请求结束后自动提交或回滚
- async 依赖：异步资源获取
- 认证依赖：JWT Bearer token 解析
- 权限依赖：admin scope 校验

### 缓存设计

`app/services/cache.py` 使用 cache-aside 模式：

1. 查询缓存，命中直接返回
2. 未命中则查询 DB
3. 回填缓存并设置 TTL
4. 写入或删除数据后按 pattern 主动失效
5. Redis 不可用时吞掉缓存异常，降级到 DB

### 部署设计

容器化部分覆盖：

- 多阶段构建降低镜像体积
- Gunicorn master-worker 模型
- UvicornWorker 支持 ASGI
- HEALTHCHECK 探测 `/health`
- Docker Compose 编排 PostgreSQL、Redis、应用服务
- SIGTERM graceful shutdown 自检

## 当前边界与改造建议

这个仓库的目标是教学和渐进式实战，因此保留了一些有意简化的地方：

| 当前实现 | 适合学习的点 | 生产改造建议 |
| --- | --- | --- |
| 没有 Alembic | 降低数据库章节门槛 | 增加迁移脚本和版本管理 |
| admin token 通过 scope 演示 | 聚焦权限依赖写法 | 接入真实用户角色、RBAC 或策略引擎 |
| WebSocket 房间存在进程内存中 | 容易理解连接管理 | 多 worker 或多实例时改为 Redis Pub/Sub |
| `/health` 只做应用存活检查 | Docker HEALTHCHECK 简洁 | 增加 readiness，检查 DB/Redis 连通性 |
| 默认 SECRET_KEY 适合开发 | 开箱即跑 | 生产必须用环境变量注入强随机密钥 |

## 常见问题

### `sqlite3.OperationalError: no such table`

说明数据库表还没有创建。先执行：

```bash
python - <<'PY'
import asyncio
from app.db import init_db

asyncio.run(init_db())
PY
```

### `ModuleNotFoundError: No module named 'redis'`

说明只安装了基础依赖。补装缓存 extra：

```bash
pip install -e ".[cache]"
```

或直接安装完整开发依赖：

```bash
pip install -e ".[dev,cache]"
```

### 端口 8000 被占用

换一个端口启动：

```bash
uvicorn app.main:app --reload --port 8001
```

### Docker 测试失败

确认 Docker daemon 正在运行：

```bash
docker version
docker compose config --quiet
```

如果只想跑普通单元测试，可以先跳过部署测试：

```bash
pytest --ignore=tests/test_19_deploy.py
```

## 学习建议

1. 先跑通 `uvicorn app.main:app --reload`
2. 打开 `/docs` 逐个试接口
3. 按顺序阅读 `docs/lessons/01-hello.md` 到 `docs/lessons/20-blog-final.md`
4. 每读完一章，运行对应测试文件
5. 最后运行 `pytest tests/test_20_blog_e2e.py -q` 串联全部知识点

## 进度查看

```bash
python check_progress.py
```

完整任务清单见 `progress.json`。
