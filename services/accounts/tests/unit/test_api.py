from collections.abc import Iterator
from types import SimpleNamespace

import jwt
import pytest
from fastapi.testclient import TestClient

from accounts import tokens
from accounts.api import get_mailer, get_repository
from accounts.config import get_settings
from accounts.main import app
from accounts.models import Account
from tests.fakes import FakeMailer
from tests.unit.fakes import FakeAccountsRepository

VALID = {"email": "juan@udesa.edu.ar", "handle": "@juan", "password": "Passw0rd"}
JWT_SECRET = "unit-test-jwt-secret-longer-than-32-bytes"


@pytest.fixture
def repository() -> Iterator[FakeAccountsRepository]:
    fake = FakeAccountsRepository()
    app.dependency_overrides[get_repository] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def mailer(repository: FakeAccountsRepository) -> FakeMailer:
    fake = FakeMailer()
    app.dependency_overrides[get_mailer] = lambda: fake
    return fake


@pytest.fixture
def client(mailer: FakeMailer) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(jwt_secret=JWT_SECRET)
    return TestClient(app)


def verify_registered_account(client: TestClient, mailer: FakeMailer) -> None:
    client.post("/api/v1/registrations", json=VALID)
    client.get(f"/api/v1/verifications/{mailer.last_token}")


def test_registers_and_echoes_the_handle_with_its_at_sign(client: TestClient) -> None:
    response = client.post("/api/v1/registrations", json=VALID)

    assert response.status_code == 201
    body = response.json()
    assert body["handle"] == "@juan"
    assert body["email"] == "juan@udesa.edu.ar"
    assert body["verified"] is False


def test_versioned_registration_route_returns_canonical_identity_values(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/registrations",
        json={**VALID, "email": "JUAN@UDESA.EDU.AR", "handle": "@JUAN"},
    )

    assert response.status_code == 201
    assert response.json()["email"] == "juan@udesa.edu.ar"
    assert response.json()["handle"] == "@juan"


def test_never_echoes_the_password_or_its_hash(client: TestClient) -> None:
    body = client.post("/api/v1/registrations", json=VALID).json()

    assert "password" not in body
    assert "password_hash" not in body


def test_reports_every_invalid_field_in_one_response(client: TestClient) -> None:
    response = client.post(
        "/api/v1/registrations",
        json={"email": "not-an-email", "handle": "juan", "password": "short"},
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert {e["field"] for e in response.json()["errors"]} == {"email", "handle", "password"}


@pytest.mark.parametrize("missing", ["email", "handle", "password"])
def test_rejects_a_missing_required_field(client: TestClient, missing: str) -> None:
    body = {k: v for k, v in VALID.items() if k != missing}

    response = client.post("/api/v1/registrations", json=body)

    assert response.status_code == 422
    assert [e["field"] for e in response.json()["errors"]] == [missing]


@pytest.mark.parametrize("empty", ["", "   ", None])
def test_rejects_an_empty_or_null_field(client: TestClient, empty: str | None) -> None:
    assert client.post("/api/v1/registrations", json={**VALID, "handle": empty}).status_code == 422


def test_rejects_an_email_already_registered(
    client: TestClient, repository: FakeAccountsRepository
) -> None:
    repository.accounts.append(Account(email="JUAN@udesa.edu.ar", handle="otro"))

    response = client.post("/api/v1/registrations", json=VALID)

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"].endswith("/email-already-registered")


def test_rejects_a_handle_already_taken(
    client: TestClient, repository: FakeAccountsRepository
) -> None:
    repository.accounts.append(Account(email="otro@udesa.edu.ar", handle="JUAN"))

    response = client.post("/api/v1/registrations", json=VALID)

    assert response.status_code == 409
    assert response.json()["type"].endswith("/handle-taken")


def test_verification_link_activates_the_account(client: TestClient, mailer: FakeMailer) -> None:
    client.post("/api/v1/registrations", json=VALID)

    response = client.get(f"/api/v1/verifications/{mailer.last_token}")

    assert response.status_code == 200
    assert response.json()["verified"] is True


def test_verification_link_stops_working_after_it_is_used(
    client: TestClient, mailer: FakeMailer
) -> None:
    client.post("/api/v1/registrations", json=VALID)
    client.get(f"/api/v1/verifications/{mailer.last_token}")

    response = client.get(f"/api/v1/verifications/{mailer.last_token}")

    assert response.status_code == 400
    assert response.json()["type"].endswith("/invalid-verification-token")


def test_rejects_a_token_nobody_issued(client: TestClient) -> None:
    assert client.get(f"/api/v1/verifications/{tokens.generate()}").status_code == 400


def test_resend_sends_a_fresh_link(client: TestClient, mailer: FakeMailer) -> None:
    client.post("/api/v1/registrations", json=VALID)
    first = mailer.last_token

    response = client.post("/api/v1/verifications/resend", json={"email": VALID["email"]})

    assert response.status_code == 202
    assert mailer.last_token != first
    assert client.get(f"/api/v1/verifications/{mailer.last_token}").status_code == 200


def test_resend_answers_the_same_for_an_unknown_address(
    client: TestClient, mailer: FakeMailer
) -> None:
    # Answering differently would turn this endpoint into a way to find out who has
    # an account.
    known = client.post("/api/v1/verifications/resend", json={"email": VALID["email"]})
    unknown = client.post("/api/v1/verifications/resend", json={"email": "nadie@udesa.edu.ar"})

    assert known.status_code == unknown.status_code == 202
    assert known.content == unknown.content
    assert mailer.sent == []


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
