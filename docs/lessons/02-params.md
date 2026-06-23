# 第 2 课 · 路径参数、查询参数与枚举

> 难度：【新手】为主，末尾含【进阶】延伸。
>
> 学完本节，你能为接口加丰富的参数声明：路径参数、查询参数、默认值、可选参数、Enum 枚举约束。

---

## 2.1 【新手】三种"参数"的区别

一个 HTTP 接口能从客户端拿到数据的位置有四种：

| 来源 | 位置 | FastAPI 怎么接 |
|---|---|---|
| 路径参数 | `/posts/{post_id}` 的 `{post_id}` | 函数参数同名 |
| 查询参数 | `?limit=10&offset=0` | 函数参数（无 `{}` 占位） |
| 请求体 | JSON / form / file | Pydantic 模型或 `UploadFile`（task-3/4） |
| 请求头/Cookie | `X-Token: xxx` | `Header()` / `Cookie()`（task-4） |

**判别规则**：FastAPI 看函数参数的类型：
- 是 `int` / `str` / `bool` 等基本类型 → 当作**路径或查询**参数
- 是 Pydantic BaseModel → 当作**请求体**
- 用了 `Query()` / `Path()` / `Header()` / `Cookie()` / `Body()` 等 → 显式声明来源

---

## 2.2 【新手】类型注解自动校验

```python
@app.get("/posts/{post_id}")
def get_post(post_id: int):
    ...
```

访问 `/posts/abc` 时，FastAPI 不能把 `"abc"` 转成 `int`，会自动返回：

```
HTTP/1.1 422 Unprocessable Entity
{
  "detail": [{
    "type": "int_parsing",
    "loc": ["path", "post_id"],
    "msg": "Input should be a valid integer..."
  }]
}
```

> 关键认知：你写的是 Python 类型注解，FastAPI 把它当成"接口契约"自动校验，并把错误转成标准的 RFC 7807 风格响应。

---

## 2.3 【新手】查询参数 + Query 边界

```python
from typing import Annotated
from fastapi import Query

@app.get("/posts")
def list_posts(
    limit: Annotated[int, Query(ge=1, le=100, description="每页条数，1~100")] = 10,
    offset: Annotated[int, Query(ge=0, description="偏移量，>=0")] = 0,
    published: Annotated[bool | None, Query(description="按 published 过滤")] = None,
    status: Annotated[PostStatus | None, Query(description="按 status 枚举过滤")] = None,
):
    ...
```

- `ge=1` (greater than or equal)、`le=100` (less than or equal) 限定数值范围
- `gt` / `lt` / `min_length` / `max_length` / `pattern`（正则）也都可用
- `Annotated[T, Query(...)]` 是 FastAPI 0.95+ 的推荐写法，比 `param: T = Query(...)` 更清晰

---

## 2.4 【新手】枚举约束

```python
from enum import Enum

class PostStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"
```

把参数声明为 `status: PostStatus | None = None`：
- 合法值 → FastAPI 自动转成 `PostStatus` 实例
- 非法值 → 422，错误消息列出**所有允许的枚举值**，前端可据此显示下拉框
- OpenAPI 文档里该参数会变成 `enum: ["draft", "published", "archived"]`

**为什么 `(str, Enum)` 双继承？** 因为 FastAPI 内部用 `PostStatus("draft")` 构造，纯 Enum 不支持这种字符串构造。

---

## 2.5 【进阶】Annotated 风格 vs 默认值风格

```python
# 风格 A（老式默认值）
def f(limit: int = Query(10, ge=1)): ...

# 风格 B（PEP 593 Annotated）
def f(limit: Annotated[int, Query(ge=1)] = 10): ...
```

为什么推荐 B：
1. 类型 `int` 与约束 `Query` 分离，IDE 提示更准
2. 同一参数可以叠加多个约束：`Annotated[int, Query(ge=1), SomeOther]`
3. Pydantic v2 / FastAPI 新文档统一用这种风格

> Ruff 也会用 `B008` 规则提示你从 A 迁移到 B（本仓库 `pyproject.toml` 已启用）。

---

## 2.6 【进阶】bool 在 FastAPI 里的解析规则

FastAPI（实际是 Pydantic）会把以下字符串都解析成 `True`：`"true"` / `"True"` / `"TRUE"` / `"1"` / `"yes"` / `"on"`。

对应地 `"false"` / `"0"` / `"no"` / `"off"` 解析成 `False`。

> 这是为什么 `?published=true` 能直接得到 `published == True` 的原因。但生产环境建议用 `"1"` / `"0"`，避免大小写歧义。

---

## 2.7 思考题

1. 如果把 `limit: Annotated[int, Query(ge=1, le=100)] = 10` 改成 `limit: int = 10`，会发生什么？（边界校验还有吗？文档会变吗？）
2. 如果一个查询参数想接受"任意字符串但不能为空"，应该怎么写？
3. `/posts/{post_id}` 和 `/posts/some_fixed_path` 同时声明时，谁优先？为什么？

---

## 2.8 本节交付物

| 文件 | 作用 |
|---|---|
| `app/schemas/__init__.py` | 让 `schemas/` 成为包 |
| `app/schemas/enums.py` | `PostStatus` 枚举 |
| `app/main.py` | 新增 `GET /posts`（分页+过滤）+ `GET /users/{username}`；POSTS 扩到 15 条带 status/published |
| `tests/test_02_params.py` | 8 条测试，全绿 |
| `docs/lessons/02-params.md` | 本文 |

---

## 2.9 下一节预告

第 3 课我们引入 **请求体**：`POST /posts` 接收 JSON，用 Pydantic `BaseModel` + `Field` 约束做字段校验，演示嵌套模型与别名。
