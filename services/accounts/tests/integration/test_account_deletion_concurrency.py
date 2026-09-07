import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from accounts import access_tokens, service
from accounts.config import get_settings
from accounts.db import get_engine
from accounts.errors import (
    AccountTemporarilyLockedError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidPasswordResetTokenError,
    InvalidVerificationTokenError,
)
from accounts.models import Account, PasswordResetToken, VerificationToken
from accounts.repository import AccountsRepository
from tests.integration.test_account_deletion import PASSWORD, add_links, snapshot
from tests.integration.test_account_deletion import account as account
from tests.integration.test_concurrency import in_parallel


def access(account: Account) -> str:
    return access_tokens.issue(account.id, get_settings().jwt_secret).token


def delete(repository: AccountsRepository, token: str, password: str = PASSWORD) -> None:
    service.delete_account(repository, token, password, get_settings().jwt_secret)


@contextmanager
def waiting_on_account(
    account: Account,
    operation: Callable[[AccountsRepository], object],
) -> Iterator[tuple[Session, list[object]]]:
    results: list[object] = []
    started = threading.Event()
    backend: list[int] = []

    def run() -> None:
        try:
            with Session(get_engine()) as worker_session:
                backend.append(worker_session.scalar(text("select pg_backend_pid()")))
                started.set()
                results.append(operation(AccountsRepository(worker_session)))
        except Exception as error:
            results.append(error)

    with Session(get_engine()) as blocker:
        blocker.scalar(select(Account).where(Account.id == account.id).with_for_update())
        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        try:
            assert started.wait(timeout=5)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with Session(get_engine()) as observer:
                    wait = observer.scalar(
                        text("select wait_event_type from pg_stat_activity where pid = :pid"),
                        {"pid": backend[0]},
                    )
                if wait == "Lock":
                    break
                assert not results, f"operation did not wait for the account row: {results}"
                time.sleep(0.01)
            else:
                pytest.fail("operation never waited for the account row lock")
            yield blocker, results
        finally:
            blocker.rollback()
            worker.join(timeout=5)
        assert not worker.is_alive(), "operation did not release its transaction"


def test_parallel_failed_deletions_share_one_budget_across_tokens(account: Account) -> None:
    jwt_tokens = [access(account) for _ in range(8)]
    results = in_parallel(
        lambda repository, index: delete(repository, jwt_tokens[index], "wrong"),
        workers=8,
    )
    assert sum(isinstance(result, InvalidCredentialsError) for result in results) == 5
    assert sum(isinstance(result, AccountTemporarilyLockedError) for result in results) == 3
    stored = snapshot(account.id)
    assert stored["failed_login_attempts"] == 5
    assert stored["locked_until"] > datetime.now(UTC) + timedelta(minutes=14)
    assert stored["deleted_at"] is None


@pytest.mark.parametrize("first", ["login", "deletion"])
def test_login_and_deletion_share_the_fifth_failure_and_lock(account: Account, first: str) -> None:
    token = access(account)
    for _ in range(4):
        with Session(get_engine()) as session:
            repository = AccountsRepository(session)
            with pytest.raises(InvalidCredentialsError):
                if first == "login":
                    service.authenticate(repository, "@delete", "wrong")
                else:
                    delete(repository, token, "wrong")
    with Session(get_engine()) as session:
        repository = AccountsRepository(session)
        with pytest.raises(InvalidCredentialsError):
            if first == "login":
                delete(repository, token, "wrong")
            else:
                service.authenticate(repository, "@delete", "wrong")
        with pytest.raises(AccountTemporarilyLockedError):
            delete(repository, token)
        with pytest.raises(AccountTemporarilyLockedError):
            service.authenticate(repository, "@delete", PASSWORD)
    assert snapshot(account.id)["failed_login_attempts"] == 5


def test_parallel_login_and_deletion_do_not_lose_failures(account: Account) -> None:
    token = access(account)
    results = in_parallel(
        lambda repository, index: (
            service.authenticate(repository, "@delete", "wrong")
            if index % 2
            else delete(repository, token, "wrong")
        ),
        workers=5,
    )
    assert all(isinstance(result, InvalidCredentialsError) for result in results)
    assert snapshot(account.id)["failed_login_attempts"] == 5


def test_confirmation_lock_window_starts_after_row_wait(session: Session, account: Account) -> None:
    account.failed_login_attempts = 4
    session.commit()
    token = access(account)
    with waiting_on_account(account, lambda repository: delete(repository, token, "wrong")) as (
        blocker,
        results,
    ):
        # The operation is known to be blocked, rather than merely scheduled on a thread.
        time.sleep(0.15)
        released_at = datetime.now(UTC)
        blocker.rollback()
    assert len(results) == 1
    assert isinstance(results[0], InvalidCredentialsError)
    assert snapshot(account.id)["locked_until"] >= released_at + timedelta(minutes=15)


@pytest.mark.parametrize("change", ["version", "revoked", "deleted"])
def test_waiting_deletion_revalidates_authority_after_row_lock(
    account: Account, change: str
) -> None:
    token = access(account)
    claims = access_tokens.decode(token, get_settings().jwt_secret)
    with waiting_on_account(account, lambda repository: delete(repository, token)) as (
        blocker,
        results,
    ):
        repository = AccountsRepository(blocker)
        if change == "revoked":
            repository.revoke_access_token(claims.jti, claims.expires_at)
        elif change == "deleted":
            delete(repository, token)
        else:
            locked = blocker.get(Account, account.id)
            locked.session_version += 1
            blocker.commit()
    assert len(results) == 1
    assert isinstance(results[0], InvalidAccessTokenError)
    stored = snapshot(account.id)
    assert stored["failed_login_attempts"] == 0
    assert stored["session_version"] == (0 if change == "revoked" else 1)
    assert (stored["deleted_at"] is not None) == (change == "deleted")


def test_jwt_expiring_while_waiting_cannot_delete(account: Account) -> None:
    issued_at = datetime.now(UTC) - timedelta(hours=1) + timedelta(seconds=3)
    token = access_tokens.issue(account.id, get_settings().jwt_secret, now=issued_at).token
    claims = access_tokens.decode(token, get_settings().jwt_secret)
    with waiting_on_account(account, lambda repository: delete(repository, token)) as (
        blocker,
        results,
    ):
        time.sleep(max(0, (claims.expires_at - datetime.now(UTC)).total_seconds()) + 0.05)
        blocker.rollback()
    assert len(results) == 1
    assert isinstance(results[0], InvalidAccessTokenError)
    assert snapshot(account.id)["deleted_at"] is None


@pytest.mark.parametrize("first", ["delete", "reset"])
def test_password_reset_and_delete_have_one_serial_outcome(
    session: Session,
    account: Account,
    first: str,
) -> None:
    token = access(account)
    _, reset = add_links(session, account.id)
    operation = (
        (lambda repository: service.reset_password(repository, reset, "NewPassw0rd"))
        if first == "delete"
        else (lambda repository: delete(repository, token))
    )
    with waiting_on_account(account, operation) as (blocker, results):
        if first == "delete":
            delete(AccountsRepository(blocker), token)
        else:
            service.reset_password(AccountsRepository(blocker), reset, "NewPassw0rd")
    assert len(results) == 1
    expected = InvalidPasswordResetTokenError if first == "delete" else InvalidAccessTokenError
    assert isinstance(results[0], expected)
    stored = snapshot(account.id)
    assert stored["session_version"] == 1
    assert (stored["deleted_at"] is not None) == (first == "delete")


def test_verification_finishes_before_waiting_deletion(
    session: Session,
    account: Account,
) -> None:
    account.verified_at = None
    verification, _ = add_links(session, account.id)
    token = access(account)
    with waiting_on_account(account, lambda repository: delete(repository, token)) as (
        blocker,
        results,
    ):
        service.verify(AccountsRepository(blocker), verification)
    assert results == [None]
    assert snapshot(account.id)["deleted_at"] is not None


def test_old_verification_waiting_for_deletion_cannot_return_profile(
    session: Session,
    account: Account,
) -> None:
    verification, _ = add_links(session, account.id)
    token = access(account)
    with waiting_on_account(
        account, lambda repository: service.verify(repository, verification)
    ) as (
        blocker,
        results,
    ):
        delete(AccountsRepository(blocker), token)
    assert len(results) == 1
    assert isinstance(results[0], InvalidVerificationTokenError)


@pytest.mark.parametrize("first", ["delete", "issue"])
def test_reset_link_issuance_cannot_survive_deletion(
    session: Session,
    account: Account,
    first: str,
) -> None:
    token = access(account)

    def issue(repository: AccountsRepository) -> object:
        now = datetime.now(UTC)
        return repository.issue_password_reset(
            PasswordResetToken(
                account_id=account.id,
                token_digest="d" * 64,
                expires_at=now + timedelta(minutes=10),
                created_at=now,
            ),
            window=timedelta(minutes=15),
            limit=3,
        )

    operation = issue if first == "delete" else lambda repository: delete(repository, token)
    with waiting_on_account(account, operation) as (blocker, results):
        if first == "delete":
            delete(AccountsRepository(blocker), token)
        else:
            assert issue(AccountsRepository(blocker)) is not None
    assert results == [None]
    with Session(get_engine()) as reader:
        records = reader.scalars(select(PasswordResetToken)).all()
        assert len(records) == (0 if first == "delete" else 1)
        assert all(record.used_at is not None for record in records)


def test_verification_issuer_waiting_on_deleted_row_creates_no_link(
    session: Session,
    account: Account,
) -> None:
    account.verified_at = None
    session.commit()
    now = datetime.now(UTC)
    with waiting_on_account(
        account,
        lambda repository: repository.issue_token(
            VerificationToken(
                account_id=account.id,
                token_digest="e" * 64,
                expires_at=now + timedelta(hours=1),
            )
        ),
    ) as (blocker, results):
        # Repository guard also protects legacy/imported deleted, unverified rows.
        locked = blocker.get(Account, account.id)
        locked.deleted_at = now
        blocker.commit()
    assert results == [None]
    with Session(get_engine()) as reader:
        assert reader.scalars(select(VerificationToken)).all() == []
