from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from accounts import tokens
from accounts.errors import ExpiredVerificationTokenError, InvalidVerificationTokenError
from accounts.models import VerificationToken
from accounts.repository import AccountsRepository
from accounts.service import register, resend_verification, verify
from tests.fakes import FakeMailer


def sign_up(session: Session, mailer: FakeMailer) -> AccountsRepository:
    repository = AccountsRepository(session)
    register(repository, mailer, "juan@udesa.edu.ar", "juan", "Passw0rd")
    return repository


def test_database_stores_the_digest_and_never_the_token(
    session: Session, mailer: FakeMailer
) -> None:
    sign_up(session, mailer)

    stored = session.execute(select(VerificationToken)).scalar_one()
    assert stored.token_digest == tokens.digest(mailer.last_token)
    assert mailer.last_token not in stored.token_digest


def test_the_link_activates_the_account(session: Session, mailer: FakeMailer) -> None:
    repository = sign_up(session, mailer)

    account = verify(repository, mailer.last_token)

    assert account.verified_at is not None


def test_the_link_stops_working_once_used(session: Session, mailer: FakeMailer) -> None:
    repository = sign_up(session, mailer)
    verify(repository, mailer.last_token)

    with pytest.raises(InvalidVerificationTokenError):
        verify(repository, mailer.last_token)


def test_an_expired_link_is_refused(session: Session, mailer: FakeMailer) -> None:
    repository = sign_up(session, mailer)
    stored = session.execute(select(VerificationToken)).scalar_one()
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()

    with pytest.raises(ExpiredVerificationTokenError):
        verify(repository, mailer.last_token)


def test_resend_burns_the_previous_link(session: Session, mailer: FakeMailer) -> None:
    repository = sign_up(session, mailer)
    first = mailer.last_token

    resend_verification(repository, mailer, "JUAN@UdeSA.edu.ar")

    with pytest.raises(InvalidVerificationTokenError):
        verify(repository, first)
    assert verify(repository, mailer.last_token).verified_at is not None
