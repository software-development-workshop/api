import uuid
from datetime import UTC, datetime

import jwt

from accounts.access_tokens import issue

SECRET = "unit-test-jwt-secret-longer-than-32-bytes"
NOW = datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC)


def decode(token: str) -> dict[str, object]:
    return jwt.decode(
        token,
        SECRET,
        algorithms=["HS256"],
        audience="udesa-x",
        issuer="udesa-x-accounts",
        options={"verify_exp": False},
    )


def test_issues_a_one_hour_access_token_for_the_account() -> None:
    account_id = uuid.UUID("d3f0215c-07c1-4e55-873c-90740965713b")

    issued = issue(account_id, SECRET, now=NOW)

    claims = decode(issued.token)
    assert claims["sub"] == str(account_id)
    assert claims["iss"] == "udesa-x-accounts"
    assert claims["aud"] == "udesa-x"
    assert claims["exp"] - claims["iat"] == 3600
    assert issued.expires_in == 3600


def test_every_access_token_has_a_distinct_identifier() -> None:
    account_id = uuid.UUID("d3f0215c-07c1-4e55-873c-90740965713b")

    first = decode(issue(account_id, SECRET, now=NOW).token)
    second = decode(issue(account_id, SECRET, now=NOW).token)

    assert first["jti"] != second["jti"]
