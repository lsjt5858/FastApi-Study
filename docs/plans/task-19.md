# task-19: Docker 化部署与 Gunicorn + Uvicorn

## 目标
为博客项目提供生产部署：多阶段 Dockerfile + docker-compose（pg + redis + blog）+ Gunicorn 多 worker + HEALTHCHECK + graceful shutdown。

## 涉及文件
- `Dockerfile`（多阶段构建）
- `docker-compose.yml`（pg/redis/blog）
- `gunicorn_conf.py`（worker 配置）
- `.dockerignore`
- `verify-deploy.sh`（部署校验脚本）
- `app/main.py`（加 /health 路由 + lifespan 暴露 redis/pg）
- `docs/lessons/19-deploy.md`
- `tests/test_19_deploy.py`（用 subprocess 跑 verify-deploy.sh）

## 验收标准
- [ ] Dockerfile 多阶段（builder + runtime），最终镜像 < 300MB
- [ ] docker-compose.yml 含 postgres、redis、blog 三个服务
- [ ] blog 用 gunicorn -k uvicorn.workers.UvicornWorker --workers 4
- [ ] /health 路由检查 pg+redis 连通
- [ ] HEALTHCHECK 指向 /health
- [ ] SIGTERM 触发 graceful shutdown
- [ ] .dockerignore 排除 .venv/.git/__pycache__
- [ ] 8 项 verify-deploy.sh 验证

## 测试点（至少 8 条，由 verify-deploy.sh 检查）
1. `docker build` 构建镜像成功
2. `docker compose up -d` 启动所有容器
3. curl /health 返回 200
4. postgres 连接成功（psql 或 ping）
5. redis 连接成功（redis-cli ping → PONG）
6. gunicorn worker 数量 = 4（ps -ef | grep worker）
7. SIGTERM 后容器在 10s 内优雅退出
8. docker images 显示镜像大小 < 300MB

## 实现要点
```dockerfile
# Dockerfile（多阶段）
FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
RUN pip install --user --no-cache-dir -e ".[standard]"
COPY app ./app

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY --from=builder /build/app /app/app
ENV PATH=/root/.local/bin:$PATH
HEALTHCHECK --interval=30s --timeout=3s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
EXPOSE 8000
CMD ["gunicorn", "app.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--graceful-timeout", "10"]
```

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: blog
      POSTGRES_PASSWORD: blog
    ports: ["5432:5432"]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
  blog:
    build: .
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:blog@postgres:5432/blog
      REDIS_URL: redis://redis:6379/0
    ports: ["8000:8000"]
    depends_on: [postgres, redis]
```

- gunicorn 的 `--graceful-timeout` 与 FastAPI lifespan shutdown 配合实现优雅退出
- 多阶段构建把 builder 层的 pip install --user 复制到 runtime，省去 build 工具

## 教学文档大纲
1. 【新手】为什么不能直接 `uvicorn` 生产部署
2. 【新手】Docker 基础概念
3. 【新手】Dockerfile 多阶段构建
4. 【进阶】Gunicorn + UvicornWorker
5. 【进阶】docker-compose 与依赖服务
6. 【进阶】HEALTHCHECK 与 readiness/liveness
7. 【进阶】graceful shutdown 与信号处理
8. 思考题：worker 数应该设多少（2*CPU+1 的来历）？
