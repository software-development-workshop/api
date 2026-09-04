import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

MAX_POST_LENGTH = 280


class Base(DeclarativeBase):
    pass


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    content: Mapped[str] = mapped_column(String(MAX_POST_LENGTH), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    like_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    repost_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    reply_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(content)) > 0",
            name="ck_posts_content_not_blank",
        ),
        CheckConstraint("like_count >= 0", name="ck_posts_like_count_nonnegative"),
        CheckConstraint("repost_count >= 0", name="ck_posts_repost_count_nonnegative"),
        CheckConstraint("reply_count >= 0", name="ck_posts_reply_count_nonnegative"),
        Index("ix_posts_author_created_at", "author_id", "created_at"),
    )
