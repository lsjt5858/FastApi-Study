# 第 15 课 · OpenAPI 文档定制与版本化

> 难度：【新手】打底，【进阶】收尾。
>
> 学完本节，你能用 `openapi_tags` 给路由分组、用 `responses` 文档化多状态码、用 `openapi_examples` 给请求体加示例、用 `deprecated=True` 标记旧端点、用 v1/v2 双 router 实现 API 版本化、用自定义 `app.openapi()` 注入扩展字段。

---

## 15.1 【新手】什么是 OpenAPI / Swagger / ReDoc

| 概念 | 是什么 |
|---|---|
| OpenAPI | 一份 JSON/YAML 描述 REST API 的规范（formerly Swagger Spec） |
| Swagger UI | 把 OpenAPI 渲染成可点击的网页（`/docs`） |
| ReDoc | 另一种渲染（`/redoc`），更易读、不可点 |
| FastAPI 的角色 | 自动从代码（类型注解 + decorator 参数）生成 OpenAPI |

`/openapi.json` 就是机器可读的契约，前端 / 第三方可以基于它生成 SDK。

---

## 15.2 【新手】tags 分组与 openapi_tags

```python
TAGS_METADATA = [
    {"name": "posts", "description": "文章 CRUD"},
    {"name": "users", "description": "作者 / 用户"},
    {"name": "auth", "description": "注册 / 登录"},
]

app = FastAPI(openapi_tags=TAGS_METADATA)

@app.get("/posts", tags=["posts"])
def list_posts(): ...

@app.post("/auth/token", tags=["auth"])
def login(): ...
```

`/docs` 会按 tags 折叠分组；定义顺序就是显示顺序。

---

## 15.3 【新手】deprecated 标记

```python
@app.get("/posts/old", deprecated=True, tags=["posts"])
def legacy_list_posts(): ...
```

Swagger UI 会给这条加红色"Deprecated"标签，告诉调用方尽快迁移。

---

## 15.4 【进阶】responses 多状态码文档

```python
@app.post(
    "/db/posts",
    response_model=PostOut,
    status_code=201,
    responses={
        201: {"description": "Created"},
        401: {"description": "Unauthorized"},
        409: {"description": "Duplicate title"},
        422: {"description": "Validation Error", "content": {...}},
    },
)
async def db_create_post(...): ...
```

201/422 是 FastAPI 自动生成的（response_model / Pydantic 校验），但 401/409 需要手动加，让前端知道这些状态也可能出现。

---

## 15.5 【进阶】openapi_examples

```python
from fastapi import Body

@app.post("/posts")
async def create_post(
    payload: PostCreate = Body(
        openapi_examples={
            "minimal": {"summary": "最小", "value": {"title": "x", "content": "y"}},
            "full": {"summary": "完整", "value": {"title": "...", "content": "...", "tags": ["a"]}},
        },
    ),
): ...
```

Swagger UI 的 "Try it out" 旁边会出现下拉菜单，让用户选示例填充表单，极大降低调试成本。

---

## 15.6 【进阶】API 版本化

两种主流做法：

### 做法 A：双 router + prefix

```python
v1 = APIRouter(prefix="/api/v1", tags=["posts"])
v2 = APIRouter(prefix="/api/v2", tags=["posts"])

@v1.get("/posts/{id}")
def v1_get(id: int): return {"id": id}

@v2.get("/posts/{id}")
def v2_get(id: int): return {"id": id, "publishedAt": "2026-01-01"}

app.include_router(v1)
app.include_router(v2)
```

简单直观；缺点：路由表会膨胀。

### 做法 B：Header `Accept-Version`

```python
@app.get("/posts/{id}")
def get(id: int, accept_version: str = Header(default="v1")):
    if accept_version == "v2":
        return {...}
    return {...}
```

URL 不变；缺点：HTTP 客户端要记得加 header。

---

## 15.7 【进阶】自定义 openapi()

```python
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    schema["info"]["x-logo"] = {"url": "https://example.com/logo.png"}
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi
```

用途：
- 加 `x-logo`（Swagger UI 显示 logo）
- 加 `x-rate-limit`（自定义限流说明）
- 删除内部端点（不让外部看到）
- 加 webhook 定义

---

## 15.8 思考题

1. 怎么把 `/openapi.json` 导出给前端生成 TypeScript 类型？
2. `deprecated=True` 的端点还能用吗？为什么要标记？
3. v1 与 v2 共用同一份 PostCreate schema 时，怎么让 v2 强制要求新字段（如 publishedAt）？

---

## 15.9 本节交付物

| 文件 | 作用 |
|---|---|
| `app/api/versioned.py` | v1_router / v2_router（演示 publishedAt 版本演进） |
| `app/main.py` | TAGS_METADATA + 自定义 openapi() + /posts/old deprecated + include v1/v2 |
| `tests/test_15_openapi.py` | 8 条测试 |
| `docs/lessons/15-openapi.md` | 本文 |

---

## 15.10 下一节预告

第 16 课我们引入 **测试夹具与 dependency_overrides**：用 pytest fixture 工厂生成不同状态的应用，让每个测试拿到隔离的 DB / 认证状态。
