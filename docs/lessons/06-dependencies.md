# 第 6 课 · 依赖注入 Depends

> 难度：【新手】为主，含【进阶】延伸。
>
> 学完本节，你能用 Depends 把"路由需要的辅助逻辑"抽成可复用、可测试的依赖。

---

## 6.1 【新手】为什么需要依赖注入

假设三个接口都要"解析 token 拿当前作者"、"按 limit/offset 分页"、"打开数据库会话"。

不用 DI：每个接口都重复一遍逻辑。代码重复 + 测试时要 mock 多处。

用 DI：把这些逻辑写成**依赖函数**，路由声明依赖，FastAPI 自动调用 + 注入结果。

```python
@app.delete("/posts/{id}")
def delete_post(id: int, author: dict = Depends(get_current_active_author)):
    # author 是 get_current_active_author 返回的 dict
    ...
```

---

## 6.2 【新手】Depends 基础

```python
def pagination(limit: int = 10, offset: int = 0) -> Pagination:
    return Pagination(limit=limit, offset=offset)

@app.get("/posts")
def list_posts(pag: Annotated[Pagination, Depends(pagination)]):
    return POSTS[pag.offset : pag.offset + pag.limit]
```

`Depends(pagination)` 让 FastAPI：
1. 把路由的 query 参数 limit/offset 喂给 pagination
2. 拿到 Pagination 实例
3. 作为 `pag` 参数注入路由

---

## 6.3 【新手】嵌套依赖

```python
def get_current_author(authorization: str | None = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(401, "Missing authorization")
    return {"username": "alice", "is_active": True}

def get_current_active_author(
    author: Annotated[dict, Depends(get_current_author)],  # ← 嵌套
) -> dict:
    if not author["is_active"]:
        raise HTTPException(403, "Inactive")
    return author
```

`get_current_active_author` 自己依赖 `get_current_author`。FastAPI 自动按依赖图调用，最深的先执行。

---

## 6.4 【进阶】yield 依赖：自动资源清理

```python
def get_db():
    db = open_session()
    try:
        yield db
    finally:
        db.close()  # 请求结束自动调用，即使发生异常

@app.post("/posts")
def create_post(payload: PostCreate, db: dict = Depends(get_db)):
    # 用 db ...
```

`yield` 让依赖变成 generator。`yield db` 之前的代码是 setup，之后是 cleanup。请求结束（或抛异常）时 finally 必触发。

> 这是数据库连接、文件锁、Redis 连接等"资源型"依赖的标准写法。

---

## 6.5 【进阶】Class-based 依赖

```python
@dataclass
class PaginationDep:
    limit: int = 10
    offset: int = 0

@app.get("/posts")
def list_posts(pag: Annotated[PaginationDep, Depends()]):
    # FastAPI 用 PaginationDep.__init__ 签名注入 query 参数
    ...
```

适合"需要内部状态"的依赖（如缓存计算结果、复用配置）。

---

## 6.6 【进阶】全局 vs 路由级 dependency_overrides

**测试时替换依赖**：

```python
def fake_db():
    yield {"session_id": "fake"}

app.dependency_overrides[get_db] = fake_db

# 现在所有依赖 get_db 的接口都拿 fake_db
```

`app.dependency_overrides` 是全局 dict，**所有路由**的相同依赖都被替换。测试结束记得 `pop` 还原。

也可以在 `APIRouter(dependencies=[...])` 级别加依赖，只对一组路由生效。

---

## 6.7 思考题

1. yield 依赖在请求过程中抛异常，finally 还会执行吗？（提示：会）
2. 嵌套依赖的执行顺序是什么？（提示：拓扑序，最深的先）
3. `Depends(pagination)` 和 `Depends()`（不传参）有什么区别？

---

## 6.8 本节交付物

| 文件 | 作用 |
|---|---|
| `app/core/__init__.py` | core 层包初始化 |
| `app/core/deps.py` | pagination/PaginationDep/get_db/get_current_author/get_current_active_author |
| `app/data.py` | POSTS/USERS 提到独立模块（避免循环 import） |
| `app/main.py` | POST /posts 加 get_db 依赖；新增 DELETE /posts/{id}（依赖 get_current_active_author） |
| `tests/test_06_dependencies.py` | 10 条测试 |
| `docs/lessons/06-dependencies.md` | 本文 |

---

## 6.9 下一节预告

第 7 课我们引入 **Pydantic 校验器与自定义类型**：自动 strip title、生成 slug、去重 tags、校验手机号。
