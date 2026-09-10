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
    # The API limits logical text to 160/50 characters. Angle brackets are stored as
    # four-character entities after sanitisation, so the columns retain that headroom.
    op.add_column("accounts", sa.Column("bio", sa.String(640), nullable=True))
    op.add_column("accounts", sa.Column("display_name", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("accounts", "display_name")
    op.drop_column("accounts", "bio")
