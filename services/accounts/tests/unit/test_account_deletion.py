from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from accounts import access_tokens, service
from accounts.api import get_repository
from accounts.config import get_settings
from accounts.errors import AccountTemporarilyLockedError, InvalidCredentialsError
from accounts.main import app
from accounts.models import Account, PasswordResetToken, VerificationToken
from accounts.passwords import hash_password
from tests.unit.fakes import FakeAccountsRepository

SECRET = "unit-test-jwt-secret-longer-than-32-bytes"
PASSWORD = " Passw0rd "
PATH = "/api/v1/account-deletions"


@pytest.fixture
def repository() -> FakeAccountsRepository:
    fake = FakeAccountsRepository()
    fake.add(
        Account(
            email="delete@udesa.edu.ar",
            handle="delete",
            password_hash=hash_password(PASSWORD),
            verified_at=datetime.now(UTC),
        )
    )
    return fake


@pytest.fixture
def client(repository: FakeAccountsRepository) -> Iterator[TestClient]:
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(jwt_secret=SECRET)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def token_for(repository: FakeAccountsRepository) -> str:
    return access_tokens.issue(repository.accounts[0].id, SECRET).token


def test_confirmation_uses_exact_password_and_preserves_identity(
    client: TestClient,
    repository: FakeAccountsRepository,
) -> None:
    account = repository.accounts[0]
    identity = (account.id, account.email, account.handle, account.password_hash)
    header = {"Authorization": f"Bearer {token_for(repository)}"}
    response = client.post(PATH, headers=header, json={"password": PASSWORD.strip()})
    assert response.status_code == 401
    assert account.deleted_at is None
    response = client.post(PATH, headers=header, json={"password": PASSWORD})
    assert response.status_code == 204
    assert response.content == b""
    assert account.deleted_at is not None
    assert account.session_version == 1
    assert (account.id, account.email, account.handle, account.password_hash) == identity
    assert account.failed_login_attempts == 0
    assert client.post(PATH, headers=header, json={"password": PASSWORD}).status_code == 401


def test_delete_invalidates_all_pending_links_and_every_session(
    client: TestClient,
    repository: FakeAccountsRepository,
) -> None:
    account = repository.accounts[0]
    old_used = datetime.now(UTC) - timedelta(hours=1)
    repository.tokens = [
        VerificationToken(account_id=account.id, used_at=used) for used in (None, None, old_used)
    ]
    repository.password_reset_tokens = [
        PasswordResetToken(account_id=account.id, used_at=used) for used in (None, None, old_used)
    ]
    headers = [{"Authorization": f"Bearer {token_for(repository)}"} for _ in range(2)]
    assert client.post(PATH, headers=headers[0], json={"password": PASSWORD}).status_code == 204
    for records in (repository.tokens, repository.password_reset_tokens):
        assert [r.used_at for r in records] == [account.deleted_at, account.deleted_at, old_used]
    for header in headers:
        assert client.post("/api/v1/sessions/introspect", headers=header).status_code == 401


@pytest.mark.parametrize(
    ("state", "expected", "slug"),
    [
        ("absent", 401, "invalid-access-token"),
        ("malformed", 401, "invalid-access-token"),
        ("revoked", 401, "invalid-access-token"),
        ("obsolete", 401, "invalid-access-token"),
        ("deleted", 401, "invalid-access-token"),
        ("suspended", 401, "invalid-access-token"),
        ("unverified", 403, "unverified-account"),
        ("locked", 423, "account-temporarily-locked"),
    ],
)
def test_ineligible_requests_do_not_consume_confirmation_attempts(
    client: TestClient,
    repository: FakeAccountsRepository,
    state: str,
    expected: int,
    slug: str,
) -> None:
    account = repository.accounts[0]
    token = token_for(repository)
    if state == "malformed":
        token = "invalid"
    elif state == "revoked":
        claims = access_tokens.decode(token, SECRET)
        repository.revoke_access_token(claims.jti, claims.expires_at)
    elif state == "obsolete":
        account.session_version = 1
    elif state == "deleted":
        account.deleted_at = datetime.now(UTC)
    elif state == "suspended":
        account.suspended_at = datetime.now(UTC)
    elif state == "unverified":
        account.verified_at = None
    if state in ("locked", "unverified", "suspended"):
        account.locked_until = datetime.now(UTC) + timedelta(minutes=15)
    header = {} if state == "absent" else {"Authorization": f"Bearer {token}"}
    response = client.post(PATH, headers=header, json={"password": PASSWORD})
    assert response.status_code == expected
    assert response.json()["type"] == f"https://udesa-x.dev/problems/{slug}"
    assert response.headers["content-type"] == "application/problem+json"
    assert account.failed_login_attempts == 0


def test_fifth_failure_locks_and_locked_attempts_never_check_password(
    repository: FakeAccountsRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = token_for(repository)
    now = datetime.now(UTC)
    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            service.delete_account(repository, token, "wrong", SECRET, now=now)
    account = repository.accounts[0]
    assert account.failed_login_attempts == 5
    assert account.locked_until == now + timedelta(minutes=15)

    def forbidden_hash(*_args: object) -> bool:
        pytest.fail("A locked deletion request must not test the password")

    monkeypatch.setattr(service, "verify_password", forbidden_hash)
    for password in (PASSWORD, "wrong"):
        with pytest.raises(AccountTemporarilyLockedError):
            service.delete_account(repository, token, password, SECRET, now=now)
    assert account.failed_login_attempts == 5
    assert account.locked_until == now + timedelta(minutes=15)


@pytest.mark.parametrize("password", [PASSWORD, "wrong"])
def test_exact_lock_expiry_allows_confirmation_or_starts_a_new_budget(
    repository: FakeAccountsRepository,
    password: str,
) -> None:
    now = datetime.now(UTC)
    account = repository.accounts[0]
    account.failed_login_attempts = 5
    account.locked_until = now
    if password == PASSWORD:
        service.delete_account(repository, token_for(repository), password, SECRET, now=now)
        assert account.deleted_at == now
        assert account.failed_login_attempts == 0
    else:
        with pytest.raises(InvalidCredentialsError):
            service.delete_account(repository, token_for(repository), password, SECRET, now=now)
        assert account.deleted_at is None
        assert account.failed_login_attempts == 1
    assert account.locked_until is None
