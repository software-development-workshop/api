import hashlib

from accounts import tokens


def test_two_tokens_are_never_the_same() -> None:
    assert len({tokens.generate() for _ in range(100)}) == 100


def test_token_carries_at_least_256_bits() -> None:
    # token_urlsafe encodes 32 bytes in base64url, which is 43 characters.
    assert len(tokens.generate()) >= 43


def test_digest_is_sha256_of_the_token() -> None:
    token = tokens.generate()

    assert tokens.digest(token) == hashlib.sha256(token.encode()).hexdigest()


def test_digest_never_contains_the_token() -> None:
    token = tokens.generate()

    assert token not in tokens.digest(token)
