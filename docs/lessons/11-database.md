# 第 11 课 · 数据库集成 SQLAlchemy 2.0 异步

> 难度：【新手】打底，【进阶】收尾。
>
> 学完本节，你能用 SQLAlchemy 2.0 风格（`DeclarativeBase` + `Mapped[...]` + `mapped_column`）定义模型、用 async engine + async session 接入 FastAPI、用 dependency_overrides + in-memory sqlite 写隔离的单元测试。

---

## 11.1 【新手】什么是 ORM

ORM（Object Relational Mapping）把数据库表映射成 Python 类：

| 数据库概念 | SQLAlchemy 类 |
|---|---|
| 表 | `class Post(Base): __tablename__ = "posts"` |
| 列 | `title: Mapped[str] = mapped_column(String(200))` |
| 行 | `post = Post(title="X")` |
| 查询 | `select(Post).where(...)` |

**好处**：
- 写 Python 而不是 SQL，IDE 能补全
- 跨数据库（sqlite / postgres / mysql 同一份代码）
- 自动类型校验

**坏处**：
- 性能比裸 SQL 略差（抽象有代价）
- 复杂 JOIN 写起来反而麻烦

---

## 11.2 【新手】SQLAlchemy 2.0 vs 1.x 风格差异

1.x 老风格：

```python
from sqlalchemy import Column, Integer, String
class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
```

2.0 新风格（**推荐**）：

```python
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
```

`Mapped[int]` 让 IDE / mypy 知道这是 `int` 类型，比 1.x 的 `Column` 更类型友好。

---

## 11.3 【新手】DeclarativeBase + Mapped

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), unique=True)
    content: Mapped[str] = mapped_column(Text)
```

`Mapped[X]` 里 X 就是 Python 类型；SQLAlchemy 会推导出对应 SQL 列类型（int -> INTEGER，str -> VARCHAR/TEXT）。要显式控制列类型，传 `mapped_column(String(200))`。

---

## 11.4 【新手】engine + sessionmaker

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

engine = create_async_engine("sqlite+aiosqlite:///./blog.db")
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
```

- `engine`：管理数据库连接池
- `AsyncSessionLocal`：会话工厂，每次调用生成一个独立 session
- `expire_on_commit=False`：commit 后对象属性仍可访问（避免 lazy load 触发同步 IO）

---

## 11.5 【进阶】async engine + aiosqlite

URL scheme 决定驱动：

| URL | 驱动 |
|---|---|
| `sqlite:///./blog.db` | 同步 sqlite3（标准库） |
| `sqlite+aiosqlite:///./blog.db` | 异步 aiosqlite |
| `postgresql+asyncpg://...` | 异步 asyncpg |
| `mysql+aiomysql://...` | 异步 aiomysql |

```python
engine = create_async_engine("sqlite+aiosqlite:///./blog.db", echo=False)
```

> ⚠️ SQLAlchemy 异步模式需要 `greenlet` 库。没装的话会报 `ValueError: the greenlet library is required`。

---

## 11.6 【进阶】关系与 back_populates

```python
class Author(Base):
    __tablename__ = "authors"
    id: Mapped[int] = mapped_column(primary_key=True)
    posts: Mapped[list["Post"]] = relationship(back_populates="author")

class Post(Base):
    __tablename__ = "posts"
    author_id: Mapped[int | None] = mapped_column(ForeignKey("authors.id"))
    author: Mapped["Author | None"] = relationship(back_populates="posts")
```

`back_populates` 让两边互引：`post.author.posts` 是同一个列表。

---

## 11.7 【进阶】事务与回滚

FastAPI 依赖管理事务：

```python
async def get_async_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

- 路由抛异常 → 自动 `rollback()`，不留脏数据
- 路由正常返回 → 自动 `commit()`

CRUD 操作里用 `db.flush()` 而不是 `db.commit()`，把事务边界交给依赖管理。

---

## 11.8 【进阶】测试隔离：in-memory sqlite + dependency_overrides

```python
@pytest.fixture()
def db_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db():
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_async_db] = _override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
```

每个测试用独立的 in-memory engine，互不干扰；fixture 拆掉时 drop_all + dispose。

---

## 11.9 思考题

1. `expire_on_commit=False` 不设会怎样？为什么 async 场景必须设？
2. N+1 问题：列表查 10 篇文章，每篇 author 各发一次 SQL，怎么避免？（提示：`selectinload`）
3. `db.flush()` 与 `db.commit()` 区别是什么？

---

## 11.10 本节交付物

| 文件 | 作用 |
|---|---|
| `app/db/__init__.py` | Base / engine / AsyncSessionLocal / get_async_db / init_db |
| `app/db/base.py` | re-export 方便导入 |
| `app/models/__init__.py` | Author / Post ORM model |
| `app/crud/__init__.py` | create_post / list_posts / get_post / delete_post |
| `app/main.py` | 新增 `/db/posts` CRUD 路由 + BizDuplicate handler |
| `tests/test_11_database.py` | 8 条测试 + per-test in-memory fixture |
| `docs/lessons/11-database.md` | 本文 |

---

## 11.11 下一节预告

第 12 课我们引入 **OAuth2 + JWT 认证**：用 `python-jose` 签发 access token，passlib + bcrypt 哈希密码，FastAPI 的 `OAuth2PasswordBearer` 自动集成 /docs 登录按钮。
