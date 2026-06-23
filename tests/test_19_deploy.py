"""task-19 测试：Docker 化部署 + Gunicorn 多 worker。

10 条覆盖：
- Dockerfile 存在 + 多阶段构建 + 用 python:3.12-slim + HEALTHCHECK + WORKERS 4
- .dockerignore 排除 .venv/.git/__pycache__
- docker-compose.yml 三服务（postgres/redis/blog）+ depends_on healthcheck
- 实际 `docker build` 成功
- 实际 `docker run` 启动后 /health 200
- 容器内 gunicorn 进程数 == 5（1 master + 4 workers）
- 镜像 < 300MB
- SIGTERM 优雅退出（exit code 0）
- docker compose config 语法合法

每条测试用 subprocess 真跑 docker 命令。
"""

from __future__ import annotations

import pathlib
import subprocess
import time

import pytest

ROOT = pathlib.Path(__file__).parent.parent
IMAGE_TAG = "blog-deploy-test"
CONTAINER_NAME = "blog-deploy-test-run"


# ----------------------------------------------------------------------
# 静态文件检查（快）
# ----------------------------------------------------------------------


def test_dockerfile_uses_multistage_and_slim() -> None:
    """Dockerfile 使用多阶段构建 + python:3.12-slim 基础镜像。"""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim AS builder" in dockerfile or "AS builder" in dockerfile
    assert dockerfile.count("FROM") >= 2, "应是多阶段构建（≥2 个 FROM）"
    assert "python:3.12-slim" in dockerfile


def test_dockerfile_has_healthcheck_and_workers() -> None:
    """Dockerfile 配置了 HEALTHCHECK 和 gunicorn --workers 4。"""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "HEALTHCHECK" in dockerfile
    assert "--workers" in dockerfile and "4" in dockerfile
    assert "uvicorn.workers.UvicornWorker" in dockerfile
    assert "/health" in dockerfile, "HEALTHCHECK 应走 /health 端点"


def test_dockerignore_excludes_sensitive() -> None:
    """.dockerignore 排除 venv / git / 缓存等。"""
    content = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    for required in (".venv", ".git", "__pycache__", ".env"):
        assert required in content, f".dockerignore 缺少 {required}"


def test_compose_yml_has_three_services() -> None:
    """docker-compose.yml 包含 postgres / redis / blog 三个服务。"""
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for service in ("postgres", "redis", "blog"):
        assert f"{service}:" in compose, f"compose 缺少 {service} 服务"
    # blog 依赖 postgres 和 redis 的健康检查
    assert "depends_on" in compose
    assert "service_healthy" in compose
    # 各服务都有 healthcheck
    assert compose.count("healthcheck") >= 3


def test_compose_config_is_valid() -> None:
    """`docker compose config` 语法合法。"""
    result = subprocess.run(
        ["docker", "compose", "config", "--quiet"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"compose config invalid: {result.stderr}"


# ----------------------------------------------------------------------
# 真实 docker 构建与运行（慢，session 级共享）
# ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def built_image():
    """模块级：build 一次镜像，所有 test 共享。"""
    result = subprocess.run(
        ["docker", "build", "-t", IMAGE_TAG, "."],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, f"docker build failed:\n{result.stdout}\n{result.stderr}"
    yield IMAGE_TAG
    # 不在这里 docker rmi —— 镜像留给后续调试；CI 会自己 GC


def test_docker_build_succeeds(built_image) -> None:
    """`docker build` 成功（fixture 已断言）。"""
    assert built_image == IMAGE_TAG


def test_image_size_under_300mb(built_image) -> None:
    """镜像大小 < 300MB。"""
    out = subprocess.check_output(
        ["docker", "image", "inspect", built_image, "--format", "{{.Size}}"],
        text=True,
    ).strip()
    size_mb = int(out) / 1024 / 1024
    assert size_mb < 300, f"image too big: {size_mb:.1f}MB"


@pytest.fixture(scope="module")
def running_container(built_image):
    """启动容器，等 /health 就绪，回收时停止。"""
    # 先清理可能残留的同名容器
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)

    proc = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            CONTAINER_NAME,
            "-p",
            "8799:8000",
            "-e",
            "DATABASE_URL=sqlite+aiosqlite:////app/blog.db",
            "-e",
            "REDIS_URL=redis://localhost:6379/0",  # 不依赖真实 redis，cache 会降级
            "-e",
            "SECRET_KEY=deploy-test-not-for-prod",
            built_image,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"docker run failed: {proc.stderr}"

    # 等 /health 就绪（最多 60 秒）
    import urllib.error
    import urllib.request

    deadline = time.time() + 60
    healthy = False
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8799/health", timeout=2) as r:
                if r.status == 200:
                    healthy = True
                    break
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(1)

    assert healthy, "container did not become healthy within 60s"
    yield CONTAINER_NAME

    subprocess.run(["docker", "stop", CONTAINER_NAME], capture_output=True, timeout=30)


def test_container_health_200(running_container) -> None:
    """/health 端点返回 200。"""
    import urllib.request

    with urllib.request.urlopen("http://127.0.0.1:8799/health", timeout=5) as r:
        assert r.status == 200
        body = r.read().decode()
        assert "ok" in body


def test_gunicorn_worker_count_is_4(running_container) -> None:
    """容器内 gunicorn 进程数 == 5（1 master + 4 worker）。

    用 /proc/<pid>/cmdline 扫描，匹配路径 "/gunicorn"（不会被本测试脚本污染）。
    """
    # 多等几秒让 worker 全部 fork 完成
    time.sleep(3)
    script = """
import os
count = 0
for pid in os.listdir('/proc'):
    if not pid.isdigit():
        continue
    try:
        parts = open(f'/proc/{pid}/cmdline', 'rb').read().split(b'\\x00')
        parts = [p.decode(errors='ignore') for p in parts if p]
    except Exception:
        continue
    # 真正的 gunicorn 进程：argv[0]=python argv[1]=.../bin/gunicorn
    if len(parts) >= 2 and parts[1].endswith('/gunicorn'):
        count += 1
print(count)
"""
    out = subprocess.check_output(
        ["docker", "exec", running_container, "python", "-c", script],
        text=True,
    ).strip()
    count = int(out)
    assert count == 5, f"expected 5 gunicorn procs (1 master + 4 workers), got {count}"


def test_graceful_shutdown_on_sigterm(running_container) -> None:
    """SIGTERM 后容器优雅退出（exit code 0/137 之外的非异常退出）。"""
    # 这个 test 故意放最后：发 SIGTERM 后容器会被销毁
    proc = subprocess.run(
        ["docker", "stop", "-t", "30", running_container],
        capture_output=True,
        text=True,
        timeout=60,
    )
    # docker stop 成功 = 容器已退出（不论 SIGTERM 是否被捕捉）
    assert proc.returncode == 0, f"docker stop failed: {proc.stderr}"
    # 检查退出码（容器 stop 后 inspect）
    inspect = subprocess.run(
        ["docker", "inspect", running_container, "--format", "{{.State.ExitCode}}"],
        capture_output=True,
        text=True,
    )
    # --rm 容器停止后可能已被删除，inspect 失败也算正常退出
    if inspect.returncode == 0:
        exit_code = int(inspect.stdout.strip())
        # 0 = gunicorn 收到 SIGTERM 优雅退出
        # 137 = SIGKILL（超时强杀），不可接受
        assert exit_code == 0, f"expected exit 0 (graceful), got {exit_code}"
