from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from accounts import service, tokens
from accounts.db import get_engine
from accounts.errors import InvalidPasswordResetTokenError
from accounts.main import app
from accounts.models import Account, PasswordResetToken
from accounts.passwords import hash_password
from accounts.repository import AccountsRepository
from tests.fakes import FakeMailer
from tests.integration.test_account_deletion import PASSWORD, add_links, snapshot
from tests.integration.test_account_deletion import account as account
from tests.integration.test_account_deletion_concurrency import waiting_on_account


@pytest.mark.parametrize("operation", ["issue", "reset", "consume"])
def test_password_reset_rechecks_suspension_after_waiting_for_account(
    session: Session,
    account: Account,
    operation: str,
) -> None:
    account_id = account.id
    _, reset = add_links(session, account_id)
    before = snapshot(account_id)
    mailer = FakeMailer()
    new_hash = hash_password("NewPassw0rd")

    def run(repository: AccountsRepository) -> object:
        # Hold a stale ORM instance across the row-lock wait.
        preloaded = repository.find_by_identifier("@delete")
        assert preloaded.suspended_at is None
        if operation == "issue":
            return service.request_password_reset(repository, mailer, "@delete")
        if operation == "reset":
            return service.reset_password(repository, reset, "NewPassw0rd")
        return repository.consume_password_reset(
            repository.find_password_reset(tokens.digest(reset)),
            new_hash,
            changed_at=datetime.now(UTC),
        )

    with waiting_on_account(account, run) as (blocker, results):
        locked = blocker.get(Account, account_id)
        locked.suspended_at = datetime.now(UTC)
        blocker.commit()

    assert len(results) == 1
    if operation == "reset":
        assert isinstance(results[0], InvalidPasswordResetTokenError)
    else:
        assert results == [None]
    assert mailer.password_resets == []
    after = snapshot(account_id)
    assert after["suspended_at"] is not None
    for key in before.keys() - {"suspended_at"}:
        assert after[key] == before[key]
    with Session(get_engine()) as reader:
        records = reader.scalars(select(PasswordResetToken)).all()
        assert len(records) == 1
        assert records[0].used_at is None


@pytest.mark.parametrize("password", [PASSWORD, "NewPassw0rd"])
def test_suspended_reset_link_never_exposes_password_state_or_changes_account(
    session: Session,
    account: Account,
    password: str,
) -> None:
    account.suspended_at = datetime.now(UTC)
    _, reset = add_links(session, account.id)
    before = snapshot(account.id)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/password-resets/{reset}",
            json={"new_password": password, "password_confirmation": password},
        )
    assert response.status_code == 400
    assert response.json()["type"].endswith("/invalid-password-reset-token")
    assert snapshot(account.id) == before
    with Session(get_engine()) as reader:
        assert reader.scalars(select(PasswordResetToken)).one().used_at is None
