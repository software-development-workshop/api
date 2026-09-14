import uuid

import pytest
from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from accounts.db import get_engine

# Valid argon2id, but not the canonical login profile migration 0005 used to require.
# Migration 0010 accepts it (any argon2id hash), so downgrading past 0010 while a row
# like this exists must fail closed rather than silently re-tightening the rule under it.
NONCANONICAL_ARGON2ID_HASH = PasswordHasher(
    memory_cost=32768,
    time_cost=3,
    parallelism=2,
).hash("Passw0rd")


def test_profile_columns_are_nullable_and_have_the_declared_limits() -> None:
    with get_engine().connect() as connection:
        columns = {
            row.column_name: (row.character_maximum_length, row.is_nullable)
            for row in connection.execute(
                text(
                    """
                    SELECT column_name, character_maximum_length, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'accounts'
                      AND column_name IN ('bio', 'display_name')
                    """
                )
            )
        }

    assert columns == {
        "bio": (640, "YES"),
        "display_name": (200, "YES"),
    }


def test_migration_0010_cannot_be_downgraded_once_a_noncanonical_argon2id_hash_exists() -> None:
    config = Config("alembic.ini")
    engine = get_engine()
    account_id = uuid.uuid4()

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO accounts (id, email, handle, password_hash)
                VALUES (:id, :email, :handle, :password_hash)
                """
            ),
            {
                "id": account_id,
                "email": "noncanonical-argon2id-migration@udesa.edu.ar",
                "handle": "@noncanonical",
                "password_hash": NONCANONICAL_ARGON2ID_HASH,
            },
        )

    try:
        with pytest.raises(IntegrityError):
            command.downgrade(config, "0008")
    finally:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM accounts WHERE id = :id"), {"id": account_id})
        command.upgrade(config, "head")
