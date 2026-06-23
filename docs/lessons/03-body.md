# 第 3 课 · 请求体与 Pydantic BaseModel

> 难度：【新手】为主，含【进阶】延伸。
>
> 学完本节，你能为接口接入 JSON 请求体，用 Pydantic 模型 + Field 约束做字段校验，理解嵌套模型、默认值、别名与未知字段策略。

---

## 3.1 【新手】什么是请求体

请求体（request body）是 HTTP 请求里**承载业务数据**的部分，最常见的格式是 JSON：

```http
POST /posts HTTP/1.1
Content-Type: application/json

{"title": "Hello", "content": "World"}
```

对比一下：
- **路径参数** `POST /posts/42` —— 标识"操作哪一篇"
- **查询参数** `POST /posts?draft=true` —— 控制"怎么操作"
- **请求体** `{"title": "..."}` —— 描述"数据是什么"

---

## 3.2 【新手】Pydantic BaseModel 基础

定义一个模型：

```python
from pydantic import BaseModel, ConfigDict, Field

class PostCreate(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    title: str = Field(min_length=1, max_length=200)
    content: str
    tags: list[str] = Field(default_factory=list)
    published: bool = False
```

把它作为 FastAPI 路由参数：

```python
@app.post("/posts", status_code=201)
def create_post(payload: PostCreate):
    return {"id": 1, **payload.model_dump()}
```

FastAPI 看到 `payload: PostCreate`（BaseModel 子类），会自动：
1. 拿到 JSON 请求体
2. 用 Pydantic 校验 → 不通过则 422
3. 把校验后的数据作为 `payload` 实例传给函数

---

## 3.3 【新手】Field 约束

```python
title: str = Field(min_length=1, max_length=200)
price: float = Field(gt=0, le=10000)        # 大于 0，小于等于 10000
name: str = Field(pattern=r"^[a-zA-Z]+$")    # 正则约束
tags: list[str] = Field(default_factory=list, max_length=10)  # 最多 10 个
```

约束失败时，FastAPI 自动返回 422 并指明哪个字段、哪个约束、什么值。

> **细节**：`list[str] = []` 是反模式（可变默认值共享）。用 `Field(default_factory=list)` 每次创建新 list。

---

## 3.4 【进阶】嵌套模型

```python
class PostMeta(BaseModel):
    seo_title: str | None = None
    seo_description: str | None = None
    cover_color: str = "#ffffff"

class PostCreate(BaseModel):
    title: str
    content: str
    metadata: PostMeta | None = None  # 嵌套
```

请求体：

```json
{
  "title": "...",
  "content": "...",
  "metadata": {"seo_title": "SEO", "cover_color": "#ff0000"}
}
```

Pydantic 会递归校验整棵树。`Optional` / `None` 表示"可缺省"。

---

## 3.5 【进阶】别名：AliasChoices

后端字段叫 `tags`，但前端习惯叫 `keywords`？让两个名字都能解析：

```python
from pydantic import AliasChoices

class PostCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    tags: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("tags", "keywords"),
    )
```

- `validation_alias=AliasChoices("tags", "keywords")` —— 输入时两个名字都接受
- `populate_by_name=True` —— 同时允许用 Python 字段名 `tags` 输入

---

## 3.6 【进阶】未知字段策略：extra

```python
class PostCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")  # 默认行为
```

| 选项 | 行为 |
|---|---|
| `"ignore"`（默认） | 未知字段被静默丢弃 |
| `"forbid"` | 未知字段触发 422 |
| `"allow"` | 未知字段被保留，可访问 |

> 生产接口一般用 `"forbid"`，避免前端误传字段时悄悄忽略。本教学为了演示 alias 用了 `"ignore"`。

---

## 3.7 Pydantic v1 vs v2 对照

| v1 | v2 |
|---|---|
| `class Config: orm_mode = True` | `model_config = ConfigDict(from_attributes=True)` |
| `.dict()` | `.model_dump()` |
| `Field(..., regex=r"...")` | `Field(..., pattern=r"...")` |
| `@validator` | `@field_validator` |
| `.dict()` 不接受 `by_alias` 默认 | `model_dump(by_alias=True)` 显式 |

> 本教学严格用 Pydantic v2 语法（Pydantic 2.13+）。

---

## 3.8 思考题

1. 如果一个字段同时有 `default` 和 `Field(...)` 约束，缺省值会过校验吗？（提示：先填默认值再校验）
2. `tags: list[str] = []` 和 `tags: list[str] = Field(default_factory=list)` 在并发下有什么区别？
3. `extra="forbid"` 在生产里能拦截什么 bug？

---

## 3.9 本节交付物

| 文件 | 作用 |
|---|---|
| `app/schemas/post.py` | `PostCreate` + `PostMeta`（嵌套 + AliasChoices + extra=ignore） |
| `app/main.py` | 新增 `POST /posts` |
| `tests/test_03_body.py` | 8 条测试（含 alias / 嵌套 / 边界 / 未知字段） |
| `docs/lessons/03-body.md` | 本文 |

---

## 3.10 下一节预告

第 4 课我们引入 **Header / Cookie / Form / 文件上传**，实现 `POST /posts/{post_id}/cover` 上传封面图，演示非 JSON 输入与 UploadFile。
