# 第 5 课 · 响应模型 response_model 与状态码

> 难度：【新手】为主，含【进阶】延伸。
>
> 学完本节，你能用 `response_model` 强制过滤响应字段（防止敏感泄露）、自定义状态码、用 `JSONResponse` 改写响应结构。

---

## 5.1 【新手】为什么需要 response_model

考虑这个场景：

```python
@app.get("/posts/{id}")
def get_post(id: int):
    return db.query(Post).get(id)  # 直接返回 ORM 对象
```

ORM 对象里可能有 `password` / `is_deleted` / `internal_state` 等敏感字段——直接 return 就**泄露到响应里**了。

正确做法：用 `response_model` 声明响应的"对外形状"，FastAPI 会按模型**强制过滤**：

```python
class PostOut(BaseModel):
    id: int
    title: str
    content: str
    author: AuthorOut | None = None
    # 没有 is_deleted / 没有 password

@app.get("/posts/{id}", response_model=PostOut)
def get_post(id: int):
    return db.query(Post).get(id)  # 即使含 password 也会被过滤
```

---

## 5.2 【新手】状态码

```python
@app.post("/posts", status_code=201)  # 整个路由固定 201
def create_post(...): ...

@app.get("/posts/{id}")
def get_post(id: int):
    if not found:
        return JSONResponse(status_code=404, content={...})  # 单次响应改状态码
    return post
```

常用：
- `200` 默认 GET / PUT / PATCH
- `201` POST 创建
- `204` DELETE 成功无响应体
- `404` 资源不存在
- `422` 校验失败（FastAPI 默认）

---

## 5.3 【新手】JSONResponse 自定义响应

`return JSONResponse(status_code=..., content={...})` 完全绕过 response_model，直接控制响应。本课 404 用它返回统一结构：

```python
return JSONResponse(
    status_code=404,
    content={"error": {"code": "POST_NOT_FOUND", "message": "..."}}
)
```

---

## 5.4 【进阶】response_model_exclude / include

```python
@app.get("/posts/{id}/brief",
         response_model=PostOut,
         response_model_include={"id", "title"})  # 白名单
def brief(id): ...

@app.get("/posts/{id}/full",
         response_model=PostOut,
         response_model_exclude={"metadata"})  # 黑名单
def full(id): ...
```

`include` 是白名单（只暴露这几个字段），`exclude` 是黑名单（除了这几个都暴露）。

> 两者优先级：include > exclude。同时设置时 include 生效。

---

## 5.5 【进阶】嵌套模型的过滤

```python
class AuthorOut(BaseModel):
    id: int
    username: str
    # 不写 password / email
```

把 PostOut.author 声明为 `AuthorOut | None`，即使内部 dict 里 `author` 含 password，FastAPI 在序列化时也会按 AuthorOut 过滤。

> 这是为什么"嵌套响应模型"是安全设计的关键。

---

## 5.6 【进阶】在响应里设置 Cookie / Header

```python
@app.post("/posts", status_code=201)
def create_post(payload: PostCreate, response: Response):
    response.headers["X-Blog-Version"] = app.version
    response.set_cookie(
        key="last_create",
        value=payload.title[:32],
        httponly=True,
        samesite="lax",
    )
    return post
```

`response: Response` 是 FastAPI 自动注入的特殊参数。`response.set_cookie(...)` 的安全属性：

| 属性 | 作用 |
|---|---|
| `httponly=True` | JS 无法读取（防 XSS） |
| `secure=True` | 仅 HTTPS |
| `samesite="strict"/"lax"` | 防 CSRF |

---

## 5.7 思考题

1. 如果一个接口想让管理员看到 is_deleted，普通用户看不到，应该怎么实现？（提示：response_model_by_alias + 动态模型）
2. `response_model_include` 和"在函数里删字段"哪种更安全？为什么？
3. JSONResponse 绕过了 response_model，会带来什么风险？

---

## 5.8 本节交付物

| 文件 | 作用 |
|---|---|
| `app/schemas/author.py` | `AuthorOut`（不含 password/email） |
| `app/schemas/post.py` | 新增 `PostOut`（不含 is_deleted） |
| `app/main.py` | list/get/create 加 response_model；新增 brief/full 端点；POST 设置 Set-Cookie 与 X-Blog-Version；404 改成自定义 JSONResponse |
| `tests/test_05_response.py` | 8 条测试 |
| `docs/lessons/05-response.md` | 本文 |

---

## 5.9 下一节预告

第 6 课我们引入 **依赖注入 Depends**：把分页、数据库会话、当前作者等公共逻辑抽成可复用、可测试的依赖。
