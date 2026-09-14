import pytest

from accounts.errors import (
    InvalidAccessTokenError,
    InvalidProfileError,
)
from accounts.service import (
    update_profile,
)
from tests.fakes import FakeMailer
from tests.unit.fakes import FakeAccountsRepository
from tests.unit.helpers import (
    LOGIN_TIME,
    active_account,
)


@pytest.fixture
def repository() -> FakeAccountsRepository:
    return FakeAccountsRepository()


@pytest.fixture
def mailer() -> FakeMailer:
    return FakeMailer()


def test_updates_and_sanitises_the_authenticated_account_profile(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = active_account(repository, mailer)

    changed = update_profile(
        repository,
        account.id,
        {
            "handle": "@nuevo",
            "bio": "<b>Bio</b><script>alert(1)</script>",
            "display_name": "  Juan  ",
        },
    )

    assert changed is account
    assert account.handle == "nuevo"
    assert account.bio == "Bio"
    assert account.display_name == "Juan"


def test_profile_update_rejects_an_unusable_account(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = active_account(repository, mailer)
    account.deleted_at = LOGIN_TIME

    with pytest.raises(InvalidAccessTokenError, match="Invalid access token"):
        update_profile(repository, account.id, {"bio": "Bio"})


def test_profile_update_rejects_unknown_fields(
    repository: FakeAccountsRepository, mailer: FakeMailer
) -> None:
    account = active_account(repository, mailer)

    with pytest.raises(InvalidProfileError, match="Only handle"):
        update_profile(repository, account.id, {"email": "nuevo@udesa.edu.ar"})
