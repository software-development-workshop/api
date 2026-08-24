from datetime import UTC, datetime, timedelta
from typing import Protocol

from accounts import tokens
from accounts.errors import (
    AccountTemporarilyLockedError,
    EmailAlreadyRegisteredError,
    ExpiredVerificationTokenError,
    HandleTakenError,
    InvalidCredentialsError,
    InvalidVerificationTokenError,
    SuspendedAccountError,
    UnverifiedAccountError,
)
from accounts.models import Account, VerificationToken
from accounts.passwords import hash_password, verify_password
from accounts.repository import AccountsRepository

VERIFICATION_TTL = timedelta(hours=24)
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_TTL = timedelta(minutes=15)


class Mailer(Protocol):
    def send_verification(self, to: str, token: str) -> None: ...


def authenticate(
    repository: AccountsRepository,
    identifier: str,
    password: str,
    now: datetime | None = None,
) -> Account:
    account = repository.find_for_login(identifier)
    password_hash = account.password_hash if account is not None else None
    password_matches = verify_password(password_hash, password)
    attempted_at = now or datetime.now(UTC)
    if account is None:
        repository.finish_login_attempt(None)
        raise InvalidCredentialsError("Invalid credentials.")

    lock_is_active = account.locked_until is not None and account.locked_until > attempted_at
    if not password_matches:
        if not lock_is_active:
            if account.locked_until is not None:
                account.failed_login_attempts = 0
                account.locked_until = None
            account.failed_login_attempts += 1
            if account.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
                account.locked_until = attempted_at + LOGIN_LOCK_TTL
        repository.finish_login_attempt(account)
        raise InvalidCredentialsError("Invalid credentials.")
    if lock_is_active:
        repository.finish_login_attempt(account)
        raise AccountTemporarilyLockedError("Account temporarily locked. Try again later.")

    account.failed_login_attempts = 0
    account.locked_until = None
    if account.suspended_at is not None or account.deleted_at is not None:
        repository.finish_login_attempt(account)
        raise SuspendedAccountError("Suspended account.")
    if account.verified_at is None:
        repository.finish_login_attempt(account)
        raise UnverifiedAccountError("Account not verified. Check your inbox.")

    repository.finish_login_attempt(account)
    return account


def register(
    repository: AccountsRepository,
    mailer: Mailer,
    email: str,
    handle: str,
    password: str,
) -> Account:
    """Create an unverified account and send its verification link.

    The uniqueness checks here are for the error message, not for correctness: the unique
    indexes decide. Two simultaneous registrations of the same email both pass this check
    and one of them loses at commit.
    """
    if repository.exists_with_email(email):
        raise EmailAlreadyRegisteredError("That email is already registered.")
    if repository.exists_with_handle(handle):
        raise HandleTakenError("That handle is already taken.")

    account = repository.add(
        Account(email=email, handle=handle, password_hash=hash_password(password))
    )
    _issue_verification(repository, mailer, account)
    return account


def verify(repository: AccountsRepository, token: str) -> Account:
    """Activate the account behind a link, spending the link in the process.

    The read decides which error the caller gets; the repository decides whether the link is
    still there to spend. A link that loses that race is indistinguishable from one that was
    already used, and gets the same answer.
    """
    record = repository.find_token(tokens.digest(token))
    if record is None or record.used_at is not None:
        raise InvalidVerificationTokenError("That verification link is not valid.")
    if record.expires_at <= datetime.now(UTC):
        raise ExpiredVerificationTokenError(
            "That verification link expired. Ask for a new one from the login screen."
        )

    account = repository.consume_token(record)
    if account is None:
        raise InvalidVerificationTokenError("That verification link is not valid.")
    return account


def resend_verification(repository: AccountsRepository, mailer: Mailer, email: str) -> None:
    """Issue a fresh link, silently doing nothing when there is nobody to send it to.

    The caller always gets the same answer. Reporting that an address is unknown would turn
    this endpoint into a way to find out who has an account.
    """
    account = repository.find_by_email(email)
    if account is None or account.verified_at is not None:
        return
    _issue_verification(repository, mailer, account)


def _issue_verification(repository: AccountsRepository, mailer: Mailer, account: Account) -> None:
    token = tokens.generate()
    repository.issue_token(
        VerificationToken(
            account_id=account.id,
            token_digest=tokens.digest(token),
            expires_at=datetime.now(UTC) + VERIFICATION_TTL,
        )
    )
    # Sent only once the replacement is committed, so no link reaches an inbox before it works.
    mailer.send_verification(account.email, token)
