# task-19：多阶段构建（builder 装依赖到 /install，runtime 只 COPY）
# 不 apt-get 任何包 —— python:3.12-slim 已含 stdlib（urllib 可做 HEALTHCHECK）
# asyncpg/bcrypt/cryptography 都有预编译 manylinux wheel，无需 gcc

# ---------- 构建阶段：纯 pip install ----------
FROM python:3.12-slim AS builder

WORKDIR /build

# 先拷依赖清单（利用 layer cache）
COPY pyproject.toml ./

# 装到 /install 目录（不污染系统 site-packages，方便 runtime COPY）
RUN pip install --no-cache-dir --target=/install \
    "fastapi>=0.115" "uvicorn[standard]>=0.30" "gunicorn>=21" \
    "pydantic>=2.7" "pydantic-settings>=2.3" \
    "sqlalchemy>=2.0" "aiosqlite" "asyncpg" \
    "python-jose[cryptography]" "passlib[bcrypt]" "python-multipart" "bcrypt<4.2" \
    "apscheduler" "redis>=5.0" "httpx"


# ---------- 运行阶段 ----------
FROM python:3.12-slim AS runtime

WORKDIR /app

# 从 builder 拷贝依赖
COPY --from=builder /install /usr/local/lib/python3.12/site-packages
# pip --target 把可执行脚本放到了 site-packages/bin/，软链到 PATH 上
RUN ln -sf /usr/local/lib/python3.12/site-packages/bin/* /usr/local/bin/

# 拷贝项目源码
COPY app ./app
COPY docs ./docs
COPY tests ./tests
COPY pyproject.toml ./

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 8000

# HEALTHCHECK 走 /health，30s 一次；用 python urllib 避免装 curl
# 注意：HEALTHCHECK 不会响应 SIGTERM 优雅退出，仅做存活探测
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).status==200 else 1)"

# 可选预启动建表 + Gunicorn/UvicornWorker，4 个 worker 进程
# INIT_DB_ON_STARTUP=true 时，python -m app.db.init_startup 会先执行一次 Base.metadata.create_all。
# --graceful-timeout: SIGTERM 后给 worker 多少秒处理完在途请求
# --timeout: 单个 worker 心跳超时
CMD ["sh", "-c", "python -m app.db.init_startup && exec gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers 4 --bind 0.0.0.0:8000 --graceful-timeout 20 --timeout 60 --access-logfile - --error-logfile -"]
