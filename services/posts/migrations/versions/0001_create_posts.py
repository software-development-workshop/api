"""Create the posts table.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.String(280), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("like_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("repost_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("reply_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint(
            "char_length(btrim(content)) > 0",
            name="ck_posts_content_not_blank",
        ),
        sa.CheckConstraint("like_count >= 0", name="ck_posts_like_count_nonnegative"),
        sa.CheckConstraint("repost_count >= 0", name="ck_posts_repost_count_nonnegative"),
        sa.CheckConstraint("reply_count >= 0", name="ck_posts_reply_count_nonnegative"),
    )
    op.create_index(
        "ix_posts_author_created_at",
        "posts",
        ["author_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("posts")
