"""task-16 测试：测试夹具与 dependency_overrides 体系。

8 条测试覆盖：
- conftest.py 提供 client / db_client / mock_email / async_client 等 fixture
- dependency_overrides 替换 get_async_db
- parametrize 参数化分页
- mock 外部邮件
- tmp_path 持久化
- httpx AsyncClient 测异步
- 每用例独立内存库
- pytest-cov 报告生成
"""

from __future__ import annotations

import asyncio

import pytest

from app.db import get_async_db
from app.main import app
from app.services.email import EmailLog


def test_client_fixture_reusable(client) -> None:
    """client fixture 可被多测试复用（基础测试）。"""
    r = client.get("/health")
    assert r.status_code == 200


def test_db_overridden(client) -> None:
    """client fixture 已用 dependency_overrides 替换 get_async_db。"""
    assert get_async_db in app.dependency_overrides
    # 实际访问 DB 路由不报错
    r = client.get("/db/posts")
    assert r.status_code == 200


def test_each_test_isolated_db(db_factory) -> None:
    """db_factory 工厂：每次调用返回独立内存 engine。"""
    engine_a = db_factory()
    engine_b = db_factory()
    # 两个 engine 互不相同（独立 in-memory sqlite）
    assert engine_a is not engine_b


@pytest.mark.parametrize(
    "limit,offset,expected_count",
    [
        (1, 0, 1),
        (5, 0, 5),
        (100, 0, "at_least_15"),  # 初始 15 条，其他测试可能加更多
        (10, 10, "at_least_5"),
        (10, 100, 0),
    ],
)
def test_parametrized_pagination(client, limit, offset, expected_count) -> None:
    """parametrize 5 组 (limit, offset)。

    注意：/posts 是内存路由，POSTS 是全局可变列表，其他测试可能加数据；
    所以前两条用 == 严格断言（初始至少 15 条够），后两条用 >= 兜底。
    """
    r = client.get(f"/posts?limit={limit}&offset={offset}")
    assert r.status_code == 200
    n = len(r.json())
    if expected_count == "at_least_15":
        assert n >= 15
    elif expected_count == "at_least_5":
        assert n >= 5
    else:
        assert n == expected_count


def test_mock_email_service(client, mock_email) -> None:
    """用 mock 替换 send_welcome_email：BackgroundTasks 触发后调用计数 +1。"""
    EmailLog.reset()
    # POST /db/posts 会触发 BackgroundTasks -> send_welcome_email
    r = client.post("/db/posts", json={"title": "MockedBG", "content": "x"})
    assert r.status_code == 201
    # with TestClient 结束后 BG 任务才跑
    # mock_email fixture 把 send_welcome_email 替换掉了，EmailLog 不会被写
    # 验证 mock 被调用了
    assert mock_email.call_count >= 1


def test_tmp_path_persistence(tmp_path) -> None:
    """tmp_path 测试持久化（每个测试独立的临时目录）。"""
    p = tmp_path / "data.txt"
    p.write_text("hello", encoding="utf-8")
    assert p.read_text(encoding="utf-8") == "hello"


def test_async_with_httpx(async_client) -> None:
    """httpx AsyncClient 测异步路径。"""
    r = asyncio.run(async_client.get("/health"))
    assert r.status_code == 200


def test_coverage_config_present() -> None:
    """pytest-cov 已安装在依赖里。"""
    import importlib

    mod = importlib.import_module("pytest_cov")
    assert mod is not None
