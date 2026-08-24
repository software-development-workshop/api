import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from accounts.db import get_engine
from accounts.passwords import hash_password

VALID_PASSWORD_HASH = hash_password("Passw0rd")


@pytest.mark.parametrize(
    "password_hash",
    [
        "",
        "\t",
        "\n",
        "\r\n",
        "\u00a0",
        "\u2003",
        "not-an-argon2-hash",
        "é",
        "$argon2id$stub",
        f"{VALID_PASSWORD_HASH}trailing",
        VALID_PASSWORD_HASH.replace("m=19456", "m=999999"),
        VALID_PASSWORD_HASH.replace("t=2", "t=999"),
        VALID_PASSWORD_HASH.replace("p=1", "p=99"),
        VALID_PASSWORD_HASH.replace("m=19456", "m=invalid"),
        VALID_PASSWORD_HASH.replace("$argon2id$", "$argon2i$"),
    ],
)
def test_password_hash_constraint_fails_safe_and_can_be_downgraded(
    password_hash: str,
) -> None:
    config = Config("alembic.ini")
    engine = get_engine()
    account_id = uuid.uuid4()
    email = "invalid-hash-migration@udesa.edu.ar"

    command.downgrade(config, "0004")
    try:
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
                    "email": email,
                    "handle": "@blank_migrate",
                    "password_hash": password_hash,
                },
            )

        with pytest.raises(RuntimeError, match="contains invalid or unsupported password hashes"):
            command.upgrade(config, "0005")
    finally:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM accounts WHERE id = :id"), {"id": account_id})
        command.upgrade(config, "head")

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (id, email, handle, password_hash)
                    VALUES (:id, :email, :handle, :password_hash)
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "email": email,
                    "handle": "@blank_migrate",
                    "password_hash": password_hash,
                },
            )
