"""Add account access state.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("accounts", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("accounts", "deleted_at")
    op.drop_column("accounts", "suspended_at")
