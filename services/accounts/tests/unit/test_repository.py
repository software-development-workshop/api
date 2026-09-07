import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from accounts.errors import EmailAlreadyRegisteredError, HandleTakenError
from accounts.models import Account, PasswordResetToken
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


class ScalarResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value


class LookupSession:
    def __init__(self, value: object) -> None:
        self.value = value
        self.statements: list[object] = []
        self.get_calls: list[tuple[object, uuid.UUID]] = []
        self.get_options: dict[str, object] = {}
        self.committed = False
        self.rolled_back = False

    def execute(self, statement: object) -> ScalarResult:
        self.statements.append(statement)
        return ScalarResult(self.value)

    def get(self, model: object, account_id: uuid.UUID, **kwargs: object) -> object:
        self.get_calls.append((model, account_id))
        self.get_options = kwargs
        return self.value

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


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


@pytest.mark.parametrize(
    ("identifier", "column", "canonical"),
    [
        (" JUAN@UdeSA.edu.AR ", "email", "juan@udesa.edu.ar"),
        (" @JUAN ", "handle", "juan"),
        (" JUAN ", "handle", "juan"),
    ],
)
def test_password_reset_identifier_lookup_normalises_email_or_handle(
    identifier: str,
    column: str,
    canonical: str,
) -> None:
    account = Account(email="juan@udesa.edu.ar", handle="juan", password_hash="hash")
    session = LookupSession(account)

    found = AccountsRepository(session).find_by_identifier(identifier)  # type: ignore[arg-type]

    statement = session.statements[0]
    compiled = statement.compile()
    assert found is account
    assert f"lower(accounts.{column})" in str(statement)
    assert canonical in compiled.params.values()


def test_password_reset_lookup_uses_the_token_digest() -> None:
    record = PasswordResetToken(account_id=uuid.uuid4(), token_digest="a" * 64)
    session = LookupSession(record)

    found = AccountsRepository(session).find_password_reset("a" * 64)  # type: ignore[arg-type]

    compiled = session.statements[0].compile()
    assert found is record
    assert "a" * 64 in compiled.params.values()


def test_password_reset_account_lookup_uses_the_account_id() -> None:
    account_id = uuid.uuid4()
    account = Account(id=account_id, email="juan@udesa.edu.ar", handle="juan")
    session = LookupSession(account)

    found = AccountsRepository(session).account_for_password_reset(  # type: ignore[arg-type]
        account_id
    )

    assert found is account
    assert session.get_calls == [(Account, account_id)]
    assert session.get_options == {"with_for_update": True, "populate_existing": True}


def test_deleted_password_reset_lookup_rolls_back_without_returning_identity() -> None:
    account = Account(id=uuid.uuid4(), deleted_at=datetime.now(UTC))
    session = LookupSession(account)
    found = AccountsRepository(session).account_for_password_reset(account.id)
    assert found is None
    assert session.rolled_back


def test_deletion_lookup_locks_and_refreshes_only_the_requested_account() -> None:
    account_id = uuid.uuid4()
    account = Account(id=account_id)
    session = LookupSession(account)
    found = AccountsRepository(session).account_for_deletion(account_id)
    assert found is account
    assert session.get_calls == [(Account, account_id)]
    assert session.get_options == {"with_for_update": True, "populate_existing": True}


def test_confirmed_deletion_spends_only_unused_links_for_its_account() -> None:
    now = datetime.now(UTC)
    account = Account(
        id=uuid.uuid4(),
        session_version=3,
        failed_login_attempts=2,
        locked_until=now,
    )
    session = LookupSession(account)
    AccountsRepository(session).finish_deletion_attempt(account, deleted_at=now)
    assert account.deleted_at == now
    assert account.session_version == 4
    assert account.failed_login_attempts == 0
    assert account.locked_until is None
    assert session.committed
    assert len(session.statements) == 2
    for statement, table in zip(
        session.statements,
        ("verification_tokens", "password_reset_tokens"),
        strict=True,
    ):
        query = str(statement)
        assert f"UPDATE {table}" in query
        assert f"{table}.account_id =" in query
        assert f"{table}.used_at IS NULL" in query
        params = statement.compile().params
        assert account.id in params.values()
        assert params["used_at"] == now


def test_failed_deletion_commits_count_without_spending_links_or_changing_version() -> None:
    account = Account(id=uuid.uuid4(), session_version=2, failed_login_attempts=1)
    session = LookupSession(account)
    AccountsRepository(session).finish_deletion_attempt(account)
    assert session.committed
    assert session.statements == []
    assert account.deleted_at is None
    assert account.session_version == 2
    assert account.failed_login_attempts == 1
