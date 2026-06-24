# task-11: 数据库集成 SQLAlchemy（同步 + 异步）

## 目标
把内存 POSTS 换成 SQLAlchemy 真实数据库，使用 SQLAlchemy 2.0 风格 + aiosqlite 异步驱动。Author/Post 两表，CRUD 重构。

## 涉及文件
- `app/db/__init__.py`
- `app/db/base.py`（DeclarativeBase + async engine + session）
- `app/models/author.py` / `app/models/post.py`
- `app/crud/posts.py` / `app/crud/authors.py`
- `app/core/deps.py`（替换 get_db 为真实 session）
- `app/main.py`（路由改 async 调用 crud）
- `docs/lessons/11-database.md`
- `tests/test_11_database.py`

## 验收标准
- [ ] 使用 SQLAlchemy 2.0 DeclarativeBase + Mapped[...]
- [ ] async engine（sqlite+aiosqlite）+ async_sessionmaker
- [ ] Author 与 Post 一对多关系
- [ ] get_db 改为 async generator（yield AsyncSession）
- [ ] POST/GET/PUT/DELETE 走真实数据库，其中 `PUT /db/posts/{id}` 更新 title/content
- [ ] 事务回滚生效
- [ ] 测试每个用例独立内存库（fixture）
- [ ] 8 条测试全绿

## 测试点（至少 8 条）
1. `test_create_post_persisted`：创建后能查到
2. `test_list_posts_from_db`：列表来自 DB
3. `test_update_post`：`PUT /db/posts/{id}` 更新 title/content 后，详情接口返回新内容
4. `test_delete_post`：删除后 404
5. `test_get_post_not_found_404`：不存在 ID 404
6. `test_title_unique_constraint`：title 重复抛 IntegrityError
7. `test_transaction_rollback`：异常后回滚不留脏数据
8. `test_concurrent_sessions_isolated`：两个测试用例 DB 隔离

## 实现要点
```python
# app/db/base.py
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine
)
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

engine = create_async_engine("sqlite+aiosqlite:///./blog.db", echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# app/models/post.py
from sqlalchemy import String, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), unique=True)
    content: Mapped[str] = mapped_column(Text)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("authors.id"))
    author: Mapped["Author"] = relationship(back_populates="posts")

# app/core/deps.py
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

# app/crud/posts.py
from sqlalchemy import select

async def create_post(db: AsyncSession, data: dict) -> Post:
    post = Post(**data)
    db.add(post)
    await db.flush()
    return post

async def list_posts(db: AsyncSession) -> list[Post]:
    result = await db.execute(select(Post))
    return result.scalars().all()

async def update_post(db: AsyncSession, post_id: int, data: dict) -> Post | None:
    post = await get_post(db, post_id)
    if post is None:
        return None
    post.title = data["title"]
    post.content = data["content"]
    await db.flush()
    return post
```
- 测试用 in-memory sqlite：`create_async_engine("sqlite+aiosqlite:///:memory:")` + per-test fixture
- 用 `mapped_column(String(200), unique=True)` 加约束

## 教学文档大纲
1. 【新手】什么是 ORM，为什么用 SQLAlchemy
2. 【新手】SQLAlchemy 2.0 vs 1.x 风格差异
3. 【新手】DeclarativeBase + Mapped
4. 【新手】engine + sessionmaker
5. 【进阶】async engine + aiosqlite
6. 【进阶】关系与 back_populates
7. 【进阶】事务与回滚
8. 思考题：N+1 问题怎么避免（joinedload/selectinload）？
