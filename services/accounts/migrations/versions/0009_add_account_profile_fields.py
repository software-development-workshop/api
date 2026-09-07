"""Add editable account profile fields.

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("bio", sa.String(160), nullable=True))
    op.add_column("accounts", sa.Column("display_name", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("accounts", "display_name")
    op.drop_column("accounts", "bio")
