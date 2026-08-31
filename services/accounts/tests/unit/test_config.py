import pytest
from pydantic import ValidationError

from accounts.config import Settings

BASE_SETTINGS = {
    "db_host": "db",
    "db_port": 5432,
    "db_name": "accounts",
    "db_user": "accounts",
    "db_password": "accounts",
    "resend_api_key": "re_a_test_key",
    "mail_from": "no-reply@udesax.app",
    "public_base_url": "https://api.udesax.app",
}


def test_rejects_a_jwt_secret_shorter_than_thirty_two_bytes() -> None:
    with pytest.raises(ValidationError):
        Settings(**BASE_SETTINGS, jwt_secret="too-short")


def test_accepts_a_jwt_secret_at_least_thirty_two_bytes_long() -> None:
    settings = Settings(**BASE_SETTINGS, jwt_secret="x" * 32)

    assert settings.jwt_secret == "x" * 32
