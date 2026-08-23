import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

ALGORITHM = "HS256"
ISSUER = "udesa-x-accounts"
AUDIENCE = "udesa-x"
ACCESS_TOKEN_TTL = timedelta(hours=1)


@dataclass(frozen=True)
class AccessToken:
    token: str
    expires_in: int


def issue(account_id: uuid.UUID, secret: str, now: datetime | None = None) -> AccessToken:
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + ACCESS_TOKEN_TTL
    token = jwt.encode(
        {
            "sub": str(account_id),
            "iat": issued_at,
            "exp": expires_at,
            "jti": str(uuid.uuid4()),
            "iss": ISSUER,
            "aud": AUDIENCE,
        },
        secret,
        algorithm=ALGORITHM,
    )
    return AccessToken(token=token, expires_in=int(ACCESS_TOKEN_TTL.total_seconds()))
