# task-3: 请求体与 Pydantic BaseModel

## 目标
实现 POST /posts 创建文章接口，引入 Pydantic BaseModel、嵌套模型、Field 约束、Optional、别名 alias。

## 涉及文件
- `app/schemas/post.py`（PostCreate / PostMeta / Tag 模型）
- `app/main.py`（新增 POST /posts）
- `docs/lessons/03-body.md`
- `tests/test_03_body.py`

## 验收标准
- [ ] POST /posts 接收 JSON 创建文章，返回 201 + 文章对象
- [ ] PostCreate 含 title（min_length=1, max_length=200）/ content / tags / metadata / published
- [ ] PostMeta 嵌套模型（seo_title、seo_description、cover_color）
- [ ] title 过短/过长返回 422
- [ ] 缺 title 返回 422
- [ ] 未知字段被静默忽略（默认行为）
- [ ] alias 别名输入（如 `@alias` 字段映射）
- [ ] 8 条测试全绿

## 测试点（至少 8 条）
1. `test_create_post_success`：合法 JSON 返回 201
2. `test_create_post_missing_title`：缺 title 返回 422
3. `test_create_post_title_too_long`：title 长度 > 200 返回 422
4. `test_create_post_with_nested_metadata`：metadata 正常解析
5. `test_create_post_tags_default_empty`：不传 tags 默认 []
6. `test_create_post_published_default_false`：不传 published 默认 false
7. `test_create_post_with_alias`：用 alias 字段名输入能解析
8. `test_create_post_unknown_field_ignored`：未知字段不报错

## 实现要点
```python
from pydantic import BaseModel, Field
from pydantic import ConfigDict

class PostMeta(BaseModel):
    seo_title: str | None = None
    seo_description: str | None = None
    cover_color: str = "#ffffff"

class PostCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=1, max_length=200)
    content: str
    tags: list[str] = []
    metadata: PostMeta | None = None
    published: bool = False

@app.post("/posts", status_code=201)
def create_post(payload: PostCreate):
    new_id = max(p["id"] for p in POSTS) + 1 if POSTS else 1
    post = {"id": new_id, **payload.model_dump()}
    POSTS.append(post)
    return post
```
- 用 Pydantic v2 风格 `model_config = ConfigDict(extra="ignore")` 替代 v1 `class Config`
- `model_dump()` 替代 v1 `dict()`

## 教学文档大纲
1. 【新手】什么是请求体 / Content-Type: application/json
2. 【新手】BaseModel 基础
3. 【新手】Field 约束（min/max/length/pattern）
4. 【进阶】嵌套模型与 list[str] 类型
5. 【进阶】Optional 与默认值
6. 【进阶】别名 alias 与 populate_by_name
7. 【进阶】extra="ignore" / "forbid" / "allow"
8. 思考题：如果想禁止多余字段该怎么配置？
