from datetime import UTC, datetime, timedelta

import pytest

from accounts import tokens
from accounts.errors import (
    ExpiredVerificationTokenError,
    InvalidVerificationTokenError,
)
from accounts.service import (
    resend_verification,
    verify,
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


@pytest.mark.parametrize("state", ["suspended_at", "deleted_at"])
def test_resend_does_not_issue_a_token_for_an_ineligible_unverified_account(
    repository: FakeAccountsRepository, mailer: FakeMailer, state: str
) -> None:
    account = sign_up(repository, mailer)
    setattr(account, state, datetime.now(UTC))
    mailer.sent.clear()
    original_tokens = list(repository.tokens)

    resend_verification(repository, mailer, account.email)

    assert mailer.sent == []
    assert repository.tokens == original_tokens
    assert original_tokens[0].used_at is None


def test_resend_shares_the_three_per_fifteen_minute_limit_with_registration(
    repository: FakeAccountsRepository,
    mailer: FakeMailer,
) -> None:
    sign_up(repository, mailer)  # already used 1 of the window's 3 slots

    for _ in range(4):
        resend_verification(repository, mailer, "juan@udesa.edu.ar")

    live = [token for token in repository.tokens if token.used_at is None]
    assert len(mailer.sent) == 3
    assert len(repository.tokens) == 3
    assert len(live) == 1


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
    repository.issue_token = lambda *args, **kwargs: None  # type: ignore[method-assign]

    resend_verification(repository, mailer, "juan@udesa.edu.ar")

    assert len(mailer.sent) == sent_so_far
