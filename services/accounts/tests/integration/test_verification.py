import pytest
from sqlalchemy.orm import Session

from accounts.errors import InvalidVerificationTokenError
from accounts.repository import AccountsRepository
from accounts.service import register, resend_verification, verify
from tests.fakes import FakeMailer


def sign_up(session: Session, mailer: FakeMailer) -> AccountsRepository:
    repository = AccountsRepository(session)
    register(repository, mailer, "juan@udesa.edu.ar", "juan", "Passw0rd")
    return repository


def test_the_link_activates_the_account(session: Session, mailer: FakeMailer) -> None:
    repository = sign_up(session, mailer)

    account = verify(repository, mailer.last_token)

    assert account.verified_at is not None


def test_the_link_stops_working_once_used(session: Session, mailer: FakeMailer) -> None:
    repository = sign_up(session, mailer)
    verify(repository, mailer.last_token)

    with pytest.raises(InvalidVerificationTokenError):
        verify(repository, mailer.last_token)


def test_resend_burns_the_previous_link(session: Session, mailer: FakeMailer) -> None:
    repository = sign_up(session, mailer)
    first = mailer.last_token

    resend_verification(repository, mailer, "JUAN@UdeSA.edu.ar")

    with pytest.raises(InvalidVerificationTokenError):
        verify(repository, first)
    assert verify(repository, mailer.last_token).verified_at is not None
