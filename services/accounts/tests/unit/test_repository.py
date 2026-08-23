import pytest
from sqlalchemy.exc import IntegrityError

from accounts.errors import EmailAlreadyRegisteredError, HandleTakenError
from accounts.models import Account
from accounts.repository import AccountsRepository


class DuplicateDiagnostic:
    def __init__(self, constraint_name: str) -> None:
        self.diag = self
        self.constraint_name = constraint_name


class CommitOnceFailingSession:
    def __init__(self, constraint_name: str) -> None:
        self.constraint_name = constraint_name
        self.rollback_calls = 0
        self._fail_next_commit = True

    def add(self, _: Account) -> None:
        pass

    def commit(self) -> None:
        if self._fail_next_commit:
            self._fail_next_commit = False
            raise IntegrityError(
                "insert account",
                {},
                DuplicateDiagnostic(self.constraint_name),
            )

    def rollback(self) -> None:
        self.rollback_calls += 1

    def refresh(self, _: Account) -> None:
        pass


@pytest.mark.parametrize(
    ("constraint_name", "expected_error", "email", "handle"),
    [
        (
            "ix_accounts_email_lower",
            EmailAlreadyRegisteredError,
            "juan@udesa.edu.ar",
            "otro",
        ),
        (
            "ix_accounts_handle_lower",
            HandleTakenError,
            "otro@udesa.edu.ar",
            "juan",
        ),
    ],
)
def test_duplicate_identity_is_translated_and_rolls_back(
    constraint_name: str,
    expected_error: type[Exception],
    email: str,
    handle: str,
) -> None:
    session = CommitOnceFailingSession(constraint_name)
    repository = AccountsRepository(session)  # type: ignore[arg-type]

    with pytest.raises(expected_error):
        repository.add(Account(email=email, handle=handle, password_hash="hash"))

    assert session.rollback_calls == 1
    saved = repository.add(
        Account(email="nuevo@udesa.edu.ar", handle="nuevo", password_hash="hash")
    )
    assert saved.email == "nuevo@udesa.edu.ar"


def test_unrelated_integrity_error_is_raised_after_rollback() -> None:
    session = CommitOnceFailingSession("unexpected_constraint")
    repository = AccountsRepository(session)  # type: ignore[arg-type]

    with pytest.raises(IntegrityError):
        repository.add(Account(email="juan@udesa.edu.ar", handle="juan", password_hash="hash"))

    assert session.rollback_calls == 1
