from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from accounts.api import get_repository
from accounts.main import app
from accounts.models import Account
from tests.unit.fakes import FakeAccountsRepository

VALID = {"email": "juan@udesa.edu.ar", "handle": "@juan", "password": "Passw0rd"}


@pytest.fixture
def repository() -> Iterator[FakeAccountsRepository]:
    fake = FakeAccountsRepository()
    app.dependency_overrides[get_repository] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def client(repository: FakeAccountsRepository) -> TestClient:
    return TestClient(app)


def test_registers_and_echoes_the_handle_with_its_at_sign(client: TestClient) -> None:
    response = client.post("/registrations", json=VALID)

    assert response.status_code == 201
    body = response.json()
    assert body["handle"] == "@juan"
    assert body["email"] == "juan@udesa.edu.ar"
    assert "password" not in body


def test_never_echoes_the_password_hash(client: TestClient) -> None:
    assert "password_hash" not in client.post("/registrations", json=VALID).json()


def test_reports_every_invalid_field_in_one_response(client: TestClient) -> None:
    response = client.post(
        "/registrations", json={"email": "not-an-email", "handle": "juan", "password": "short"}
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    fields = {e["field"] for e in response.json()["errors"]}
    assert fields == {"email", "handle", "password"}


@pytest.mark.parametrize("missing", ["email", "handle", "password"])
def test_rejects_a_missing_required_field(client: TestClient, missing: str) -> None:
    body = {k: v for k, v in VALID.items() if k != missing}

    response = client.post("/registrations", json=body)

    assert response.status_code == 422
    assert [e["field"] for e in response.json()["errors"]] == [missing]


@pytest.mark.parametrize("empty", ["", "   ", None])
def test_rejects_an_empty_or_null_field(client: TestClient, empty: str | None) -> None:
    assert client.post("/registrations", json={**VALID, "handle": empty}).status_code == 422


def test_rejects_an_email_already_registered(
    client: TestClient, repository: FakeAccountsRepository
) -> None:
    repository.accounts.append(Account(email="JUAN@udesa.edu.ar", handle="otro"))

    response = client.post("/registrations", json=VALID)

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"].endswith("/email-already-registered")


def test_rejects_a_handle_already_taken(
    client: TestClient, repository: FakeAccountsRepository
) -> None:
    repository.accounts.append(Account(email="otro@udesa.edu.ar", handle="JUAN"))

    response = client.post("/registrations", json=VALID)

    assert response.status_code == 409
    assert response.json()["type"].endswith("/handle-taken")
