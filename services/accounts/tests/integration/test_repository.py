import pytest
from sqlalchemy.orm import Session

from accounts.errors import EmailAlreadyRegisteredError, HandleTakenError
from accounts.models import Account
from accounts.repository import AccountsRepository


def account(email: str = "juan@udesa.edu.ar", handle: str = "juan") -> Account:
    return Account(email=email, handle=handle, password_hash="$argon2id$stub")


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
