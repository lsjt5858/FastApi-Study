# task-2: 路径参数、查询参数与枚举

## 目标
为博客文章列表/详情接口加丰富的参数声明：路径参数类型校验、查询参数默认值、Enum 枚举约束。

## 涉及文件
- `app/main.py`（扩展路由）
- `app/schemas/__init__.py` + `app/schemas/enums.py`（PostStatus 枚举）
- `docs/lessons/02-params.md`
- `tests/test_02_params.py`

## 验收标准
- [ ] GET /posts 支持 ?limit=10&offset=0&published=true&status=published
- [ ] GET /posts/{post_id} 的 post_id 强制 int，传入 str 返回 422
- [ ] GET /users/{username} 支持 str 路径参数
- [ ] PostStatus Enum 包含 draft/published/archived 三态
- [ ] 非法枚举值返回 422 且错误消息指出允许值
- [ ] 8 条测试全绿
- [ ] 复用 task-1 的 app/main.py 骨架，只增量修改

## 测试点（至少 8 条）
1. `test_list_posts_default_pagination`：GET /posts 返回前 10 条
2. `test_list_posts_custom_limit_offset`：?limit=5&offset=2 分页生效
3. `test_list_posts_filter_published`：?published=true 只回 published
4. `test_list_posts_filter_status_enum_valid`：?status=published 正常
5. `test_list_posts_filter_status_enum_invalid`：?status=xyz 返回 422
6. `test_get_post_id_must_be_int`：/posts/abc 返回 422
7. `test_get_user_by_username_str`：/users/alice 正常返回
8. `test_combined_query_params`：?limit=5&offset=0&published=true&status=published 组合生效

## 实现要点
```python
from enum import Enum
from fastapi import Query

class PostStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"

@app.get("/posts")
def list_posts(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    published: bool | None = None,
    status: PostStatus | None = None,
):
    items = POSTS
    if published is not None:
        items = [p for p in items if p.get("published") == published]
    if status is not None:
        items = [p for p in items if p.get("status") == status.value]
    return items[offset : offset + limit]
```
- 优先使用 `Query(ge=1, le=100)` 加边界约束
- Enum 同时继承 `str, Enum`，OpenAPI 才能正确显示枚举

## 教学文档大纲
1. 【新手】路径参数 vs 查询参数 vs 请求体的区别
2. 【新手】类型注解自动校验
3. 【新手】Query/Path 的默认值与边界
4. 【进阶】Enum 集成 + OpenAPI 文档表现
5. 【进阶】Annotated 风格 vs 默认值风格（PEP 593）
6. 思考题：bool 类型 FastAPI 怎么解析 "true"/"1"/"yes"？
