from argon2 import PasswordHasher

from accounts.passwords import hash_password


def test_hashes_with_argon2id() -> None:
    assert hash_password("Passw0rd").startswith("$argon2id$")


def test_hash_verifies_against_the_original_password() -> None:
    assert PasswordHasher().verify(hash_password("Passw0rd"), "Passw0rd")


def test_same_password_hashes_differently_each_time() -> None:
    assert hash_password("Passw0rd") != hash_password("Passw0rd")


def test_uses_the_owasp_parameters() -> None:
    # m=19456 KiB, t=2, p=1. Argon2 encodes them in the hash, so this asserts what a
    # stolen database would actually cost to attack.
    assert "$m=19456,t=2,p=1$" in hash_password("Passw0rd")
