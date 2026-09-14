"""Loosen the password hash constraint to only require the argon2id prefix.

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

_OLD_CONSTRAINT = "ck_accounts_password_hash_supported"
_NEW_CONSTRAINT = "ck_accounts_password_hash_is_argon2id"
_HASH_IS_ARGON2ID = "password_hash LIKE '$argon2id$%'"


def upgrade() -> None:
    has_non_argon2id_hash = (
        op.get_bind()
        .execute(
            sa.text(
                f"SELECT EXISTS (SELECT 1 FROM accounts WHERE NOT ({_HASH_IS_ARGON2ID}))"  # noqa: S608
            )
        )
        .scalar_one()
    )
    if has_non_argon2id_hash:
        raise RuntimeError(
            "accounts contains password hashes that are not argon2id; "
            "repair or replace those hashes before retrying"
        )
    op.drop_constraint(_OLD_CONSTRAINT, "accounts", type_="check")
    op.create_check_constraint(
        _NEW_CONSTRAINT,
        "accounts",
        _HASH_IS_ARGON2ID,
    )


def downgrade() -> None:
    op.drop_constraint(_NEW_CONSTRAINT, "accounts", type_="check")
    op.create_check_constraint(
        _OLD_CONSTRAINT,
        "accounts",
        (
            "length(password_hash) = 97 AND "
            "password_hash ~ '^[$]argon2id[$]v=19[$]m=19456,t=2,p=1"
            "[$][A-Za-z0-9+/]{22}[$][A-Za-z0-9+/]{43}$'"
        ),
    )
