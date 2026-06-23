"""task-3 引入：请求体模型 PostCreate / PostMeta。

用 Pydantic v2 风格：
- model_config = ConfigDict(...) 替代 v1 的 class Config
- model_dump() 替代 v1 的 dict()
- Field(min_length=..., max_length=...) 做字段约束
- 通过 AliasChoices 让 tags 同时接受 "tags" 和 "keywords" 两种输入名
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.schemas.enums import PostStatus


class PostMeta(BaseModel):
    """文章 SEO 元数据（嵌套模型示例）。"""

    seo_title: str | None = None
    seo_description: str | None = None
    cover_color: str = "#ffffff"


class PostCreate(BaseModel):
    """创建文章的请求体模型。

    - title 长度约束 1~200
    - tags 同时接受 'tags' 和 'keywords' 两种字段名（AliasChoices）
    - extra='ignore' 让未知字段被静默丢弃
    - status 由后端控制，请求体不暴露（用户不能自己改文章状态）
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
