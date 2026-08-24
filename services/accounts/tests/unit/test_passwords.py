import pytest
from argon2 import PasswordHasher, extract_parameters
from argon2.exceptions import InvalidHashError

from accounts import passwords
from accounts.passwords import hash_password, verify_password


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


def test_verifies_the_original_password() -> None:
    password_hash = hash_password("Passw0rd")

    assert verify_password(password_hash, "Passw0rd") is True


def test_rejects_a_hash_with_noncanonical_stronger_parameters() -> None:
    password_hash = PasswordHasher(
        memory_cost=32768,
        time_cost=3,
        parallelism=2,
    ).hash("Passw0rd")

    assert verify_password(password_hash, "Passw0rd") is False


def test_every_login_path_uses_the_canonical_argon2_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_hash = hash_password("Passw0rd")
    stronger_hash = PasswordHasher(
        memory_cost=32768,
        time_cost=3,
        parallelism=2,
    ).hash("Passw0rd")
    profiles: list[object] = []

    class SpyHasher:
        def verify(self, password_hash: str, candidate: str) -> bool:
            profiles.append(extract_parameters(password_hash))
            return False

    monkeypatch.setattr(passwords, "_hasher", SpyHasher())

    passwords.verify_password(None, "Passw0rd")
    passwords.verify_password(canonical_hash, "Passw0rd")
    passwords.verify_password(stronger_hash, "Passw0rd")

    assert profiles[0] == profiles[1] == profiles[2]


def test_rejects_a_different_password() -> None:
    password_hash = hash_password("Passw0rd")

    assert verify_password(password_hash, "Wr0ngPassword") is False


def test_rejects_a_password_for_a_missing_account_without_raising() -> None:
    assert verify_password(None, "Passw0rd") is False


def test_rejects_a_password_for_a_malformed_hash_without_raising() -> None:
    assert verify_password("not-an-argon2-hash", "Passw0rd") is False


def test_rejects_a_password_for_a_non_ascii_hash_without_raising() -> None:
    assert verify_password("é", "Passw0rd") is False


@pytest.mark.parametrize("password_hash", ["", "   ", "\t", "\n", "\r\n", "\u00a0", "\u2003"])
def test_empty_hash_never_authenticates_with_the_dummy_password(password_hash: str) -> None:
    assert verify_password(password_hash, "DummyPassw0rd") is False


@pytest.mark.parametrize(
    "verification_error",
    [
        InvalidHashError(),
        UnicodeEncodeError("ascii", "é", 0, 1, "ordinal not in range"),
    ],
)
def test_malformed_hash_still_performs_dummy_argon2_work(
    monkeypatch: pytest.MonkeyPatch, verification_error: Exception
) -> None:
    calls: list[str] = []
    malformed_hash = hash_password("Passw0rd")

    class SpyHasher:
        def verify(self, password_hash: str, candidate: str) -> bool:
            calls.append(password_hash)
            if password_hash == malformed_hash:
                raise verification_error
            return True

    monkeypatch.setattr(passwords, "_hasher", SpyHasher())
    monkeypatch.setattr(passwords, "_dummy_hash", "dummy")

    assert passwords.verify_password(malformed_hash, "Passw0rd") is False
    assert calls == [malformed_hash, "dummy"]


@pytest.mark.parametrize(
    ("current", "unsupported"),
    [
        ("m=19456", "m=01024"),
        ("m=19456", "m=65537"),
        ("m=19456", "m=999999"),
        ("t=2", "t=5"),
        ("p=1", "p=5"),
    ],
)
def test_rejects_unsupported_parameters_before_argon2_verification(
    monkeypatch: pytest.MonkeyPatch,
    current: str,
    unsupported: str,
) -> None:
    unsupported_hash = hash_password("Passw0rd").replace(current, unsupported)
    calls: list[str] = []

    class SpyHasher:
        def verify(self, password_hash: str, candidate: str) -> bool:
            calls.append(password_hash)
            return True

    monkeypatch.setattr(passwords, "_hasher", SpyHasher())
    monkeypatch.setattr(passwords, "_dummy_hash", "dummy")

    assert passwords.verify_password(unsupported_hash, "Passw0rd") is False
    assert calls == ["dummy"]
