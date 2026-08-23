import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from accounts.errors import EmailAlreadyRegisteredError, HandleTakenError
from accounts.models import Account, VerificationToken
from accounts.repository import AccountsRepository


def account(email: str = "juan@udesa.edu.ar", handle: str = "juan") -> Account:
    return Account(email=email, handle=handle, password_hash="$argon2id$stub")


def token(account_id: uuid.UUID, digest: str = "a" * 64, hours: int = 24) -> VerificationToken:
    return VerificationToken(
        account_id=account_id,
        token_digest=digest,
        expires_at=datetime.now(UTC) + timedelta(hours=hours),
    )


def test_persists_an_account_and_stamps_created_at(session: Session) -> None:
    stored = AccountsRepository(session).add(account())

    assert stored.id is not None
    assert stored.created_at is not None
    assert stored.verified_at is None


@pytest.mark.parametrize("lookup", ["juan@udesa.edu.ar", "JUAN@UdeSA.EDU.ar"])
def test_finds_an_email_whatever_the_casing(session: Session, lookup: str) -> None:
    repository = AccountsRepository(session)
    repository.add(account(email="Juan@Udesa.edu.ar"))

    assert repository.exists_with_email(lookup)


@pytest.mark.parametrize("lookup", ["juan", "JUAN"])
def test_finds_a_handle_whatever_the_casing(session: Session, lookup: str) -> None:
    repository = AccountsRepository(session)
    repository.add(account(handle="Juan"))

    assert repository.exists_with_handle(lookup)


def test_duplicate_email_is_mapped_and_the_session_is_reusable(session: Session) -> None:
    # AC.7 holds because of this index, not because of the check in the service: two
    # concurrent registrations both pass that check and one of them has to lose here.
    repository = AccountsRepository(session)
    repository.add(account(email="juan@udesa.edu.ar"))

    with pytest.raises(EmailAlreadyRegisteredError):
        repository.add(account(email="JUAN@UDESA.EDU.AR", handle="otro"))

    saved = repository.add(account(email="nuevo@udesa.edu.ar", handle="nuevo"))
    assert saved.email == "nuevo@udesa.edu.ar"


def test_duplicate_handle_is_mapped_and_the_session_is_reusable(session: Session) -> None:
    repository = AccountsRepository(session)
    repository.add(account(handle="juan"))

    with pytest.raises(HandleTakenError):
        repository.add(account(email="otro@udesa.edu.ar", handle="JUAN"))

    saved = repository.add(account(email="nuevo@udesa.edu.ar", handle="nuevo"))
    assert saved.handle == "nuevo"


def test_stores_a_token_and_finds_it_by_its_digest(session: Session) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())

    saved = repository.issue_token(token(stored.id))

    assert repository.find_token("a" * 64).id == saved.id


def test_a_digest_nobody_issued_finds_nothing(session: Session) -> None:
    assert AccountsRepository(session).find_token("b" * 64) is None


def test_finds_an_account_by_email_whatever_the_casing(session: Session) -> None:
    repository = AccountsRepository(session)
    repository.add(account(email="Juan@Udesa.edu.ar"))

    assert repository.find_by_email("JUAN@udesa.EDU.ar") is not None


def test_issuing_burns_every_live_token_of_the_account(session: Session) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())
    repository.issue_token(token(stored.id, digest="c" * 64))
    repository.issue_token(token(stored.id, digest="d" * 64))

    repository.issue_token(token(stored.id, digest="e" * 64))

    assert repository.find_token("c" * 64).used_at is not None
    assert repository.find_token("d" * 64).used_at is not None
    assert repository.find_token("e" * 64).used_at is None


def test_consuming_stamps_the_token_and_the_account(session: Session) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())
    saved = repository.issue_token(token(stored.id))

    verified = repository.consume_token(saved)

    assert verified.verified_at is not None
    assert repository.find_token("a" * 64).used_at is not None


def test_consuming_a_spent_token_answers_nothing(session: Session) -> None:
    repository = AccountsRepository(session)
    stored = repository.add(account())
    saved = repository.issue_token(token(stored.id))
    repository.consume_token(saved)

    assert repository.consume_token(saved) is None
