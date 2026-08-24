import logging
import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_logger = logging.getLogger(__name__)

# OWASP Password Storage Cheat Sheet, argon2id: 19 MiB of memory, 2 iterations, 1 degree of
# parallelism. Argon2 encodes its parameters in the hash, so raising these later leaves every
# existing hash verifiable after a coordinated policy migration.
_hasher = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)
_dummy_hash = _hasher.hash("DummyPassw0rd")
_SUPPORTED_HASH_PATTERN = re.compile(
    r"\$argon2id\$v=19\$m=19456,t=2,p=1\$[A-Za-z0-9+/]{22}\$[A-Za-z0-9+/]{43}"
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def _is_supported_hash(password_hash: str | None) -> bool:
    return (
        password_hash is not None and _SUPPORTED_HASH_PATTERN.fullmatch(password_hash) is not None
    )


def verify_password(password_hash: str | None, candidate: str) -> bool:
    hash_is_usable = _is_supported_hash(password_hash)
    if password_hash is not None and not hash_is_usable:
        _logger.warning("Stored password hash uses an invalid or unsupported format.")
    try:
        matches = _hasher.verify(password_hash if hash_is_usable else _dummy_hash, candidate)
    except VerifyMismatchError:
        return False
    except (InvalidHashError, UnicodeError, VerificationError):
        _logger.warning("Stored password hash is malformed.")
        _perform_dummy_verification(candidate)
        return False
    return hash_is_usable and matches


def _perform_dummy_verification(candidate: str) -> None:
    try:
        _hasher.verify(_dummy_hash, candidate)
    except (InvalidHashError, UnicodeError, VerificationError):
        pass
