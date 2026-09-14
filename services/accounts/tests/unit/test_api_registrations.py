import pytest
from fastapi.testclient import TestClient

from accounts.api import get_mailer
from accounts.main import app
from accounts.models import Account
from tests.fakes import RefusingMailer
from tests.unit.fakes import FakeAccountsRepository
from tests.unit.helpers import VALID


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


def test_a_send_failure_leaves_the_account_and_says_so(
    client: TestClient, repository: FakeAccountsRepository
) -> None:
    """The account and its token are committed before the send, so the caller keeps both.

    Letting the provider's own exception escape answers 500, which names no way out of a
    state the resend endpoint already knows how to fix.
    """

    app.dependency_overrides[get_mailer] = RefusingMailer

    response = client.post("/api/v1/registrations", json=VALID)

    assert response.status_code == 502
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"].endswith("/verification-email-not-sent")
    assert repository.exists_with_email(VALID["email"])
