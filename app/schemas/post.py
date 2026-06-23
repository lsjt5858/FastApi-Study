from __future__ import annotations

import re

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from app.schemas.author import AuthorOut
from app.schemas.enums import PostStatus


class PostMeta(BaseModel):
    """文章 SEO 元数据（嵌套模型示例）。"""

    seo_title: str | None = None
    seo_description: str | None = None
    cover_color: str = "#ffffff"


def _normalize_tags(tags: list[str]) -> list[str]:
    """去重 + 小写化，保持首次出现顺序。"""
    seen: list[str] = []
    for t in tags:
        tl = t.lower()
        if tl not in seen:
            seen.append(tl)
    return seen


def _title_to_slug(title: str) -> str:
    """把 title 转成 URL 友好的 slug。"""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


class PostCreate(BaseModel):
    """创建文章的请求体模型。

    task-7 强化：
    - title 自动 strip
    - tags 去重 + 小写
    - slug 由 title 自动生成（model_validator）
    - excerpt 由 content 前 50 字自动生成（computed_field）
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    title: str = Field(min_length=1, max_length=200)
    content: str
    tags: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("tags", "keywords"),
    )
    metadata: PostMeta | None = None
    published: bool = False
    status: PostStatus = PostStatus.draft
    slug: str = ""  # 由 model_validator 自动填充

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return v.strip()

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: list[str]) -> list[str]:
        return _normalize_tags(v)

    @model_validator(mode="after")
    def generate_slug(self) -> PostCreate:
        # 仅当用户未显式传 slug 时自动生成
        if not self.slug:
            self.slug = _title_to_slug(self.title)
        return self

    @computed_field
    @property
    def excerpt(self) -> str:
        return self.content[:50]


class PostOut(BaseModel):
    """文章对外响应模型。

    与 PostCreate 的区别：
    - 多了 id / author
    - 没有 is_deleted（即使内部 dict 里有，也被过滤）
    - author 嵌套 AuthorOut，过滤 password 等敏感字段
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    published: bool = False
    status: PostStatus = PostStatus.draft
    tags: list[str] = Field(default_factory=list)
    metadata: PostMeta | None = None
    author: AuthorOut | None = None
    slug: str = ""

    @computed_field
    @property
    def excerpt(self) -> str:
        return self.content[:50]
