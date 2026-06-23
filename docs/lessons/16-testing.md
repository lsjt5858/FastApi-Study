# 第 16 课 · 测试体系 TestClient + Fixture

> 难度：【新手】打底，【进阶】收尾。
>
> 学完本节，你能用 pytest fixture 隔离每个测试的 DB / 认证状态、用 dependency_overrides 替换 FastAPI 依赖、用 httpx AsyncClient 测异步路径、用 parametrize 批量化、用 monkeypatch mock 外部服务。

---

## 16.1 【新手】为什么需要 fixture

测试代码如果直接 `import app.main; client = TestClient(app)`，会有几个问题：
- 全局 POSTS 列表会被前一个测试污染
- 数据库文件残留脏数据
- 外部服务（邮件）真的会被调用

`pytest fixture` 提供可复用的"测试准备/清理"逻辑，每个测试自动拿到隔离的环境。

---

## 16.2 【新手】TestClient 基础

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
```

`TestClient` 内部用 httpx 发请求，但**同步阻塞**——适合大多数用例。

---

## 16.3 【新手】conftest.py 共享 fixture

`tests/conftest.py` 是 pytest 自动加载的"全局 fixture 库"。里面定义的 fixture，所有测试文件都能直接用：

```python
# tests/conftest.py
import pytest

@pytest.fixture()
def client():
    ...
```

```python
# tests/test_xxx.py
def test_something(client):   # 自动注入
    ...
```

不用 import；conftest.py 的存在就是声明"这些 fixture 全项目可用"。

---

## 16.4 【进阶】dependency_overrides 替换依赖

FastAPI 的 `app.dependency_overrides` 是测试的瑞士军刀：

```python
from app.db import get_async_db
from app.main import app

async def _override_get_db():
    async with TestSessionLocal() as session:
        yield session

app.dependency_overrides[get_async_db] = _override_get_db
```

之后所有 `Depends(get_async_db)` 的路由，拿到的就是 `TestSessionLocal` 而不是生产 engine。

**关键**：fixture 拆掉时必须 `.clear()`，否则污染其他测试。

---

## 16.5 【进阶】httpx.AsyncClient 测异步

`TestClient` 是同步的。要测真正的 async 路径（如 `await asyncio.gather`），用 AsyncClient：

```python
from httpx import ASGITransport, AsyncClient

transport = ASGITransport(app=app)
async with AsyncClient(transport=transport, base_url="http://test") as ac:
    r = await ac.get("/stats/aggregate/1")
```

ASGITransport 直接走 ASGI 协议，不开 socket，比真发请求快。

---

## 16.6 【进阶】pytest.mark.parametrize

```python
@pytest.mark.parametrize("limit,offset,expected", [
    (1, 0, 1),
    (5, 0, 5),
    (100, 0, 15),
])
def test_pagination(client, limit, offset, expected):
    r = client.get(f"/posts?limit={limit}&offset={offset}")
    assert len(r.json()) == expected
```

pytest 会自动跑 3 次，每次一个组合，输出 `test_pagination[1-0-1]` 这种带后缀的 case。

---

## 16.7 【进阶】mock 外部服务

```python
from unittest.mock import AsyncMock

@pytest.fixture()
def mock_email(monkeypatch):
    mock = AsyncMock(return_value=None)
    import app.main
    monkeypatch.setattr(app.main, "send_welcome_email", mock)
    return mock

def test_create_post_triggers_email(client, mock_email):
    client.post("/db/posts", json={"title": "X", "content": "Y"})
    # with 退出后 BG 任务才跑
    assert mock_email.call_count >= 1
```

`monkeypatch` 是 pytest 内置的，比 `unittest.mock.patch` 干净——测试结束自动还原。

---

## 16.8 【进阶】tmp_path 测试持久化

```python
def test_file_write(tmp_path):
    p = tmp_path / "data.txt"
    p.write_text("hello")
    assert p.read_text() == "hello"
```

`tmp_path` 每个 test 独立目录，pytest 自动清理。比手写 `/tmp/xxx` 安全。

---

## 16.9 思考题

1. fixture scope=function 与 scope=session 的区别？什么场景用 session？
2. `dependency_overrides` 替换依赖时，子依赖会不会被一起替换？
3. `pytest-cov --cov=app --cov-report=html` 怎么集成到 CI？

---

## 16.10 本节交付物

| 文件 | 作用 |
|---|---|
| `tests/conftest.py` | db_factory / db_client / client / async_client / mock_email |
| `tests/test_16_blog_fixtures.py` | 8 条测试 + 5 条 parametrize |
| `docs/lessons/16-testing.md` | 本文 |

---

## 16.11 下一节预告

第 17 课我们引入 **项目结构重构**：把所有路由从 main.py 拆到 `app/routers/` 目录，把业务逻辑拆到 `app/services/`，遵循 FastAPI 大型项目分层约定。
