import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from accounts import tokens
from accounts.db import get_engine
from accounts.errors import InvalidCredentialsError, InvalidVerificationTokenError
from accounts.models import Account, VerificationToken
from accounts.repository import AccountsRepository
from accounts.service import authenticate, register, resend_verification, verify
from tests.fakes import FakeMailer

WORKERS = 2


def in_parallel(
    work: Callable[[AccountsRepository, int], object], workers: int = WORKERS
) -> list[object]:
    """Run `work` on its own session in every worker, all released at the same instant.

    The barrier is what makes these tests worth running: without it the threads queue up
    behind each other and the second one only ever sees the first one's committed result,
    which is the sequential case the other integration tests already cover.
    """
    barrier = threading.Barrier(workers)
    results: list[object] = [None] * workers

    def run(index: int) -> None:
        with Session(get_engine()) as session:
            repository = AccountsRepository(session)
            barrier.wait()
            try:
                results[index] = work(repository, index)
            except Exception as error:
                results[index] = error

    threads = [threading.Thread(target=run, args=(index,)) for index in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def sign_up(session: Session, mailer: FakeMailer) -> AccountsRepository:
    repository = AccountsRepository(session)
    register(repository, mailer, "juan@udesa.edu.ar", "juan", "Passw0rd")
    return repository


def test_two_requests_carrying_the_same_link_verify_the_account_once(
    session: Session, mailer: FakeMailer
) -> None:
    sign_up(session, mailer)
    link = mailer.last_token

    results = in_parallel(lambda repository, _: verify(repository, link))

    refused = [r for r in results if isinstance(r, InvalidVerificationTokenError)]
    accepted = [r for r in results if not isinstance(r, Exception)]
    assert len(accepted) == 1
    assert len(refused) == 1
    assert accepted[0].verified_at is not None


def test_two_simultaneous_resends_leave_exactly_one_usable_link(
    session: Session, mailer: FakeMailer
) -> None:
    sign_up(session, mailer)
    mailers = [FakeMailer() for _ in range(WORKERS)]

    in_parallel(
        lambda repository, index: resend_verification(
            repository, mailers[index], "juan@udesa.edu.ar"
        )
    )

    session.rollback()
    stored = session.execute(select(VerificationToken)).scalars().all()
    live = [token for token in stored if token.used_at is None]
    assert len(stored) == 1 + WORKERS
    assert len(live) == 1

    survivor = next(
        m.last_token for m in mailers if tokens.digest(m.last_token) == live[0].token_digest
    )
    assert verify(AccountsRepository(session), survivor).verified_at is not None


def test_five_simultaneous_wrong_passwords_lock_the_account(
    session: Session, mailer: FakeMailer
) -> None:
    repository = sign_up(session, mailer)
    verify(repository, mailer.last_token)

    results = in_parallel(
        lambda concurrent_repository, _: authenticate(
            concurrent_repository, "juan@udesa.edu.ar", "Wr0ngPassword"
        ),
        workers=5,
    )

    assert all(isinstance(result, InvalidCredentialsError) for result in results)
    session.rollback()
    stored = session.execute(
        select(Account).where(Account.email == "juan@udesa.edu.ar")
    ).scalar_one()
    assert stored.failed_login_attempts == 5
    assert stored.locked_until is not None


def test_lock_ttl_starts_after_waiting_for_the_account_row(
    session: Session, mailer: FakeMailer
) -> None:
    repository = sign_up(session, mailer)
    verify(repository, mailer.last_token)
    for _ in range(4):
        with pytest.raises(InvalidCredentialsError):
            authenticate(repository, "juan@udesa.edu.ar", "Wr0ngPassword")

    with Session(get_engine()) as blocker:
        blocker.execute(
            select(Account).where(Account.email == "juan@udesa.edu.ar").with_for_update()
        ).scalar_one()
        started = threading.Event()
        result: list[object] = []

        def fifth_failure() -> None:
            with Session(get_engine()) as concurrent_session:
                started.set()
                try:
                    authenticate(
                        AccountsRepository(concurrent_session),
                        "juan@udesa.edu.ar",
                        "Wr0ngPassword",
                    )
                except Exception as error:
                    result.append(error)

        worker = threading.Thread(target=fifth_failure)
        worker.start()
        assert started.wait(timeout=1)
        time.sleep(0.75)
        released_at = datetime.now(UTC)
        blocker.rollback()
        worker.join(timeout=2)

    assert not worker.is_alive()
    assert len(result) == 1
    assert isinstance(result[0], InvalidCredentialsError)
    session.rollback()
    stored = session.execute(
        select(Account).where(Account.email == "juan@udesa.edu.ar")
    ).scalar_one()
    assert stored.locked_until is not None
    assert stored.locked_until >= released_at + timedelta(minutes=15, seconds=-0.2)
