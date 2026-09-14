import pytest
from fastapi.testclient import TestClient

from accounts import tokens
from accounts.api import get_mailer
from accounts.main import app
from tests.fakes import FailingPasswordResetMailer, FakeMailer
from tests.unit.fakes import FakeAccountsRepository
from tests.unit.helpers import verify_registered_account


def test_password_reset_request_answers_the_same_for_known_and_unknown_identifiers(
    client: TestClient,
    mailer: FakeMailer,
) -> None:
    verify_registered_account(client, mailer)

    known = client.post("/api/v1/password-resets", json={"identifier": "@juan"})
    unknown = client.post("/api/v1/password-resets", json={"identifier": "nadie"})

    assert known.status_code == unknown.status_code == 202
    assert known.content == unknown.content == b""
    assert len(mailer.password_resets) == 1


def test_password_reset_request_stays_generic_when_email_delivery_fails(
    client: TestClient,
    mailer: FakeMailer,
    repository: FakeAccountsRepository,
) -> None:
    verify_registered_account(client, mailer)
    failing_mailer = FailingPasswordResetMailer()
    app.dependency_overrides[get_mailer] = lambda: failing_mailer

    response = client.post("/api/v1/password-resets", json={"identifier": "juan"})

    assert response.status_code == 202
    assert response.content == b""
    assert repository.password_reset_tokens[-1].used_at is not None


def test_password_reset_completion_returns_no_content(
    client: TestClient,
    mailer: FakeMailer,
) -> None:
    verify_registered_account(client, mailer)
    client.post("/api/v1/password-resets", json={"identifier": "juan"})

    response = client.post(
        f"/api/v1/password-resets/{mailer.last_password_reset_token}",
        json={
            "new_password": "NewPassw0rd",
            "password_confirmation": "NewPassw0rd",
        },
    )

    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.parametrize(
    "body",
    [
        {"new_password": "NewPassw0rd", "password_confirmation": "AnotherPassw0rd"},
        {"new_password": "newpassword1", "password_confirmation": "newpassword1"},
    ],
)
def test_password_reset_completion_validates_confirmation_and_password_policy(
    client: TestClient,
    mailer: FakeMailer,
    body: dict[str, str],
) -> None:
    verify_registered_account(client, mailer)
    client.post("/api/v1/password-resets", json={"identifier": "juan"})

    response = client.post(
        f"/api/v1/password-resets/{mailer.last_password_reset_token}",
        json=body,
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


def test_password_reset_completion_rejects_an_unknown_token(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/password-resets/{tokens.generate()}",
        json={
            "new_password": "NewPassw0rd",
            "password_confirmation": "NewPassw0rd",
        },
    )

    assert response.status_code == 400
    assert response.json()["type"].endswith("/invalid-password-reset-token")


def test_password_reset_completion_rejects_a_used_token(
    client: TestClient,
    mailer: FakeMailer,
) -> None:
    verify_registered_account(client, mailer)
    client.post("/api/v1/password-resets", json={"identifier": "juan"})
    path = f"/api/v1/password-resets/{mailer.last_password_reset_token}"
    first_body = {
        "new_password": "NewPassw0rd",
        "password_confirmation": "NewPassw0rd",
    }
    client.post(path, json=first_body)

    response = client.post(
        path,
        json={
            "new_password": "AnotherPassw0rd",
            "password_confirmation": "AnotherPassw0rd",
        },
    )

    assert response.status_code == 400
    assert response.json()["type"].endswith("/invalid-password-reset-token")


def test_password_reset_completion_rejects_an_expired_token(
    client: TestClient,
    mailer: FakeMailer,
    repository: FakeAccountsRepository,
) -> None:
    verify_registered_account(client, mailer)
    client.post("/api/v1/password-resets", json={"identifier": "juan"})
    repository.password_reset_tokens[0].expires_at = repository.password_reset_tokens[0].created_at

    response = client.post(
        f"/api/v1/password-resets/{mailer.last_password_reset_token}",
        json={
            "new_password": "NewPassw0rd",
            "password_confirmation": "NewPassw0rd",
        },
    )

    assert response.status_code == 410
    assert response.json()["type"].endswith("/expired-password-reset-token")


def test_password_reset_completion_rejects_the_current_password(
    client: TestClient,
    mailer: FakeMailer,
) -> None:
    verify_registered_account(client, mailer)
    client.post("/api/v1/password-resets", json={"identifier": "juan"})

    response = client.post(
        f"/api/v1/password-resets/{mailer.last_password_reset_token}",
        json={"new_password": "Passw0rd", "password_confirmation": "Passw0rd"},
    )

    assert response.status_code == 400
    assert response.json()["type"].endswith("/password-unchanged")
