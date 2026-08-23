from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

# OWASP Password Storage Cheat Sheet, argon2id: 19 MiB of memory, 2 iterations, 1 degree of
# parallelism. Argon2 encodes its parameters in the hash, so raising these later leaves every
# existing hash verifiable.
_hasher = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)
_dummy_hash = _hasher.hash("DummyPassw0rd")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, candidate: str) -> bool:
    try:
        matches = _hasher.verify(password_hash or _dummy_hash, candidate)
    except VerificationError:
        return False
    return password_hash is not None and matches
