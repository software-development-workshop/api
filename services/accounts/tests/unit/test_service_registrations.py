from datetime import UTC, datetime, timedelta

import pytest

from accounts import tokens
from accounts.errors import (
    EmailAlreadyRegisteredError,
    HandleTakenError,
)
from accounts.service import (
    register,
)
from tests.fakes import FakeMailer
from tests.unit.fakes import FakeAccountsRepository
from tests.unit.helpers import (
    sign_up,
)


@pytest.fixture
def repository() -> FakeAccountsRepository:
    return FakeAccountsRepository()


@pytest.fixture
def mailer() -> FakeMailer:
    return FakeMailer()


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
