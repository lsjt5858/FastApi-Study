"""task-11：ORM models。Author / Post 两表，一对多。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Author(Base):
    """博客作者。"""

    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(200))

    if TYPE_CHECKING:
        posts: list[Post]
    else:
        posts: Mapped[list[Post]] = relationship(
            back_populates="author", cascade="all, delete-orphan"
        )


class Post(Base):
    """博客文章。title 唯一约束（用于演示 IntegrityError -> 409）。"""

    __tablename__ = "posts_db"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    content: Mapped[str] = mapped_column(Text)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("authors.id"), nullable=True)

    if TYPE_CHECKING:
        author: Author | None
    else:
        author: Mapped[Author | None] = relationship(back_populates="posts")
