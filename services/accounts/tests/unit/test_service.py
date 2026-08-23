import pytest

from accounts.errors import EmailAlreadyRegisteredError, HandleTakenError
from accounts.models import Account
from accounts.service import register
from tests.unit.fakes import FakeAccountsRepository


def test_stores_the_account_with_a_hashed_password() -> None:
    repository = FakeAccountsRepository()

    account = register(repository, "juan@udesa.edu.ar", "juan", "Passw0rd")

    assert account.password_hash.startswith("$argon2id$")
    assert "Passw0rd" not in account.password_hash
    assert repository.accounts == [account]


def test_new_account_starts_unverified() -> None:
    account = register(FakeAccountsRepository(), "juan@udesa.edu.ar", "juan", "Passw0rd")

    assert account.verified_at is None


@pytest.mark.parametrize("email", ["juan@udesa.edu.ar", "JUAN@UdeSA.edu.AR"])
def test_rejects_an_email_already_registered_whatever_the_casing(email: str) -> None:
    repository = FakeAccountsRepository([Account(email="juan@udesa.edu.ar", handle="juan")])

    with pytest.raises(EmailAlreadyRegisteredError):
        register(repository, email, "otro", "Passw0rd")


@pytest.mark.parametrize("handle", ["juan", "JUAN"])
def test_rejects_a_handle_already_taken_whatever_the_casing(handle: str) -> None:
    repository = FakeAccountsRepository([Account(email="otro@udesa.edu.ar", handle="juan")])

    with pytest.raises(HandleTakenError):
        register(repository, "nuevo@udesa.edu.ar", handle, "Passw0rd")
