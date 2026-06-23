# task-15: OpenAPI 文档定制与版本化

## 目标
整理博客 OpenAPI：tags_metadata 分组、examples、deprecated、responses 多状态码文档、/api/v1 与 /api/v2 共存。

## 涉及文件
- `app/api/__init__.py`（routers 聚合）
- `app/api/v1.py` / `app/api/v2.py`（版本路由）
- `app/main.py`（include_router with prefix + openapi_tags）
- `docs/lessons/15-openapi.md`
- `tests/test_15_openapi.py`

## 验收标准
- [ ] openapi_tags 定义 posts/users/comments/auth/stats 5 组
- [ ] POST /posts 含 examples + responses(201/422/401) 文档
- [ ] GET /posts/old 标记 deprecated
- [ ] /api/v1/posts 与 /api/v2/posts 同时可访问
- [ ] v2 支持新字段（如 publishedAt）
- [ ] /docs 标题改为 "Blog API Docs"
- [ ] 自定义 openapi() 路径生效
- [ ] 8 条测试全绿

## 测试点（至少 8 条）
1. `test_openapi_has_tags`：/openapi.json 含 tags 列表
2. `test_tags_metadata_order`：5 个 tag 按定义顺序
3. `test_deprecated_marked`：/posts/old 有 deprecated: true
4. `test_examples_in_request_body`：requestBody 含 examples
5. `test_responses_has_422`：responses 包含 422 文档
6. `test_v1_v2_isolated`：/api/v1/posts 与 /api/v2/posts 都可访问
7. `test_docs_title_custom`：/docs 页面标题是 "Blog API Docs"
8. `test_custom_openapi_schema`：自定义 openapi() 注入了额外字段

## 实现要点
```python
from fastapi import FastAPI, APIRouter

tags_metadata = [
    {"name": "posts", "description": "文章 CRUD"},
    {"name": "users", "description": "作者相关"},
    {"name": "comments", "description": "评论"},
    {"name": "auth", "description": "认证"},
    {"name": "stats", "description": "统计"},
]

app = FastAPI(
    title="Blog API",
    version="2.0.0",
    openapi_tags=tags_metadata,
    docs_url="/docs",
)

v1 = APIRouter(prefix="/api/v1", tags=["posts"])
v2 = APIRouter(prefix="/api/v2", tags=["posts"])

@v1.get("/posts/{post_id}")
def v1_get_post(post_id: int): ...

@v2.get("/posts/{post_id}")
def v2_get_post(post_id: int): ...  # 返回多了 publishedAt 字段

@app.get("/posts/old", deprecated=True, tags=["posts"])
def legacy_list(): ...

@app.post(
    "/posts",
    response_model=PostOut,
    status_code=201,
    responses={
        201: {"description": "Created"},
        401: {"description": "Unauthorized"},
        422: {"description": "Validation Error"},
    },
    tags=["posts"],
)
async def create_post(
    payload: PostCreate = Body(
        openapi_examples={
            "minimal": {"summary": "最小示例", "value": {"title": "x", "content": "y"}},
            "full": {"summary": "完整示例", "value": {...}},
        }
    ),
): ...
```
- 自定义 `app.openapi()` 可在文档里注入额外字段（如 x-logo）

## 教学文档大纲
1. 【新手】什么是 OpenAPI / Swagger UI / ReDoc
2. 【新手】tags 分组与 openapi_tags
3. 【新手】deprecated 标记
4. 【进阶】responses 多状态码文档
5. 【进阶】examples（openapi_examples）
6. 【进阶】API 版本化（prefix / 双 router）
7. 【进阶】自定义 openapi() 函数
8. 思考题：如何把 OpenAPI 文档导出给前端用？
