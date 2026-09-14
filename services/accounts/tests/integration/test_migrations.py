import uuid

import pytest
from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from accounts.db import get_engine

# Valid argon2id, but not the canonical login profile migration 0005 used to require.
# Migration 0009 accepts it (any argon2id hash), so downgrading past 0009 while a row
# like this exists must fail closed rather than silently re-tightening the rule under it.
NONCANONICAL_ARGON2ID_HASH = PasswordHasher(
    memory_cost=32768,
    time_cost=3,
    parallelism=2,
).hash("Passw0rd")


def test_migration_0009_cannot_be_downgraded_once_a_noncanonical_argon2id_hash_exists() -> None:
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
