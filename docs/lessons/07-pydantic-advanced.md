# 第 7 课 · Pydantic 校验器与自定义类型

> 难度：【进阶】为主，少量【新手】铺垫。
>
> 学完本节，你能用 Pydantic v2 的 `@field_validator` / `@model_validator` / `computed_field` / `Annotated + AfterValidator` 做复杂的字段级与跨字段校验。

---

## 7.1 【新手】为什么要在模型层做校验

接口拿到的数据经常需要"加工"：

| 场景 | 加工 |
|---|---|
| 用户在 title 前后多敲了空格 | 自动 strip |
| 标签数组里有重复 | 去重 |
| 邮箱大小写不一 | 自动 lower |
| 手机号格式非法 | 拒绝 |
| 想自动从 title 生成 URL slug | 派生字段 |

这些**纯加工逻辑**最适合放在模型层，让接口更干净。

---

## 7.2 【新手】@field_validator

针对**单字段**校验：

```python
from pydantic import field_validator

class PostCreate(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return v.strip()
```

v2 必须加 `@classmethod`（v1 不需要）。

---

## 7.3 【进阶】mode="before" vs mode="after"

```python
@field_validator("price", mode="before")
@classmethod
def to_float(cls, v):
    return float(v)  # 在类型转换前执行，可接收任意原始类型

@field_validator("price", mode="after")
@classmethod
def check_positive(cls, v: float) -> float:
    if v <= 0:
        raise ValueError("price must be > 0")
    return v  # 在类型转换后执行，v 已经是 float
```

默认是 `mode="after"`。

---

## 7.4 【进阶】@model_validator 跨字段

```python
from pydantic import model_validator

class PostCreate(BaseModel):
    title: str
    slug: str = ""

    @model_validator(mode="after")
    def generate_slug(self) -> "PostCreate":
        if not self.slug:  # 用户未显式传
            self.slug = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")
        return self
```

`mode="after"` 时 self 已经构造完毕，可访问所有字段。

---

## 7.5 【进阶】computed_field 派生字段

```python
from pydantic import computed_field

class PostCreate(BaseModel):
    content: str

    @computed_field
    @property
    def excerpt(self) -> str:
        return self.content[:50]
```

`computed_field` 让 property 也出现在 `model_dump()` 输出里，但**不接受输入**（用户传 excerpt 会被忽略）。

---

## 7.6 【进阶】Annotated + AfterValidator 自定义类型

```python
from typing import Annotated
from pydantic import AfterValidator
import re

def _validate_phone(v: str) -> str:
    if not re.fullmatch(r"\+?\d{10,15}", v):
        raise ValueError("Invalid phone number")
    return v

PhoneNumber = Annotated[str, AfterValidator(_validate_phone)]

class AuthorCreate(BaseModel):
    phone: PhoneNumber | None = None  # 复用 PhoneNumber 类型
```

好处：**类型可复用**。N 个模型都引用 PhoneNumber，校验规则改一处即可。

---

## 7.7 【进阶】校验器与依赖注入做校验的区别

| 维度 | Pydantic 校验器 | Depends 校验 |
|---|---|---|
| 触发时机 | 请求体解析时 | 路由执行前 |
| 适合做什么 | 字段加工、类型转换、简单规则 | 跨表查询、权限、IO |
| 失败响应 | 422 自动 | 自定义（401/403/...） |
| 可测试性 | 直接构造模型 | 通过 dependency_overrides |

> 经验：能放模型层的校验就放模型层，DI 只负责业务规则。

---

## 7.8 思考题

1. `@field_validator("tags", mode="before")` 收到的 `v` 是什么类型？如果客户端传字符串 `"py,fastapi"`，怎么自动 split？
2. `model_validator(mode="before")` 和 `mode="after"` 各适合做什么？
3. computed_field 在 ORM 模型里能用吗？（提示：依赖 `self.xxx`）

---

## 7.9 本节交付物

| 文件 | 作用 |
|---|---|
| `app/schemas/types.py` | `PhoneNumber = Annotated[str, AfterValidator(...)]` |
| `app/schemas/post.py` | PostCreate 加 strip_title / normalize_tags / generate_slug / excerpt |
| `app/schemas/author.py` | 新增 `AuthorCreate`（email 自动 lower + phone 校验） |
| `app/main.py` | 新增 `POST /authors/preview`（演示 AuthorCreate 校验） |
| `tests/test_07_pydantic.py` | 9 条测试 |
| `docs/lessons/07-pydantic-advanced.md` | 本文 |

---

## 7.10 下一节预告

第 8 课我们引入 **async/await 异步编程**：用 `asyncio.gather` 并发拉取多作者统计，对比同步 vs 异步耗时。
