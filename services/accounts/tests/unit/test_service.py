from datetime import UTC, datetime, timedelta

import pytest

from accounts import tokens
from accounts.access_tokens import issue
from accounts.errors import (
    AccountTemporarilyLockedError,
    EmailAlreadyRegisteredError,
    ExpiredVerificationTokenError,
    HandleTakenError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidVerificationTokenError,
    SuspendedAccountError,
    UnverifiedAccountError,
)
from accounts.models import Account
from accounts.service import (
    authenticate,
    register,
    resend_verification,
    revoke_access_token,
    validate_access_token,
    verify,
)
from tests.fakes import FakeMailer
from tests.unit.fakes import FakeAccountsRepository

LOGIN_TIME = datetime(2030, 1, 2, 3, 4, 5, tzinfo=UTC)
JWT_SECRET = "unit-test-jwt-secret-longer-than-32-bytes"


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


def active_account(repository: FakeAccountsRepository, mailer: FakeMailer) -> Account:
    account = sign_up(repository, mailer)
    account.verified_at = datetime.now(UTC)
    return account


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
