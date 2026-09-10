import asyncio
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from accounts import recovery, tokens
from accounts.api import get_mailer, get_repository
from accounts.db import get_engine
from accounts.errors import VerificationEmailNotSentError
from accounts.main import app
from accounts.models import Account, PasswordResetToken, VerificationToken
from accounts.passwords import hash_password
from accounts.repository import AccountsRepository
from accounts.service import request_password_reset, resend_verification
from tests.fakes import FakeMailer


@pytest.mark.parametrize("operation", ["reset", "resend"])
@pytest.mark.parametrize("state", ["suspended_at", "deleted_at", "verified_at"])
def test_token_issuance_rechecks_eligibility_under_the_account_lock(
    session: Session, mailer: FakeMailer, operation: str, state: str
) -> None:
    repository = AccountsRepository(session)
    account = repository.add(
        Account(
            email="juan@udesa.edu.ar",
            handle="juan",
            password_hash=hash_password("Passw0rd"),
            verified_at=datetime.now(UTC) if operation == "reset" else None,
        )
    )
    with Session(get_engine()) as other_session:
        changed = other_session.get(Account, account.id)
        value = None if state == "verified_at" and operation == "reset" else datetime.now(UTC)
        setattr(changed, state, value)
        other_session.commit()

    # The first session still holds the eligible snapshot from before the state change.
    if operation == "reset":
        assert account.verified_at is not None
        request_password_reset(repository, mailer, "@JUAN")
    else:
        assert account.verified_at is None
        resend_verification(repository, mailer, "JUAN@udesa.edu.ar")

    assert mailer.sent == mailer.password_resets == []
    assert session.scalar(select(func.count()).select_from(VerificationToken)) == 0
    assert session.scalar(select(func.count()).select_from(PasswordResetToken)) == 0


@pytest.mark.parametrize("operation", ["reset", "resend"])
@pytest.mark.parametrize("fails", [False, True])
def test_background_delivery_owns_its_database_session_and_commits_before_sending(
    session: Session, monkeypatch: pytest.MonkeyPatch, operation: str, fails: bool
) -> None:
    repository = AccountsRepository(session)
    account = repository.add(
        Account(
            email="juan@udesa.edu.ar",
            handle="juan",
            password_hash=hash_password("Passw0rd"),
            verified_at=datetime.now(UTC) if operation == "reset" else None,
        )
    )
    model = PasswordResetToken if operation == "reset" else VerificationToken
    observed = []

    class Provider(FakeMailer):
        def send_verification(self, to: str, token: str) -> None:
            with Session(get_engine()) as observer:
                stored = observer.scalars(
                    select(model).where(model.token_digest == tokens.digest(token))
                ).one()
                assert stored.account_id == account.id
                assert stored.used_at is None
            observed.append(to)
            if fails:
                raise VerificationEmailNotSentError("provider unavailable")

        send_password_reset = send_verification

    def no_request_repository() -> None:
        raise AssertionError("generic response must not open a request repository")

    monkeypatch.setitem(app.dependency_overrides, get_repository, no_request_repository)
    monkeypatch.setitem(app.dependency_overrides, get_mailer, Provider)
    path = "/api/v1/password-resets" if operation == "reset" else "/api/v1/verifications/resend"
    body = {"identifier": "@JUAN"} if operation == "reset" else {"email": "JUAN@udesa.edu.ar"}
    with TestClient(app) as client:
        response = client.post(path, json=body)

    assert response.status_code == 202
    assert response.content == b""
    assert observed == ["juan@udesa.edu.ar"]
    session.expire_all()
    stored = session.scalars(select(model)).one()
    assert (stored.used_at is not None) == (fails and operation == "reset")


def test_a_late_failed_delivery_does_not_invalidate_a_newer_password_reset(
    session: Session,
) -> None:
    AccountsRepository(session).add(
        Account(
            email="juan@udesa.edu.ar",
            handle="juan",
            password_hash=hash_password("Passw0rd"),
            verified_at=datetime.now(UTC),
        )
    )
    delivered = FakeMailer()

    class LateFailure(FakeMailer):
        def send_password_reset(self, to: str, token: str) -> None:
            asyncio.run(recovery.request_password_reset("@JUAN", delivered))
            raise ConnectionError("the first send failed after the second completed")

    asyncio.run(recovery.request_password_reset("JUAN@udesa.edu.ar", LateFailure()))

    records = list(session.scalars(select(PasswordResetToken)))
    assert len(records) == 2
    live = [record for record in records if record.used_at is None]
    assert len(live) == 1
    assert live[0].token_digest == tokens.digest(delivered.last_password_reset_token)
