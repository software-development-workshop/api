from datetime import UTC, datetime, timedelta

import pytest

from accounts.access_tokens import issue
from accounts.errors import (
    AccountTemporarilyLockedError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    SuspendedAccountError,
    UnverifiedAccountError,
)
from accounts.service import (
    authenticate,
    revoke_access_token,
    validate_access_token,
)
from tests.fakes import FakeMailer
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
def test_authenticates_by_email_or_handle(
    repository: FakeAccountsRepository, mailer: FakeMailer, identifier: str
) -> None:
    account = active_account(repository, mailer)

    authenticated = authenticate(repository, identifier, "Passw0rd")

    assert authenticated is account


def test_unknown_identity_and_wrong_password_are_indistinguishable(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    active_account(repository, mailer)

    with pytest.raises(InvalidCredentialsError) as unknown:
        authenticate(repository, "nadie@udesa.edu.ar", "Wr0ngPassword")
    with pytest.raises(InvalidCredentialsError) as wrong:
        authenticate(repository, "juan@udesa.edu.ar", "Wr0ngPassword")

    assert unknown.value.detail == wrong.value.detail == "Invalid credentials."


def test_unknown_identity_and_wrong_password_complete_the_same_login_lifecycle(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    active_account(repository, mailer)

    for identifier in ["nadie@udesa.edu.ar", "juan@udesa.edu.ar"]:
        with pytest.raises(InvalidCredentialsError):
            authenticate(repository, identifier, "Wr0ngPassword")

    assert repository.completed_login_attempts == 2


def test_a_malformed_stored_hash_is_an_invalid_credential(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = active_account(repository, mailer)
    account.password_hash = "not-an-argon2-hash"

    with pytest.raises(InvalidCredentialsError, match="Invalid credentials"):
        authenticate(repository, account.email, "Passw0rd", now=LOGIN_TIME)

    assert account.failed_login_attempts == 1


@pytest.mark.parametrize("state", ["unverified", "suspended", "deleted"])
def test_a_wrong_password_never_reveals_account_state(
    repository: FakeAccountsRepository, mailer: FakeMailer, state: str
) -> None:
    account = sign_up(repository, mailer)
    if state != "unverified":
        account.verified_at = datetime.now(UTC)
    if state == "suspended":
        account.suspended_at = datetime.now(UTC)
    if state == "deleted":
        account.deleted_at = datetime.now(UTC)

    with pytest.raises(InvalidCredentialsError, match="Invalid credentials"):
        authenticate(repository, account.email, "Wr0ngPassword")


def test_correct_credentials_for_an_unverified_account_point_to_the_inbox(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = sign_up(repository, mailer)

    with pytest.raises(UnverifiedAccountError, match="Check your inbox"):
        authenticate(repository, account.email, "Passw0rd")


@pytest.mark.parametrize("state", ["suspended", "deleted"])
def test_correct_credentials_for_an_unusable_account_share_one_error(
    repository: FakeAccountsRepository, mailer: FakeMailer, state: str
) -> None:
    account = active_account(repository, mailer)
    setattr(account, f"{state}_at", datetime.now(UTC))

    with pytest.raises(SuspendedAccountError, match="Suspended account"):
        authenticate(repository, account.email, "Passw0rd")


def test_the_fifth_consecutive_wrong_password_locks_for_fifteen_minutes(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = active_account(repository, mailer)

    for _ in range(5):
        with pytest.raises(InvalidCredentialsError, match="Invalid credentials"):
            authenticate(repository, account.email, "Wr0ngPassword", now=LOGIN_TIME)

    assert account.failed_login_attempts == 5
    assert account.locked_until == LOGIN_TIME + timedelta(minutes=15)


def test_correct_password_is_refused_while_the_lock_is_active(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = active_account(repository, mailer)
    account.failed_login_attempts = 5
    account.locked_until = LOGIN_TIME + timedelta(minutes=15)

    with pytest.raises(AccountTemporarilyLockedError, match="temporarily locked"):
        authenticate(repository, account.email, "Passw0rd", now=LOGIN_TIME)


def test_wrong_password_remains_generic_while_the_lock_is_active(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = active_account(repository, mailer)
    account.failed_login_attempts = 5
    account.locked_until = LOGIN_TIME + timedelta(minutes=15)

    with pytest.raises(InvalidCredentialsError, match="Invalid credentials"):
        authenticate(repository, account.email, "Wr0ngPassword", now=LOGIN_TIME)

    assert account.failed_login_attempts == 5
    assert account.locked_until == LOGIN_TIME + timedelta(minutes=15)


def test_an_expired_lock_allows_the_correct_password(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = active_account(repository, mailer)
    account.failed_login_attempts = 5
    account.locked_until = LOGIN_TIME

    authenticated = authenticate(
        repository,
        account.email,
        "Passw0rd",
        now=LOGIN_TIME + timedelta(seconds=1),
    )

    assert authenticated is account
    assert account.failed_login_attempts == 0
    assert account.locked_until is None


def test_a_wrong_password_after_an_expired_lock_starts_a_new_streak(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = active_account(repository, mailer)
    account.failed_login_attempts = 5
    account.locked_until = LOGIN_TIME

    with pytest.raises(InvalidCredentialsError):
        authenticate(
            repository,
            account.email,
            "Wr0ngPassword",
            now=LOGIN_TIME + timedelta(seconds=1),
        )

    assert account.failed_login_attempts == 1
    assert account.locked_until is None


def test_a_correct_password_breaks_the_failure_streak(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = active_account(repository, mailer)
    with pytest.raises(InvalidCredentialsError):
        authenticate(repository, account.email, "Wr0ngPassword", now=LOGIN_TIME)

    authenticate(repository, account.email, "Passw0rd", now=LOGIN_TIME)
    with pytest.raises(InvalidCredentialsError):
        authenticate(repository, account.email, "Wr0ngPassword", now=LOGIN_TIME)

    assert account.failed_login_attempts == 1
    assert account.locked_until is None


def test_logout_revokes_a_valid_access_token_and_validation_rejects_it(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = active_account(repository, mailer)
    token = issue(account.id, JWT_SECRET, now=datetime.now(UTC)).token

    revoke_access_token(repository, token, JWT_SECRET)

    with pytest.raises(InvalidAccessTokenError, match="Invalid access token"):
        validate_access_token(repository, token, JWT_SECRET)


def test_validation_accepts_an_active_access_token(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = active_account(repository, mailer)
    token = issue(account.id, JWT_SECRET, now=datetime.now(UTC)).token

    claims = validate_access_token(repository, token, JWT_SECRET)

    assert claims.subject == account.id


@pytest.mark.parametrize("state", ["suspended", "deleted"])
def test_validation_rejects_an_access_token_for_an_unusable_account(
    repository: FakeAccountsRepository,
    mailer: FakeMailer,
    state: str,
) -> None:
    account = active_account(repository, mailer)
    token = issue(account.id, JWT_SECRET, now=datetime.now(UTC)).token
    setattr(account, f"{state}_at", datetime.now(UTC))

    with pytest.raises(InvalidAccessTokenError, match="Invalid access token"):
        validate_access_token(repository, token, JWT_SECRET)


def test_validation_rejects_an_access_token_from_an_older_session_version(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = active_account(repository, mailer)
    account.session_version = 4
    stale_token = issue(
        account.id,
        JWT_SECRET,
        session_version=3,
        now=datetime.now(UTC),
    ).token

    with pytest.raises(InvalidAccessTokenError, match="Invalid access token"):
        validate_access_token(repository, stale_token, JWT_SECRET)


def test_validation_rejects_a_malformed_access_token(
    repository: FakeAccountsRepository,
) -> None:
    with pytest.raises(InvalidAccessTokenError, match="Invalid access token"):
        validate_access_token(repository, "malformed", JWT_SECRET)


def test_logout_is_idempotent_for_the_same_access_token(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = active_account(repository, mailer)
    token = issue(account.id, JWT_SECRET, now=datetime.now(UTC)).token

    revoke_access_token(repository, token, JWT_SECRET)
    revoke_access_token(repository, token, JWT_SECRET)

    assert len(repository.revoked_access_tokens) == 1
