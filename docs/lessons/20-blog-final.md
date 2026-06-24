# task-20 · 综合实战：博客系统端到端

> 前 19 个知识点的"毕业考"：把骨架、参数、Pydantic、依赖注入、异步、中间件、异常、数据库、JWT、后台任务、WebSocket、文档、测试、结构、缓存、容器化全部串成一个完整博客 API，并新增 **scope-based 授权**作为收官特性。

## 【新手】这一章在做什么

task-1 ~ task-19 每个 task 引入"一个"知识点，代码是渐进式叠加的。task-20 不引入全新大模块，而是：

1. **串起来**：用一组 e2e 测试覆盖完整用户旅程（注册 → 登录 → 发文章 → WS 评论 → 缓存命中 → 统计 → admin 删除），确保 19 个知识点协同工作不回归。
2. **补一刀**：在 task-12 的"resource ownership"之上，加一层"global capability"——`scope=admin` 才能调用 `DELETE /admin/posts/{id}`。

完成后，本仓库就是一个**可运行、可测试、可部署**的迷你博客后端样本。

## 【进阶】架构总览

```
                    ┌─────────────────────────────────────────┐
                    │              app/main.py                │
                    │  FastAPI app + 路由聚合 + 中间件注册    │
                    └────────────────┬────────────────────────┘
                                     │ include_router
       ┌──────────────┬──────────────┼──────────────┬──────────────┬─────────────┐
       ▼              ▼              ▼              ▼              ▼             ▼
  api/auth.py  api/ws_comments.py  api/versioned  api/admin.py  /posts/*     /db/posts/*
  register     WS 房间广播         v1+v2 双版本   scope 校验    内存版       DB+缓存版
  token        /ws/posts/{id}                     DELETE         (task 1~7)   (task 11/18)
  /me                                             /admin/posts/
                                                  {id}
                                     │
       ┌───────────────────────────┴───────────────────────────┐
       ▼                ▼                  ▼                    ▼
   core/config     core/security      core/deps             core/exceptions
   pydantic-       bcrypt + JWT       get_db /              PostNotFound /
   settings        create/decode      get_current_author    BizError 统一结构
                                     (task-6/12)           (task-10)
                                     │
       ┌───────────────────────────┴───────────────────────────┐
       ▼                ▼                  ▼                    ▼
   models/          schemas/           crud/                services/
   Author / Post    PostCreate /       create/list/get/    cache (Redis)
   SQLAlchemy 2.0   PostOut /          delete              email (BackgroundTask)
   DeclarativeBase  AuthorOut                              hot_posts (APScheduler)
                                                          stats (asyncio.gather)
                                                          upload (UploadFile)
                                                          ws_manager (房间模型)
```

### 模块依赖关系（一句话版）

- `main.py` 是**装配层**：import 各 router、注册中间件、注册异常处理器，本身不放业务逻辑
- `api/*` 是**传输层**：HTTP/WS 协议、请求/响应模型绑定、调用 services/crud
- `crud/*` 是**数据访问层**：纯 SQLAlchemy 操作，不感知 HTTP
- `services/*` 是**领域服务层**：缓存、邮件、统计、调度等副作用或聚合
- `core/*` 是**基础设施层**：配置、安全、依赖、异常——被所有人共享

依赖方向永远"向内"：`api → crud → models`，外层不能反向 import 内层。

## 【进阶】task-20 新增：scope-based 授权

task-12 实现的是 **ownership 校验**："你能删这篇文章吗？因为你是这篇文章的作者"。

task-20 加的是 **capability 校验**："你能删任意文章吗？因为你是管理员"。

### JWT 的 scope 字段

OAuth2 / RFC 6749 把 `scope` 定义为"持有人能做什么的声明"。我们用 `extra={"scope": "admin"}` 把 scope 塞进 JWT payload：

```python
# app/core/security.py
def create_access_token(subject, expires_minutes=60, secret="", extra=None):
    payload = {"sub": subject, "iat": ..., "exp": ...}
    if extra:
        payload.update(extra)   # ← 这里把 scope 注进去
    return jwt.encode(payload, secret, algorithm=ALGORITHM)
```

### require_admin 依赖

```python
# app/api/admin.py
async def require_admin(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token, settings.SECRET_KEY.get_secret_value())

    raw_scope = payload.get("scope", "")
    scopes = raw_scope.split() if isinstance(raw_scope, str) else list(raw_scope)
    if "admin" not in scopes:
        raise HTTPException(403, "Admin scope required")
    return payload
```

注意 `scope` 字段支持两种格式：
- **字符串**（OAuth2 标准）："admin read write" — 用空格分隔
- **列表**：`["admin", "read"]`

这是为了兼容不同 IdP（Identity Provider）的 JWT 风格——Auth0 默认用字符串，Cognito / AzureAD 常用数组。

### 401 vs 403 的边界

| 场景 | 状态码 | 含义 |
|------|--------|------|
| 没带 Authorization 头 | 401 | "你是谁？" — 身份未知 |
| token 过期 / 伪造 | 401 | "你是谁？" — 身份无效 |
| 合法用户但 scope=user | 403 | "我知道你是谁，但你不能干这个" |
| 合法用户 scope=admin | 204 | 放行 |

记住一句话：**401 是"不认识你"，403 是"认识你但不让你做"**。

## 【进阶】e2e 测试的隔离策略

task-20 的 `e2e_client` fixture 把三层状态都重置成"干净世界"：

```python
@pytest.fixture()
def e2e_client(monkeypatch):
    # 1. 缓存：fakeredis 替换 + 单例重置 + 单飞锁清空
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache_mod, "get_cache", lambda: fake)
    monkeypatch.setattr(cache_mod, "_client", None)
    cache_mod._single_flight_locks.clear()

    # 2. 数据库：每测试独立 in-memory sqlite
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # ... create_all + dependency_overrides[get_async_db] = 内存 session

    # 3. TestClient with dependency_overrides
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

为什么每个测试都要重置？
- **缓存**：模块级 `_client` 单例会让上一个测试的 Redis 数据残留到下一个测试
- **单飞锁**：`asyncio.Lock` 跨事件循环复用可能行为异常，必须清空
- **数据库**：sqlite `:memory:` 引擎生命周期与 fixture 绑定，每个测试独立

如果不重置，你会看到"单独跑这个测试能过，整个 suite 跑就挂"的经典 fixture 污染问题。

## 【进阶】反假实现审查（task-20 代码的真实性）

`/goal` 流程禁止 stub / placeholder / mock-only 假实现。task-20 的所有代码路径都**真打实**：

| 端点 | 真实路径 |
|------|---------|
| `POST /auth/register` | 真的 bcrypt 哈希密码写进 sqlite |
| `POST /auth/token` | 真的 verify_password + 签 JWT |
| `POST /db/posts` | 真的 INSERT + 失效缓存（fakeredis SCAN） |
| `GET /db/posts` | 真的 cache-aside + 单飞 + 降级 |
| `WS /ws/posts/{id}/comments` | 真的进 manager 房间 + 广播 |
| `DELETE /admin/posts/{id}` | 真的 decode JWT + scope 校验 + DELETE SQL |

mock 的只有两类：
- `fakeredis`：Redis 协议的内存实现（不是 mock，是 fake — 实现了真实协议）
- `monkeypatch crud_list_posts`：观察 DB 调用次数（不改业务行为，只包一层计数器）

这是 **观察**而非 **替代**，不违反"不许 stub"的规则。

## 【进阶】生产化 checklist（性能 / 安全 / 可观测）

### 性能

- [x] **异步 IO 全链路**：所有 DB / Redis / 外部服务调用都是 async（`AsyncSession`、`aioredis`、`asyncio.gather`）
- [x] **缓存层**：列表查询走 cache-aside + 单飞 + 空值缓存，避免击穿/穿透
- [x] **后台任务非阻塞**：邮件发送用 `BackgroundTasks` 不阻塞 HTTP 响应
- [x] **阻塞任务隔离**：CPU 密集任务用 `loop.run_in_executor` 不卡事件循环
- [x] **多 worker**：Gunicorn `-k uvicorn.workers.UvicornWorker --workers 4`

### 安全

- [x] **密码哈希**：passlib bcrypt（不是明文 / MD5 / SHA1）
- [x] **JWT 签名**：HS256 + SECRET_KEY（生产从环境变量注入，不在代码里）
- [x] **scope 校验**：`require_admin` 默认拒绝；越权返回 403 而不是 404（避免信息泄漏）
- [x] **Pydantic 校验入参**：所有 body / query / path 都走模型校验，不让原始 `dict` 进业务
- [x] **响应模型过滤敏感字段**：`response_model=PostOut` 自动剥掉 `is_deleted` / `hashed_password`
- [x] **CORS 白名单**：只放行博客前端域名，不是 `*`
- [ ] **HTTPS**：生产必须 termination at LB / nginx（本仓库没实现，留给运维层）
- [ ] **限流**：未实现，建议加 `slowapi` 或 nginx `limit_req`

### 可观测性

- [x] **结构化日志**：`logging` + `extra=` 字段（生产再接 structlog / loguru）
- [x] **请求 ID**：`X-Request-ID` 中间件每请求生成 UUID，绑到 `request.state`
- [x] **耗时埋点**：`X-Response-Time` 中间件
- [x] **健康检查**：`/health` 端点（Docker HEALTHCHECK 用）
- [x] **统一错误结构**：`{"error": {"code", "message"}}` 适配前端错误处理
- [ ] **指标导出**：未实现，建议加 `prometheus-fastapi-instrumentator`
- [ ] **分布式追踪**：未实现，建议加 OpenTelemetry

## 【新手】思考题

1. **为什么 `require_admin` 用 `Header()` 而不是 `Depends(oauth2_scheme)`？**
   提示：看 task-12 的 `get_current_jwt_author`，那个依赖还会去 DB 查 author 实体；而 admin 删除只需要 scope 校验，不需要 author 实体。两个依赖关注点不同。

2. **如果要让普通用户也能删自己的文章，admin 能删所有人的文章，路由应该怎么设计？**
   提示：两个端点（`DELETE /posts/{id}` 用 ownership 校验、`DELETE /admin/posts/{id}` 用 scope 校验），而不是在一个端点里写复杂分支。

3. **e2e 测试为什么不用 `httpx.AsyncClient` 全程走异步？**
   提示：TestClient 是 sync 接口，对 WebSocket 支持更好；当测试需要观察并发（如 task-18 单飞）时再切 AsyncClient。fixture 可以同时提供两者。

4. **删除后为什么要 `cache_invalidate_pattern("post:list:*")`？**
   提示：cache-aside 的写入失效模式——不主动更新缓存，而是让下次读触发回源。否则用户会看到"已删除的文章还在列表里"直到 TTL 过期。

## 【进阶】下一步可以做什么

本仓库止于"可运行的迷你博客后端"。继续深化的话：

- **迁移到 Postgres**：改 `DATABASE_URL` + 加 asyncpg；测试仍用 sqlite `:memory:`
- **加全文搜索**：Postgres `tsvector` 或 Meilisearch；列表接口加 `?q=keyword`
- **加 refresh token**：access token 短 TTL（15min）+ refresh token 长 TTL（7d），降低泄露风险
- **加 RBAC**：scope 升级为 role，用 Casbin 做策略；`require_admin` → `require_role("editor")`
- **加 GraphQL**：`strawberry-graphql` 暴露 `/graphql`，和 REST 共存
- **加 OpenTelemetry**：自动 trace FastAPI + SQLAlchemy + Redis，接到 Jaeger

每一项都是另一章节的体量——task-20 是起点不是终点。
