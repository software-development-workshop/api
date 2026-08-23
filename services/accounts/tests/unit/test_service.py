from datetime import UTC, datetime, timedelta

import pytest

from accounts import tokens
from accounts.errors import (
    EmailAlreadyRegisteredError,
    ExpiredVerificationTokenError,
    HandleTakenError,
    InvalidVerificationTokenError,
)
from accounts.models import Account
from accounts.service import register, resend_verification, verify
from tests.fakes import FakeMailer
from tests.unit.fakes import FakeAccountsRepository


@pytest.fixture
def repository() -> FakeAccountsRepository:
    return FakeAccountsRepository()


@pytest.fixture
def mailer() -> FakeMailer:
    return FakeMailer()


def sign_up(
    repository: FakeAccountsRepository, mailer: FakeMailer, email: str = "juan@udesa.edu.ar"
) -> Account:
    return register(repository, mailer, email, "juan", "Passw0rd")


def test_stores_the_account_with_a_hashed_password(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = sign_up(repository, mailer)

    assert account.password_hash.startswith("$argon2id$")
    assert "Passw0rd" not in account.password_hash


def test_new_account_starts_unverified(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    assert sign_up(repository, mailer).verified_at is None


def test_sends_the_verification_link_to_the_address_that_registered(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = sign_up(repository, mailer)

    assert [to for to, _ in mailer.sent] == [account.email]


def test_stores_the_digest_and_never_the_token(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    sign_up(repository, mailer)

    stored = repository.tokens[0]
    assert stored.token_digest == tokens.digest(mailer.last_token)
    assert mailer.last_token not in stored.token_digest


def test_token_expires_in_twenty_four_hours(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    sign_up(repository, mailer)

    remaining = repository.tokens[0].expires_at - datetime.now(UTC)
    assert timedelta(hours=23, minutes=59) < remaining <= timedelta(hours=24)


@pytest.mark.parametrize("email", ["juan@udesa.edu.ar", "JUAN@UdeSA.edu.AR"])
def test_rejects_an_email_already_registered_whatever_the_casing(
    repository: FakeAccountsRepository, mailer: FakeMailer, email: str
) -> None:
    sign_up(repository, mailer)

    with pytest.raises(EmailAlreadyRegisteredError):
        register(repository, mailer, email, "otro", "Passw0rd")


@pytest.mark.parametrize("handle", ["juan", "JUAN"])
def test_rejects_a_handle_already_taken_whatever_the_casing(
    repository: FakeAccountsRepository, mailer: FakeMailer, handle: str
) -> None:
    sign_up(repository, mailer)

    with pytest.raises(HandleTakenError):
        register(repository, mailer, "nuevo@udesa.edu.ar", handle, "Passw0rd")


def test_verifies_an_account_with_its_token(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    sign_up(repository, mailer)

    account = verify(repository, mailer.last_token)

    assert account.verified_at is not None


def test_a_token_only_works_once(repository: FakeAccountsRepository, mailer: FakeMailer) -> None:
    sign_up(repository, mailer)
    verify(repository, mailer.last_token)

    with pytest.raises(InvalidVerificationTokenError):
        verify(repository, mailer.last_token)


def test_a_link_that_loses_the_race_is_refused_like_a_used_one(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    sign_up(repository, mailer)
    # Stands in for the request that read the token while it was live and reached the
    # database after another one had already spent it.
    repository.consume_token = lambda _: None

    with pytest.raises(InvalidVerificationTokenError):
        verify(repository, mailer.last_token)


def test_rejects_a_token_nobody_issued(repository: FakeAccountsRepository) -> None:
    with pytest.raises(InvalidVerificationTokenError):
        verify(repository, tokens.generate())


def test_rejects_an_expired_token(repository: FakeAccountsRepository, mailer: FakeMailer) -> None:
    sign_up(repository, mailer)
    repository.tokens[0].expires_at = datetime.now(UTC) - timedelta(seconds=1)

    with pytest.raises(ExpiredVerificationTokenError):
        verify(repository, mailer.last_token)


def test_resend_issues_a_new_token_and_burns_the_old_one(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    sign_up(repository, mailer)
    first = mailer.last_token

    resend_verification(repository, mailer, "juan@udesa.edu.ar")

    assert mailer.last_token != first
    with pytest.raises(InvalidVerificationTokenError):
        verify(repository, first)
    assert verify(repository, mailer.last_token).verified_at is not None


def test_resend_stays_silent_for_an_address_nobody_registered(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    resend_verification(repository, mailer, "nadie@udesa.edu.ar")

    assert mailer.sent == []


def test_resend_stays_silent_for_an_already_verified_account(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    sign_up(repository, mailer)
    verify(repository, mailer.last_token)
    sent_so_far = len(mailer.sent)

    resend_verification(repository, mailer, "juan@udesa.edu.ar")

    assert len(mailer.sent) == sent_so_far


def test_resend_does_not_send_when_no_replacement_token_was_issued(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    sign_up(repository, mailer)
    sent_so_far = len(mailer.sent)
    repository.issue_token = lambda _: None  # type: ignore[method-assign]

    resend_verification(repository, mailer, "juan@udesa.edu.ar")

    assert len(mailer.sent) == sent_so_far
