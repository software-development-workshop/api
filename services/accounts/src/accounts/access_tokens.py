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


@dataclass(frozen=True)
class AccessTokenClaims:
    subject: uuid.UUID
    jti: uuid.UUID
    expires_at: datetime


class InvalidAccessTokenError(Exception):
    pass


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


def decode(token: str, secret: str) -> AccessTokenClaims:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["sub", "iat", "exp", "jti", "iss", "aud"]},
        )
        subject = _uuid_claim(payload, "sub")
        jti = _uuid_claim(payload, "jti")
        expires_at = _expiry_claim(payload)
    except (jwt.InvalidTokenError, TypeError, ValueError, OverflowError, OSError):
        raise InvalidAccessTokenError from None
    return AccessTokenClaims(subject=subject, jti=jti, expires_at=expires_at)


def _uuid_claim(payload: dict[str, object], name: str) -> uuid.UUID:
    value = payload.get(name)
    if not isinstance(value, str):
        raise InvalidAccessTokenError
    return uuid.UUID(value)


def _expiry_claim(payload: dict[str, object]) -> datetime:
    value = payload.get("exp")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise InvalidAccessTokenError
    return datetime.fromtimestamp(value, UTC)
