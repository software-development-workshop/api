from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from accounts import tokens
from accounts.api import get_mailer, get_repository
from accounts.main import app
from accounts.models import Account
from tests.fakes import FakeMailer
from tests.unit.fakes import FakeAccountsRepository

VALID = {"email": "juan@udesa.edu.ar", "handle": "@juan", "password": "Passw0rd"}


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
    return TestClient(app)


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
