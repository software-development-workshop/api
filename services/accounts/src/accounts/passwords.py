import logging

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_logger = logging.getLogger(__name__)

# OWASP Password Storage Cheat Sheet, argon2id: 19 MiB of memory, 2 iterations, 1 degree of
# parallelism. Argon2 encodes its parameters in the hash, so raising these later leaves every
# existing hash verifiable after a coordinated policy migration.
_hasher = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, candidate: str) -> bool:
    if password_hash is None:
        return False
    try:
        return _hasher.verify(password_hash, candidate)
    except VerifyMismatchError:
        return False
    except (InvalidHashError, UnicodeError, VerificationError):
        _logger.warning("Stored password hash is malformed.")
        return False
