# task-16: 测试体系 TestClient + Fixture

## 目标
把博客测试重构为体系化：conftest.py 提供 client/db_session/current_author fixture；dependency_overrides 替换 db；httpx.AsyncClient 测异步；参数化；mock 外部邮件。

## 涉及文件
- `tests/conftest.py`（核心 fixture）
- `tests/test_16_blog_fixtures.py`（验证 fixture 体系）
- `docs/lessons/16-testing.md`
- `pyproject.toml` 或 `pytest.ini`（pytest-asyncio 配置）

## 验收标准
- [ ] conftest.py 提供 client / db_session / current_author / mock_email fixture
- [ ] dependency_overrides 替换真实 db
- [ ] httpx.AsyncClient 测异步路径
- [ ] pytest.mark.parametrize 参数化分页
- [ ] mock 外部邮件（unittest.mock 或 pytest-mock）
- [ ] tmp_path 测试持久化
- [ ] pytest-cov 覆盖率统计
- [ ] 8 条测试全绿

## 测试点（至少 8 条）
1. `test_client_fixture_reusable`：fixture 在多测试间复用
2. `test_db_overridden`：dependency_overrides 替换 get_db
3. `test_parametrized_pagination`：parametrize 5 组 limit/offset
4. `test_mock_email_service`：用 mock 替换 send_welcome_email
5. `test_tmp_path_persistence`：tmp_path 测试上传文件
6. `test_async_with_httpx`：AsyncClient 测 /stats/aggregate
7. `test_each_test_isolated_db`：每用例独立内存库
8. `test_coverage_runs`：pytest-cov 报告生成

## 实现要点
```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.core.deps import get_db
from app.db.base import Base

@pytest.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()

@pytest.fixture
def client(test_db):
    async def _override():
        yield test_db
    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
async def async_client(test_db):
    async def _override():
        yield test_db
    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.fixture
def mock_email(mocker):
    return mocker.patch("app.services.email.send_welcome_email", return_value=None)
```
- 用 pytest-asyncio 的 `asyncio_mode = "auto"` 自动识别 async 测试
- dependency_overrides 在 yield 后清理，避免污染其他用例

## 教学文档大纲
1. 【新手】为什么需要 fixture
2. 【新手】TestClient 基础
3. 【新手】conftest.py 共享 fixture
4. 【进阶】dependency_overrides 替换依赖
5. 【进阶】httpx.AsyncClient 测异步
6. 【进阶】pytest.mark.parametrize
7. 【进阶】mock 外部服务
8. 思考题：如何测 BackgroundTasks 触发的真实逻辑？
