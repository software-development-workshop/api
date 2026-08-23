from argon2 import PasswordHasher

# OWASP Password Storage Cheat Sheet, argon2id: 19 MiB of memory, 2 iterations, 1 degree of
# parallelism. Argon2 encodes its parameters in the hash, so raising these later leaves every
# existing hash verifiable.
_hasher = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)


def hash_password(password: str) -> str:
    return _hasher.hash(password)
