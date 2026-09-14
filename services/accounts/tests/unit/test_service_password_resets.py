from datetime import UTC, datetime, timedelta

import pytest

from accounts import tokens
from accounts.access_tokens import issue
from accounts.errors import (
    ExpiredPasswordResetTokenError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidPasswordResetTokenError,
    PasswordUnchangedError,
)
from accounts.service import (
    authenticate,
    request_password_reset,
    reset_password,
    validate_access_token,
)
from tests.fakes import FailingPasswordResetMailer, FakeMailer
from tests.unit.fakes import FakeAccountsRepository
from tests.unit.helpers import (
    JWT_SECRET,
    LOGIN_TIME,
    active_account,
    sign_up,
)


@pytest.fixture
def repository() -> FakeAccountsRepository:
    return FakeAccountsRepository()


@pytest.fixture
def mailer() -> FakeMailer:
    return FakeMailer()


@pytest.mark.parametrize(
    "identifier",
    ["juan@udesa.edu.ar", "JUAN@UdeSA.edu.AR", "@juan", "@JUAN", "juan"],
)
def test_password_reset_request_accepts_email_or_handle(
    repository: FakeAccountsRepository,
    mailer: FakeMailer,
    identifier: str,
) -> None:
    account = active_account(repository, mailer)

    request_password_reset(repository, mailer, identifier, now=LOGIN_TIME)

    assert [to for to, _ in mailer.password_resets] == [account.email]


def test_password_reset_request_stores_a_ten_minute_digest(
    repository: FakeAccountsRepository,
    mailer: FakeMailer,
) -> None:
    active_account(repository, mailer)

    request_password_reset(repository, mailer, "juan", now=LOGIN_TIME)

    raw_token = mailer.last_password_reset_token
    stored = repository.password_reset_tokens[0]
    assert stored.token_digest == tokens.digest(raw_token)
    assert raw_token not in stored.token_digest
    assert stored.expires_at == LOGIN_TIME + timedelta(minutes=10)


def test_password_reset_request_invalidates_the_token_when_delivery_fails(
    repository: FakeAccountsRepository,
    mailer: FakeMailer,
) -> None:
    active_account(repository, mailer)
    failing_mailer = FailingPasswordResetMailer()

    request_password_reset(repository, failing_mailer, "juan", now=LOGIN_TIME)

    assert repository.password_reset_tokens[-1].used_at is not None


def test_email_and_handle_requests_share_the_three_per_fifteen_minute_limit(
    repository: FakeAccountsRepository,
    mailer: FakeMailer,
) -> None:
    active_account(repository, mailer)

    for identifier in ["juan@udesa.edu.ar", "@juan", "JUAN", "JUAN@UDESA.EDU.AR"]:
        request_password_reset(repository, mailer, identifier, now=LOGIN_TIME)

    live = [token for token in repository.password_reset_tokens if token.used_at is None]
    assert len(mailer.password_resets) == 3
    assert len(repository.password_reset_tokens) == 3
    assert len(live) == 1


@pytest.mark.parametrize("state", ["unknown", "unverified", "suspended", "deleted"])
def test_password_reset_request_stays_silent_for_an_ineligible_account(
    repository: FakeAccountsRepository,
    mailer: FakeMailer,
    state: str,
) -> None:
    if state != "unknown":
        account = sign_up(repository, mailer)
        if state != "unverified":
            account.verified_at = LOGIN_TIME
            setattr(account, f"{state}_at", LOGIN_TIME)

    request_password_reset(repository, mailer, "juan", now=LOGIN_TIME)

    assert mailer.password_resets == []


def test_password_reset_changes_login_password_and_rejects_previous_jwts(
    repository: FakeAccountsRepository,
    mailer: FakeMailer,
) -> None:
    account = active_account(repository, mailer)
    account.failed_login_attempts = 5
    account.locked_until = LOGIN_TIME + timedelta(minutes=15)
    old_access_token = issue(
        account.id,
        JWT_SECRET,
        session_version=account.session_version,
        now=datetime.now(UTC),
    ).token
    request_password_reset(repository, mailer, account.email, now=LOGIN_TIME)

    changed = reset_password(
        repository,
        mailer.last_password_reset_token,
        "NewPassw0rd",
        now=LOGIN_TIME + timedelta(minutes=1),
    )

    with pytest.raises(InvalidCredentialsError):
        authenticate(repository, account.email, "Passw0rd", now=LOGIN_TIME)
    assert authenticate(repository, account.email, "NewPassw0rd", now=LOGIN_TIME) is account
    with pytest.raises(InvalidAccessTokenError):
        validate_access_token(repository, old_access_token, JWT_SECRET)
    assert changed.session_version == 1
    assert changed.failed_login_attempts == 0
    assert changed.locked_until is None


def test_password_reset_rejects_a_token_nobody_issued(
    repository: FakeAccountsRepository,
) -> None:
    with pytest.raises(InvalidPasswordResetTokenError):
        reset_password(repository, tokens.generate(), "NewPassw0rd", now=LOGIN_TIME)


def test_password_reset_token_works_only_once(
    repository: FakeAccountsRepository,
    mailer: FakeMailer,
) -> None:
    active_account(repository, mailer)
    request_password_reset(repository, mailer, "juan", now=LOGIN_TIME)
    raw_token = mailer.last_password_reset_token
    reset_password(repository, raw_token, "NewPassw0rd", now=LOGIN_TIME + timedelta(minutes=1))

    with pytest.raises(InvalidPasswordResetTokenError):
        reset_password(
            repository, raw_token, "AnotherPassw0rd", now=LOGIN_TIME + timedelta(minutes=2)
        )


def test_password_reset_rejects_a_token_at_its_expiration_time(
    repository: FakeAccountsRepository,
    mailer: FakeMailer,
) -> None:
    active_account(repository, mailer)
    request_password_reset(repository, mailer, "juan", now=LOGIN_TIME)

    with pytest.raises(ExpiredPasswordResetTokenError):
        reset_password(
            repository,
            mailer.last_password_reset_token,
            "NewPassw0rd",
            now=LOGIN_TIME + timedelta(minutes=10),
        )


def test_rejecting_the_current_password_keeps_the_reset_link_usable(
    repository: FakeAccountsRepository,
    mailer: FakeMailer,
) -> None:
    active_account(repository, mailer)
    request_password_reset(repository, mailer, "juan", now=LOGIN_TIME)
    raw_token = mailer.last_password_reset_token

    with pytest.raises(PasswordUnchangedError):
        reset_password(repository, raw_token, "Passw0rd", now=LOGIN_TIME + timedelta(minutes=1))

    assert repository.find_password_reset(tokens.digest(raw_token)).used_at is None
    assert (
        reset_password(
            repository,
            raw_token,
            "NewPassw0rd",
            now=LOGIN_TIME + timedelta(minutes=2),
        ).session_version
        == 1
    )
