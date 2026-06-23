# task-19 · Docker 化部署与 Gunicorn 多 worker

> 把博客从"本地能跑"带到"生产可部署"：容器化、编排、多进程、健康检查、优雅退出。

## 【新手】为什么要容器化

`uvicorn app.main:app --reload` 是开发模式，生产用它有三个问题：

1. **环境不一致**："本地能跑"≠"服务器能跑"。Python 版本、系统库、依赖版本任何差异都会出 bug。
2. **单进程**：uvicorn 单 worker 无法利用多核 CPU，吞吐天花板低。
3. **没有进程守护**：崩了就崩了，没人重启。

Docker 把"代码 + 依赖 + 系统"打包成不可变镜像，**build once, run anywhere**。Gunicorn 在容器内 fork 多个 worker，单容器多进程并行处理请求。

## 【新手】Dockerfile 多阶段构建

```dockerfile
# ---------- 构建阶段：装依赖 ----------
FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
RUN pip install --no-cache-dir --target=/install \
    "fastapi>=0.115" "uvicorn[standard]>=0.30" ...

# ---------- 运行阶段：拷贝产物 ----------
FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /install /usr/local/lib/python3.12/site-packages
COPY app ./app
CMD ["gunicorn", ...]
```

**为什么多阶段？**

- builder 阶段装的 pip 缓存、setuptools、wheel 不会进最终镜像
- runtime 只需要已编译好的 `.dist-info` + `.so` + `.py`，镜像更小
- 我们这里 73MB（python:3.12-slim 基础 ~50MB + 依赖 ~22MB + 源码 ~1MB）

### `pip install --target=/install` 的小坑

`--target` 会把 console scripts（`gunicorn`、`dotenv`）放到 `/install/bin/`，不在 PATH 上。需要软链：

```dockerfile
RUN ln -sf /usr/local/lib/python3.12/site-packages/bin/* /usr/local/bin/
```

否则容器启动时报 `gunicorn: executable file not found in $PATH`。

## 【进阶】asyncpg / bcrypt / cryptography 的 wheel 套路

这三个包在 Linux 上有 **manylinux wheel**（PyPI 上预编译好的二进制）：

- `asyncpg`：自带 libpq，**不需要** apt-get install libpq5
- `bcrypt`：自带 Rust 编译产物
- `cryptography`：自带 OpenSSL 静态库

**结论**：`python:3.12-slim` 直接 `pip install` 就够，**不用** `apt-get install gcc libpq-dev`。少装一层编译工具，镜像瘦 100+MB。

## 【进阶】Gunicorn + UvicornWorker

```dockerfile
CMD ["gunicorn", "app.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--graceful-timeout", "20", \
     "--timeout", "60"]
```

| 参数 | 含义 |
|---|---|
| `-k uvicorn.workers.UvicornWorker` | 用 uvicorn 的 ASGI worker（支持 FastAPI 异步） |
| `--workers 4` | prefork 4 个子进程（推荐 CPU 核数 × 2+1） |
| `--graceful-timeout 20` | SIGTERM 后给 worker 20 秒处理完在途请求 |
| `--timeout 60` | worker 心跳超时（uvicorn 的 keep-alive 由 ASGI 管） |

启动后进程树：
```
gunicorn master (PID 1)        # 管理子进程，重启挂掉的 worker
├── gunicorn worker (PID 7)    # 真正处理 HTTP 请求
├── gunicorn worker (PID 8)
├── gunicorn worker (PID 9)
└── gunicorn worker (PID 10)
```

### 为什么不直接用 uvicorn --workers 4

也可以。但 gunicorn 更成熟：
- **Master-worker 模型**：worker 崩溃 master 自动重启
- **预热**：worker 在 import 阶段就把 app 加载好，第一个请求不会冷启动
- **graceful reload**：`kill -HUP master` 平滑重启所有 worker，0 停机发版

## 【进阶】HEALTHCHECK

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).status==200 else 1)"
```

- `start-period=10s`：容器刚启动时给 10 秒宽限，不算失败
- `interval=30s`：之后每 30 秒探一次
- `retries=3`：连续 3 次失败标 `unhealthy`

容器编排器（compose、k8s）会根据这个状态决定是否重启 / 切流量。

**为什么用 python 而不是 curl**：python:3.12-slim 没装 curl。`apt-get install curl` 会拉一堆依赖（libcurl、openssl），镜像多 30MB。Python stdlib 的 urllib 已经够用。

## 【进阶】docker-compose 编排

```yaml
services:
  postgres:
    image: postgres:16-alpine
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "blog"]
      ...
  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      ...
  blog:
    build: .
    depends_on:
      postgres:
        condition: service_healthy    # 等 postgres 健康再启动
      redis:
        condition: service_healthy
    environment:
      DATABASE_URL: "postgresql+asyncpg://blog:blog@postgres:5432/blog"
      REDIS_URL: "redis://redis:6379/0"
```

**关键点**：

1. `depends_on: condition: service_healthy`：不只是等容器启动，还要等它健康。否则 blog 先起，postgres 还没 ready 就连不上。
2. 服务间通过服务名互相访问：`postgres:5432`、`redis:6379`。docker compose 自动建 DNS。
3. healthcheck 必须配 —— 否则 `service_healthy` 永远不满足。

## 【进阶】优雅退出（graceful shutdown）

容器收到 SIGTERM 时：

1. Gunicorn master 不再 accept 新请求
2. 给每个 worker 发 SIGTERM
3. worker 处理完在途请求后退出（最多 `--graceful-timeout` 秒）
4. 超时未退出的 worker 被 SIGKILL

```
docker stop    # 默认先 SIGTERM，10s 后 SIGKILL
docker stop -t 30  # SIGTERM 后 30s 才 SIGKILL，给业务足够时间
```

k8s 的 `terminationGracePeriodSeconds` 同理。**SIGTERM 是容器化的"软关机"信号**，应用必须正确处理。

## 【进阶】.dockerignore

`COPY . .` 会把整个项目丢进 builder context。不忽略 `.venv/` `__pycache__/` 会导致：

- 构建变慢（context 上传耗时）
- 镜像变大（.venv 几百 MB）
- 本地缓存污染构建

```
.venv/
__pycache__/
.git/
.env
blog.db
```

特别注意 **`.env` 绝不能进镜像** —— 镜像一旦推送到 registry，密钥就泄露了。生产密钥用运行时 `-e SECRET_KEY=xxx` 或 docker secret 注入。

## 思考题

1. **`--workers 4` 一定是 4 吗？** 一个 8 核机器应该开几个 worker？提示：CPU 密集 vs I/O 密集的差异。
2. **HEALTHCHECK 和 k8s 的 livenessProbe / readinessProbe 有什么区别？** 提示：恢复 vs 不分发流量。
3. **如果想做 zero-downtime 发版（rolling update），需要满足哪三个条件？** 提示：SIGTERM 处理、healthcheck、replica 数。
4. **为什么 Dockerfile 把 `COPY pyproject.toml` 放在 `COPY app` 前面？** 提示：layer cache 命中率。
5. **容器内 `app.main:app` 与宿主机 `/health` 的关系？** 怎么从外面探到容器里的服务？提示：端口映射、bridge 网络。

## 本次改动

- 新增 `Dockerfile`：多阶段构建（builder pip install → runtime COPY）
- 新增 `.dockerignore`：排除 .venv / __pycache__ / .env / blog.db
- 新增 `docker-compose.yml`：postgres + redis + blog 三服务，healthcheck + depends_on
- 新增 `verify-deploy.sh`：8 项部署自检脚本
- 新增 `tests/test_19_deploy.py`：10 条测试（静态 + 真实 docker build/run/exec/stop）
- `pyproject.toml` 依赖加 `gunicorn>=21` + `uvicorn[standard]>=0.30`
