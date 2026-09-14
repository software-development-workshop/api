import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from accounts import tokens
from accounts.db import get_engine
from accounts.errors import InvalidCredentialsError, InvalidVerificationTokenError
from accounts.models import Account, PasswordResetToken, VerificationToken
from accounts.passwords import hash_password
from accounts.repository import AccountsRepository
from accounts.service import (
    authenticate,
    register,
    request_password_reset,
    resend_verification,
    verify,
)
from tests.fakes import FakeMailer

WORKERS = 2
THREAD_TIMEOUT_SECONDS = 5


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

    threads = [threading.Thread(target=run, args=(index,), daemon=True) for index in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=THREAD_TIMEOUT_SECONDS)
    assert all(not thread.is_alive() for thread in threads), "parallel worker did not finish"
    return results


def sign_up(
    session: Session,
    mailer: FakeMailer,
    email: str = "juan@udesa.edu.ar",
    handle: str = "juan",
) -> AccountsRepository:
    repository = AccountsRepository(session)
    register(repository, mailer, email, handle, "Passw0rd")
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


def test_two_requests_carrying_the_same_password_reset_change_it_once(
    session: Session,
) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(
        Account(
            email="reset@udesa.edu.ar",
            handle="reset",
            password_hash=hash_password("Passw0rd"),
            verified_at=datetime.now(UTC),
        )
    )
    requested_at = datetime.now(UTC)
    digest = "f" * 64
    issued = repository.issue_password_reset(
        PasswordResetToken(
            account_id=stored.id,
            token_digest=digest,
            expires_at=requested_at + timedelta(minutes=10),
            created_at=requested_at,
        ),
        window=timedelta(minutes=15),
        limit=3,
    )
    assert issued is not None
    new_hash = hash_password("NewPassw0rd")

    results = in_parallel(
        lambda concurrent_repository, _: concurrent_repository.consume_password_reset(
            concurrent_repository.find_password_reset(digest),
            new_hash,
            changed_at=requested_at + timedelta(minutes=1),
        )
    )

    assert sum(result is not None for result in results) == 1
    session.expire_all()
    assert session.get(Account, stored.id).session_version == 1


def test_four_simultaneous_password_reset_requests_respect_the_account_limit(
    session: Session,
    mailer: FakeMailer,
) -> None:
    repository = sign_up(session, mailer)
    verify(repository, mailer.last_token)
    requested_at = datetime.now(UTC)
    mailers = [FakeMailer() for _ in range(4)]
    identifiers = ["juan@udesa.edu.ar", "@juan", "JUAN", "JUAN@UDESA.EDU.AR"]

    results = in_parallel(
        lambda concurrent_repository, index: request_password_reset(
            concurrent_repository,
            mailers[index],
            identifiers[index],
            now=requested_at,
        ),
        workers=len(identifiers),
    )

    assert all(result is None for result in results)
    session.expire_all()
    stored = session.execute(select(PasswordResetToken)).scalars().all()
    assert len(stored) == 3
    assert sum(token.used_at is None for token in stored) == 1
    assert sum(len(reset_mailer.password_resets) for reset_mailer in mailers) == 3


def test_four_simultaneous_verification_resends_respect_the_account_limit(
    session: Session,
) -> None:
    # Created directly, not via sign_up/register: registering already issues one
    # verification token, which would consume one of the window's three slots before the
    # concurrent resends even start.
    repository = AccountsRepository(session)
    stored = repository.add(
        Account(
            email="juan@udesa.edu.ar",
            handle="juan",
            password_hash=hash_password("Passw0rd"),
        )
    )
    mailers = [FakeMailer() for _ in range(4)]

    in_parallel(
        lambda concurrent_repository, index: resend_verification(
            concurrent_repository, mailers[index], stored.email
        ),
        workers=4,
    )

    session.expire_all()
    stored_tokens = (
        session.execute(select(VerificationToken).where(VerificationToken.account_id == stored.id))
        .scalars()
        .all()
    )
    live = [token for token in stored_tokens if token.used_at is None]
    assert len(stored_tokens) == 3
    assert len(live) == 1
    assert sum(len(resend_mailer.sent) for resend_mailer in mailers) == 3


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
    identifiers = [
        "juan@udesa.edu.ar",
        "JUAN@UdeSA.edu.AR",
        "@juan",
        "@JUAN",
        "juan",
    ]

    results = in_parallel(
        lambda concurrent_repository, index: authenticate(
            concurrent_repository, identifiers[index], "Wr0ngPassword"
        ),
        workers=len(identifiers),
    )

    assert all(isinstance(result, InvalidCredentialsError) for result in results)
    session.rollback()
    stored = session.execute(
        select(Account).where(Account.email == "juan@udesa.edu.ar")
    ).scalar_one()
    assert stored.failed_login_attempts == 5
    assert stored.locked_until is not None
