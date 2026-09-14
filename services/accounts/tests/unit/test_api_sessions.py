from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from accounts.access_tokens import issue
from tests.fakes import FakeMailer
from tests.unit.fakes import FakeAccountsRepository
from tests.unit.helpers import JWT_SECRET, VALID, verify_registered_account


def test_login_issues_a_one_hour_bearer_token(
    client: TestClient, mailer: FakeMailer, repository: FakeAccountsRepository
) -> None:
    verify_registered_account(client, mailer)

    response = client.post(
        "/api/v1/sessions",
        json={"identifier": "JUAN@UdeSA.edu.AR", "password": "Passw0rd"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    claims = jwt.decode(
        body["access_token"],
        JWT_SECRET,
        algorithms=["HS256"],
        audience="udesa-x",
        issuer="udesa-x-accounts",
    )
    assert claims["sub"] == str(repository.accounts[0].id)


def test_login_issues_the_accounts_current_session_version(
    client: TestClient, mailer: FakeMailer, repository: FakeAccountsRepository
) -> None:
    verify_registered_account(client, mailer)
    repository.accounts[0].session_version = 4

    response = client.post(
        "/api/v1/sessions",
        json={"identifier": VALID["email"], "password": VALID["password"]},
    )

    claims = jwt.decode(
        response.json()["access_token"],
        JWT_SECRET,
        algorithms=["HS256"],
        audience="udesa-x",
        issuer="udesa-x-accounts",
    )
    assert claims["session_version"] == 4


def test_introspection_returns_the_active_account_id(
    client: TestClient,
    mailer: FakeMailer,
    repository: FakeAccountsRepository,
) -> None:
    verify_registered_account(client, mailer)
    login = client.post(
        "/api/v1/sessions",
        json={"identifier": VALID["email"], "password": VALID["password"]},
    )

    response = client.post(
        "/api/v1/sessions/introspect",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json() == {"account_id": str(repository.accounts[0].id)}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer malformed"}])
def test_introspection_rejects_a_missing_or_malformed_bearer_token(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    response = client.post("/api/v1/sessions/introspect", headers=headers)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"].endswith("/invalid-access-token")


def test_introspection_rejects_an_expired_access_token(
    client: TestClient,
    mailer: FakeMailer,
    repository: FakeAccountsRepository,
) -> None:
    verify_registered_account(client, mailer)
    expired = issue(
        repository.accounts[0].id,
        JWT_SECRET,
        now=datetime.now(UTC) - timedelta(hours=2),
    ).token

    response = client.post(
        "/api/v1/sessions/introspect",
        headers={"Authorization": f"Bearer {expired}"},
    )

    assert response.status_code == 401
    assert response.json()["type"].endswith("/invalid-access-token")


def test_introspection_rejects_a_revoked_access_token(
    client: TestClient,
    mailer: FakeMailer,
) -> None:
    verify_registered_account(client, mailer)
    login = client.post(
        "/api/v1/sessions",
        json={"identifier": VALID["email"], "password": VALID["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    client.post("/api/v1/sessions/logout", headers=headers)

    response = client.post("/api/v1/sessions/introspect", headers=headers)

    assert response.status_code == 401
    assert response.json()["type"].endswith("/invalid-access-token")


def test_introspection_rejects_an_access_token_from_an_older_session_version(
    client: TestClient,
    mailer: FakeMailer,
    repository: FakeAccountsRepository,
) -> None:
    verify_registered_account(client, mailer)
    login = client.post(
        "/api/v1/sessions",
        json={"identifier": VALID["email"], "password": VALID["password"]},
    )
    repository.accounts[0].session_version += 1

    response = client.post(
        "/api/v1/sessions/introspect",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 401
    assert response.json()["type"].endswith("/invalid-access-token")


@pytest.mark.parametrize("state", ["suspended", "deleted"])
def test_introspection_rejects_an_access_token_for_an_unusable_account(
    client: TestClient,
    mailer: FakeMailer,
    repository: FakeAccountsRepository,
    state: str,
) -> None:
    verify_registered_account(client, mailer)
    login = client.post(
        "/api/v1/sessions",
        json={"identifier": VALID["email"], "password": VALID["password"]},
    )
    setattr(repository.accounts[0], f"{state}_at", datetime.now(UTC))

    response = client.post(
        "/api/v1/sessions/introspect",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 401
    assert response.json()["type"].endswith("/invalid-access-token")


def test_login_preserves_spaces_that_are_part_of_the_password(
    client: TestClient, mailer: FakeMailer
) -> None:
    password = " Passw0rd "
    client.post("/api/v1/registrations", json={**VALID, "password": password})
    client.get(f"/api/v1/verifications/{mailer.last_token}")

    response = client.post(
        "/api/v1/sessions",
        json={"identifier": VALID["email"], "password": password},
    )

    assert response.status_code == 200


def test_login_does_not_reveal_unknown_identity_or_wrong_password(
    client: TestClient, mailer: FakeMailer
) -> None:
    verify_registered_account(client, mailer)

    unknown = client.post(
        "/api/v1/sessions",
        json={"identifier": "nadie@udesa.edu.ar", "password": "Wr0ngPassword"},
    )
    wrong = client.post(
        "/api/v1/sessions",
        json={"identifier": VALID["email"], "password": "Wr0ngPassword"},
    )

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.headers["content-type"].startswith("application/problem+json")
    assert unknown.json() == wrong.json()
    assert unknown.json()["type"].endswith("/invalid-credentials")


def test_login_points_an_unverified_account_to_the_inbox(
    client: TestClient, mailer: FakeMailer
) -> None:
    client.post("/api/v1/registrations", json=VALID)

    response = client.post(
        "/api/v1/sessions",
        json={"identifier": "@juan", "password": "Passw0rd"},
    )

    assert response.status_code == 403
    assert response.json()["type"].endswith("/unverified-account")
    assert "Check your inbox" in response.json()["detail"]


@pytest.mark.parametrize("state", ["suspended", "deleted"])
def test_login_uses_one_response_for_suspended_and_deleted_accounts(
    client: TestClient,
    mailer: FakeMailer,
    repository: FakeAccountsRepository,
    state: str,
) -> None:
    verify_registered_account(client, mailer)
    setattr(repository.accounts[0], f"{state}_at", repository.accounts[0].verified_at)

    response = client.post(
        "/api/v1/sessions",
        json={"identifier": "juan", "password": "Passw0rd"},
    )

    assert response.status_code == 403
    assert response.json()["type"].endswith("/suspended-account")
    assert response.json()["detail"] == "Suspended account."


def test_five_wrong_passwords_lock_the_account_without_revealing_it_early(
    client: TestClient, mailer: FakeMailer
) -> None:
    verify_registered_account(client, mailer)

    failures = [
        client.post(
            "/api/v1/sessions",
            json={"identifier": VALID["email"], "password": "Wr0ngPassword"},
        )
        for _ in range(5)
    ]

    assert {response.status_code for response in failures} == {401}
    assert {response.json()["type"] for response in failures} == {
        "https://udesa-x.dev/problems/invalid-credentials"
    }
    locked = client.post(
        "/api/v1/sessions",
        json={"identifier": VALID["email"], "password": VALID["password"]},
    )
    assert locked.status_code == 423
    assert locked.json()["type"].endswith("/account-temporarily-locked")


def test_non_ascii_stored_hash_stays_generic_and_counts_toward_lockout(
    client: TestClient,
    mailer: FakeMailer,
    repository: FakeAccountsRepository,
) -> None:
    verify_registered_account(client, mailer)
    account = repository.accounts[0]
    account.password_hash = "é"

    failures = [
        client.post(
            "/api/v1/sessions",
            json={"identifier": VALID["email"], "password": "Wr0ngPassword"},
        )
        for _ in range(5)
    ]

    assert {response.status_code for response in failures} == {401}
    assert {response.json()["type"] for response in failures} == {
        "https://udesa-x.dev/problems/invalid-credentials"
    }
    assert account.failed_login_attempts == 5
    assert account.locked_until is not None


def test_logout_revokes_the_bearer_access_token(
    client: TestClient, mailer: FakeMailer, repository: FakeAccountsRepository
) -> None:
    verify_registered_account(client, mailer)
    login = client.post(
        "/api/v1/sessions",
        json={"identifier": VALID["email"], "password": VALID["password"]},
    )

    response = client.post(
        "/api/v1/sessions/logout",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 204
    assert len(repository.revoked_access_tokens) == 1


def test_logout_is_idempotent_for_a_previously_revoked_token(
    client: TestClient, mailer: FakeMailer, repository: FakeAccountsRepository
) -> None:
    verify_registered_account(client, mailer)
    login = client.post(
        "/api/v1/sessions",
        json={"identifier": VALID["email"], "password": VALID["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.post("/api/v1/sessions/logout", headers=headers).status_code == 204
    repeated = client.post("/api/v1/sessions/logout", headers=headers)

    assert repeated.status_code == 204
    assert len(repository.revoked_access_tokens) == 1


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer malformed"}])
def test_logout_rejects_a_missing_or_invalid_bearer_token(
    client: TestClient, headers: dict[str, str]
) -> None:
    response = client.post("/api/v1/sessions/logout", headers=headers)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"].endswith("/invalid-access-token")
