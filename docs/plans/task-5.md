# task-5: 响应模型 response_model 与状态码

## 目标
为博客接口加响应模型 PostOut（过滤作者密码等敏感字段），并演示 response_model_exclude/include、状态码、自定义 Response。

## 涉及文件
- `app/schemas/post.py`（新增 PostOut、AuthorOut）
- `app/schemas/author.py`（作者对外模型）
- `app/main.py`（GET/POST 加 response_model）
- `docs/lessons/05-response.md`
- `tests/test_05_response.py`

## 验收标准
- [ ] 定义 PostOut（不含 is_deleted、author.password）
- [ ] GET /posts 用 `response_model=list[PostOut]`
- [ ] POST /posts 返回 201
- [ ] response_model_exclude={"is_deleted"} 隐藏内部字段
- [ ] response_model_include={"id", "title"} 白名单
- [ ] 404 用 JSONResponse 返回自定义结构 {error: {...}}
- [ ] 响应能 set_cookie 与 set header
- [ ] 8 条测试全绿

## 测试点（至少 8 条）
1. `test_post_out_excludes_is_deleted`：响应不含 is_deleted
2. `test_post_out_excludes_author_password`：嵌套作者不含 password
3. `test_response_model_exclude`：exclude 生效
4. `test_response_model_include`：include 生效
5. `test_create_post_returns_201`：状态码 201
6. `test_404_custom_json_structure`：404 返回 {error: {code, message}}
7. `test_response_sets_cookie`：响应有 Set-Cookie 头
8. `test_response_custom_header`：响应有 X-Blog-Version 头

## 实现要点
```python
from pydantic import BaseModel, ConfigDict
from fastapi import Response

class AuthorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    # 不含 password、email

class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    content: str
    author: AuthorOut | None = None
    # 不含 is_deleted

@app.get("/posts", response_model=list[PostOut])
def list_posts(): ...

@app.post("/posts", response_model=PostOut, status_code=201)
def create_post(payload: PostCreate, response: Response):
    response.headers["X-Blog-Version"] = "0.5.0"
    response.set_cookie(key="last_create", value=str(payload.title))
    ...

@app.get("/posts/{post_id}")
def get_post(post_id: int):
    p = find_post(post_id)
    if not p:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "POST_NOT_FOUND", "message": "..."}}
        )
    return p
```
- `response_model` 比"在函数里删字段"安全：即使你返回了完整对象，FastAPI 也会按模型过滤
- `model_config = ConfigDict(from_attributes=True)` 允许 ORM 对象直接转响应（task-11 会用到）

## 教学文档大纲
1. 【新手】为什么需要 response_model（不能直接返回 ORM）
2. 【新手】状态码（status_code 参数 / Response.status_code）
3. 【新手】JSONResponse 自定义响应
4. 【进阶】exclude / include / exclude_unset / by_alias
5. 【进阶】嵌套模型的过滤
6. 【进阶】set_cookie / set header
7. 【进阶】response_model 与 response_model_by_alias 的协作
8. 思考题：如果想根据请求动态切换响应模型，应该怎么做？
