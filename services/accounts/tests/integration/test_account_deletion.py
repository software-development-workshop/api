import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from accounts import access_tokens, service, tokens
from accounts.config import get_settings
from accounts.db import get_engine
from accounts.main import app
from accounts.models import Account, PasswordResetToken, VerificationToken
from accounts.passwords import hash_password
from accounts.repository import AccountsRepository

PASSWORD = "Passw0rd"
PATH = "/api/v1/account-deletions"


@pytest.fixture
def account(session: Session) -> Account:
    return AccountsRepository(session).add(
        Account(
            email="delete@udesa.edu.ar",
            handle="delete",
            password_hash=hash_password(PASSWORD),
            verified_at=datetime.now(UTC),
        )
    )


def bearer(account: Account, **kwargs: object) -> dict[str, str]:
    issued = access_tokens.issue(account.id, get_settings().jwt_secret, **kwargs)
    return {"Authorization": f"Bearer {issued.token}"}


def snapshot(account_id: uuid.UUID) -> dict[str, object]:
    with Session(get_engine()) as reader:
        account = reader.get(Account, account_id)
        assert account is not None
        return {column.name: getattr(account, column.name) for column in Account.__table__.columns}


def add_links(session: Session, account_id: uuid.UUID) -> tuple[str, str]:
    now = datetime.now(UTC)
    verification, reset = tokens.generate(), tokens.generate()
    session.add_all(
        [
            VerificationToken(
                account_id=account_id,
                token_digest=tokens.digest(verification),
                expires_at=now + timedelta(hours=1),
            ),
            PasswordResetToken(
                account_id=account_id,
                token_digest=tokens.digest(reset),
                expires_at=now + timedelta(minutes=10),
            ),
        ]
    )
    session.commit()
    return verification, reset


def test_deletion_preserves_references_and_rejects_every_existing_access_path(
    session: Session,
    account: Account,
) -> None:
    account_id = account.id
    headers = [bearer(account), bearer(account)]
    verification, reset = add_links(session, account_id)
    before = snapshot(account_id)

    with TestClient(app) as client:
        response = client.post(PATH, headers=headers[0], json={"password": PASSWORD})
        assert response.status_code == 204, response.text
        assert response.content == b""
        for header in headers:
            introspection = client.post("/api/v1/sessions/introspect", headers=header)
            assert introspection.status_code == 401
            assert introspection.json()["type"].endswith("/invalid-access-token")
        assert client.post(PATH, headers=headers[1], json={"password": PASSWORD}).status_code == 401
        assert (
            client.post(
                "/api/v1/sessions", json={"identifier": "@delete", "password": PASSWORD}
            ).status_code
            == 403
        )
        assert client.get(f"/api/v1/verifications/{verification}").status_code == 400
        assert (
            client.post(
                f"/api/v1/password-resets/{reset}",
                json={"new_password": "NewPassw0rd", "password_confirmation": "NewPassw0rd"},
            ).status_code
            == 400
        )

    after = snapshot(account_id)
    assert after["deleted_at"] is not None
    assert after["session_version"] == 1
    assert after["failed_login_attempts"] == 0
    assert after["locked_until"] is None
    for key in ("id", "email", "handle", "password_hash", "verified_at", "created_at"):
        assert after[key] == before[key]
    with Session(get_engine()) as reader:
        for model in (VerificationToken, PasswordResetToken):
            records = reader.scalars(select(model).where(model.account_id == account_id)).all()
            assert len(records) == 1
            assert records[0].used_at == after["deleted_at"]


def test_wrong_password_persists_only_shared_security_counters(
    session: Session,
    account: Account,
) -> None:
    account_id = account.id
    headers = [bearer(account), bearer(account)]
    add_links(session, account_id)
    before = snapshot(account_id)

    with TestClient(app) as client:
        for attempt in range(1, 6):
            response = client.post(
                PATH, headers=headers[attempt % 2], json={"password": "Wr0ngPassword"}
            )
            assert response.status_code == 401
            assert response.json()["type"].endswith("/invalid-credentials")
            stored = snapshot(account_id)
            assert stored["failed_login_attempts"] == attempt
            for key in before.keys() - {"failed_login_attempts", "locked_until"}:
                assert stored[key] == before[key]
            if attempt < 5:
                assert stored["locked_until"] is None
        locked = snapshot(account_id)
        assert locked["locked_until"] > datetime.now(UTC) + timedelta(minutes=14)
        for password in (PASSWORD, "Wr0ngPassword"):
            response = client.post(PATH, headers=headers[0], json={"password": password})
            assert response.status_code == 423
            assert response.json()["type"].endswith("/account-temporarily-locked")
            assert snapshot(account_id) == locked

    with Session(get_engine()) as reader:
        for model in (VerificationToken, PasswordResetToken):
            assert reader.scalars(select(model)).one().used_at is None


@pytest.mark.parametrize(
    ("state", "status", "slug"),
    [
        ("missing-token", 401, "invalid-access-token"),
        ("malformed-token", 401, "invalid-access-token"),
        ("expired-token", 401, "invalid-access-token"),
        ("revoked-token", 401, "invalid-access-token"),
        ("missing-account", 401, "invalid-access-token"),
        ("obsolete-token", 401, "invalid-access-token"),
        ("deleted", 401, "invalid-access-token"),
        ("suspended-and-locked", 401, "invalid-access-token"),
        ("unverified-and-locked", 403, "unverified-account"),
        ("locked", 423, "account-temporarily-locked"),
    ],
)
def test_denied_state_preserves_account_and_problem_contract(
    session: Session,
    account: Account,
    state: str,
    status: int,
    slug: str,
) -> None:
    now = datetime.now(UTC)
    headers = bearer(account)
    if state == "missing-token":
        headers = {}
    elif state == "malformed-token":
        headers = {"Authorization": "Bearer malformed"}
    elif state == "expired-token":
        headers = bearer(account, now=now - timedelta(hours=2))
    elif state == "revoked-token":
        claims = access_tokens.decode(headers["Authorization"][7:], get_settings().jwt_secret)
        AccountsRepository(session).revoke_access_token(claims.jti, claims.expires_at)
    elif state == "missing-account":
        token = access_tokens.issue(uuid.uuid4(), get_settings().jwt_secret).token
        headers = {"Authorization": f"Bearer {token}"}
    elif state == "obsolete-token":
        account.session_version = 1
    elif state == "deleted":
        account.deleted_at = now
    elif state == "suspended-and-locked":
        account.suspended_at = now
        account.locked_until = now + timedelta(minutes=15)
    elif state == "unverified-and-locked":
        account.verified_at = None
        account.locked_until = now + timedelta(minutes=15)
    elif state == "locked":
        account.locked_until = now + timedelta(minutes=15)
    session.commit()
    before = snapshot(account.id)

    with TestClient(app) as client:
        response = client.post(PATH, headers=headers, json={"password": PASSWORD})

    assert response.status_code == status, response.text
    problem = response.json()
    assert response.headers["content-type"] == "application/problem+json"
    assert problem["type"] == f"https://udesa-x.dev/problems/{slug}"
    assert problem["status"] == status
    assert problem["title"]
    assert problem["detail"]
    assert snapshot(account.id) == before


@pytest.mark.parametrize("body", [{}, {"password": ""}, {"password": "x" * 129}])
def test_invalid_request_never_consumes_password_attempts(account: Account, body: dict) -> None:
    before = snapshot(account.id)
    with TestClient(app) as client:
        response = client.post(PATH, headers=bearer(account), json=body)
    assert response.status_code == 422
    assert response.json()["type"].endswith("/validation-error")
    assert snapshot(account.id) == before


@pytest.mark.parametrize("kind", ["verification", "password-reset"])
def test_deleted_account_cannot_issue_a_new_link_under_repository_lock(
    session: Session,
    account: Account,
    kind: str,
) -> None:
    account.verified_at = None
    account.deleted_at = datetime.now(UTC)
    session.commit()
    repository = AccountsRepository(session)
    now = datetime.now(UTC)
    if kind == "verification":
        result = repository.issue_token(
            VerificationToken(
                account_id=account.id,
                token_digest="a" * 64,
                expires_at=now + timedelta(hours=1),
            ),
            window=service.VERIFICATION_WINDOW,
            limit=service.VERIFICATION_LIMIT,
        )
        model = VerificationToken
    else:
        result = repository.issue_password_reset(
            PasswordResetToken(
                account_id=account.id,
                token_digest="b" * 64,
                expires_at=now + timedelta(minutes=10),
                created_at=now,
            ),
            window=timedelta(minutes=15),
            limit=3,
        )
        model = PasswordResetToken
    assert result is None
    with Session(get_engine()) as reader:
        assert reader.scalars(select(model)).all() == []


@pytest.mark.parametrize("kind", ["verification", "password-reset", "same-password-reset"])
def test_deleted_account_with_an_unspent_link_never_returns_profile_or_password_state(
    session: Session,
    account: Account,
    kind: str,
) -> None:
    account.verified_at = None
    account.deleted_at = datetime.now(UTC)
    verification, reset = add_links(session, account.id)
    before = snapshot(account.id)
    with TestClient(app) as client:
        if kind == "verification":
            response = client.get(f"/api/v1/verifications/{verification}")
            expected_slug = "invalid-verification-token"
        else:
            password = PASSWORD if kind == "same-password-reset" else "NewPassw0rd"
            response = client.post(
                f"/api/v1/password-resets/{reset}",
                json={
                    "new_password": password,
                    "password_confirmation": password,
                },
            )
            expected_slug = "invalid-password-reset-token"
    assert response.status_code == 400
    assert response.json()["type"].endswith(f"/{expected_slug}")
    assert snapshot(account.id) == before


def test_login_refreshes_shared_failure_count_preloaded_before_a_deletion_attempt(
    session: Session,
    account: Account,
) -> None:
    from accounts.errors import InvalidCredentialsError

    account_id = account.id
    token = bearer(account)["Authorization"][7:]
    with Session(get_engine()) as stale_session:
        preloaded = stale_session.get(Account, account_id)
        assert preloaded.failed_login_attempts == 0
        with Session(get_engine()) as deletion_session:
            with pytest.raises(InvalidCredentialsError):
                service.delete_account(
                    AccountsRepository(deletion_session),
                    token,
                    "wrong",
                    get_settings().jwt_secret,
                )
        with pytest.raises(InvalidCredentialsError):
            service.authenticate(AccountsRepository(stale_session), "@delete", "wrong")
    assert snapshot(account_id)["failed_login_attempts"] == 2
