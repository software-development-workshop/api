import hashlib
import secrets

TOKEN_BYTES = 32


def generate() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def digest(token: str) -> str:
    """Hash a verification token for storage.

    SHA-256 and not argon2: key stretching exists to slow down dictionary attacks, and there
    is no dictionary against 256 bits of CSPRNG output. Paying argon2's cost here would buy
    nothing and make every verification request expensive.
    """
    return hashlib.sha256(token.encode()).hexdigest()
