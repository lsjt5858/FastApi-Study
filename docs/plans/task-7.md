# task-7: Pydantic 校验器与自定义类型

## 目标
强化博客模型：title 自动 strip、slug 由 title 生成、tags 去重小写、AuthorCreate.email 自动 lower、手机号自定义 Annotated 类型、computed_field 生成 excerpt。

## 涉及文件
- `app/schemas/post.py`（加校验器）
- `app/schemas/author.py`（AuthorCreate + 自定义类型）
- `app/schemas/types.py`（PhoneNumber 自定义类型）
- `docs/lessons/07-pydantic-advanced.md`
- `tests/test_07_pydantic.py`

## 验收标准
- [ ] PostCreate.title 用 @field_validator(mode="before") 自动 strip
- [ ] PostCreate 用 @model_validator(mode="after") 由 title 生成 slug
- [ ] tags @field_validator 去重并小写
- [ ] AuthorCreate.email 字段级 lower
- [ ] PhoneNumber 用 Annotated + AfterValidator 校验
- [ ] computed_field 自动生成 excerpt（content 前 50 字）
- [ ] Optional 字段为 None 时跳过校验
- [ ] 8 条测试全绿

## 测试点（至少 8 条）
1. `test_title_stripped`：title 含前后空格自动去除
2. `test_slug_generated_from_title`：title "Hello World" → slug "hello-world"
3. `test_tags_deduplicated`：["py", "py", "fastapi"] → ["py", "fastapi"]
4. `test_tags_lowercased`：["PY"] → ["py"]
5. `test_email_lowercased`：User@Example.COM → user@example.com
6. `test_invalid_phone_number`：非手机号格式抛 422
7. `test_computed_excerpt`：computed_field 取 content 前 50 字
8. `test_optional_field_skipped`：Optional 字段 None 时不触发校验

## 实现要点
```python
import re
from pydantic import (
    BaseModel, Field, field_validator, model_validator,
    computed_field, AfterValidator, ConfigDict,
)
from typing import Annotated

def _normalize_phone(v: str) -> str:
    if not re.fullmatch(r"\+?\d{10,15}", v):
        raise ValueError("Invalid phone number")
    return v

PhoneNumber = Annotated[str, AfterValidator(_normalize_phone)]

class PostCreate(BaseModel):
    title: str
    content: str
    tags: list[str] = []

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return v.strip()

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: list[str]) -> list[str]:
        seen = []
        for t in v:
            tl = t.lower()
            if tl not in seen:
                seen.append(tl)
        return seen

    @model_validator(mode="after")
    def generate_slug(self):
        self.slug = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")
        return self

    @computed_field
    @property
    def excerpt(self) -> str:
        return self.content[:50]

class AuthorCreate(BaseModel):
    username: str
    email: str
    phone: PhoneNumber | None = None

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower()
```
- Pydantic v2 区分 `@validator`（v1）与 `@field_validator`（v2）
- `mode="before"` 在类型转换前执行，`mode="after"` 在之后
- `model_validator(mode="after")` 可以访问所有字段

## 教学文档大纲
1. 【新手】为什么需要在模型层做校验
2. 【新手】@field_validator 基础
3. 【进阶】mode="before" vs mode="after"
4. 【进阶】@model_validator 联合校验
5. 【进阶】computed_field
6. 【进阶】Annotated 自定义类型（AfterValidator）
7. 【进阶】校验器异常如何自定义消息
8. 思考题：校验器和依赖注入做校验的区别？
