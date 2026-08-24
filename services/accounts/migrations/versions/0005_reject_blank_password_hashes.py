"""Require supported Argon2 password hashes.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_CONSTRAINT = "ck_accounts_password_hash_supported"
_HASH_IS_SUPPORTED = (
    "length(password_hash) = 97 AND "
    "password_hash ~ '^[$]argon2id[$]v=19[$]m=19456,t=2,p=1"
    "[$][A-Za-z0-9+/]{22}[$][A-Za-z0-9+/]{43}$'"
)


def upgrade() -> None:
    has_blank_hash = (
        op.get_bind()
        .execute(
            sa.text(
                f"SELECT EXISTS (SELECT 1 FROM accounts WHERE NOT ({_HASH_IS_SUPPORTED}))"  # noqa: S608
            )
        )
        .scalar_one()
    )
    if has_blank_hash:
        raise RuntimeError(
            "accounts contains invalid or unsupported password hashes; "
            "repair or replace those hashes before retrying"
        )
    op.create_check_constraint(
        _CONSTRAINT,
        "accounts",
        _HASH_IS_SUPPORTED,
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "accounts", type_="check")
