# task-6: 依赖注入系统 Depends

## 目标
把博客公共逻辑抽到依赖：分页参数、数据库会话（yield）、当前作者（嵌套依赖）。演示 class-based 依赖与 dependency_overrides。

## 涉及文件
- `app/core/__init__.py`
- `app/core/deps.py`（pagination / get_db / get_current_author / get_current_active_author）
- `app/main.py`（路由用 Depends）
- `docs/lessons/06-dependencies.md`
- `tests/test_06_dependencies.py`

## 验收标准
- [ ] pagination 依赖返回 {limit, offset}
- [ ] get_db 用 yield 模拟会话，结束时执行清理
- [ ] get_current_author 解析 token 拿作者（暂时硬编码）
- [ ] get_current_active_author 嵌套依赖前者并校验 is_active
- [ ] POST /posts 必须依赖当前作者
- [ ] dependency_overrides 能替换 db
- [ ] 8 条测试全绿

## 测试点（至少 8 条）
1. `test_pagination_defaults`：依赖默认 limit=10, offset=0
2. `test_pagination_custom`：传入 limit=5&offset=3 生效
3. `test_missing_token_returns_401`：缺 token 创建文章 401
4. `test_yield_db_cleanup_called`：yield 依赖清理被调用（用 spy 验证）
5. `test_dependency_overrides_replace_db`：app.dependency_overrides 替换 get_db
6. `test_class_based_dependency`：class Pagination 复用
7. `test_nested_dependency_chain`：3 层嵌套依赖执行顺序
8. `test_global_dependency_applied`：app 级 dependency_overrides 全局生效

## 实现要点
```python
from fastapi import Depends, HTTPException, Header
from typing import Annotated
from dataclasses import dataclass

@dataclass
class Pagination:
    limit: int = 10
    offset: int = 0

def pagination(limit: int = 10, offset: int = 0) -> Pagination:
    return Pagination(limit=limit, offset=offset)

class PaginationDep:
    def __init__(self, limit: int = 10, offset: int = 0):
        self.limit = limit
        self.offset = offset

def get_db():
    db = {"session_id": "mock", "items": list(POSTS)}
    try:
        yield db
    finally:
        db.clear()  # 清理

def get_current_author(authorization: Annotated[str | None, Header()] = None):
    if not authorization:
        raise HTTPException(401, "Missing token")
    return {"id": 1, "username": "alice", "is_active": True}

def get_current_active_author(author = Depends(get_current_author)):
    if not author["is_active"]:
        raise HTTPException(403, "Inactive author")
    return author

@app.post("/posts", response_model=PostOut, status_code=201)
def create_post(
    payload: PostCreate,
    db = Depends(get_db),
    author = Depends(get_current_active_author),
):
    ...
```
- yield 依赖的 finally 块在请求结束后执行（即使发生异常）
- 测试中 `app.dependency_overrides[get_db] = lambda: iter([{"items":[]}])` 替换

## 教学文档大纲
1. 【新手】为什么需要依赖注入（DRY / 可测）
2. 【新手】Depends 基础用法
3. 【新手】嵌套依赖
4. 【进阶】yield 依赖与资源清理
5. 【进阶】Class-based 依赖
6. 【进阶】全局依赖 vs 路由依赖
7. 【进阶】dependency_overrides 在测试中的应用
8. 思考题：yield 依赖抛异常时，finally 还会执行吗？
