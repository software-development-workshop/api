import pytest
from fastapi.testclient import TestClient

from accounts.models import Account
from tests.fakes import FakeMailer
from tests.unit.fakes import FakeAccountsRepository
from tests.unit.helpers import VALID, verify_registered_account


def authenticated_headers(client: TestClient, mailer: FakeMailer) -> dict[str, str]:
    verify_registered_account(client, mailer)
    response = client.post(
        "/api/v1/sessions",
        json={"identifier": VALID["email"], "password": VALID["password"]},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_profile_update_changes_editable_fields_and_keeps_email_immutable(
    client: TestClient,
    mailer: FakeMailer,
    repository: FakeAccountsRepository,
) -> None:
    headers = authenticated_headers(client, mailer)

    response = client.patch(
        "/api/v1/accounts/me",
        headers=headers,
        json={
            "handle": "@nuevo",
            "bio": "I build useful things.",
            "display_name": "Juan Pérez",
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == VALID["email"]
    assert response.json()["handle"] == "@nuevo"
    assert response.json()["bio"] == "I build useful things."
    assert response.json()["display_name"] == "Juan Pérez"
    assert repository.accounts[0].email == VALID["email"]


def test_profile_update_removes_html_and_script_markup(
    client: TestClient, mailer: FakeMailer
) -> None:
    headers = authenticated_headers(client, mailer)

    response = client.patch(
        "/api/v1/accounts/me",
        headers=headers,
        json={
            "bio": "<b>Bio</b><script>alert(1)</script>",
            "display_name": " <i>Juan</i> ",
        },
    )

    assert response.status_code == 200
    assert response.json()["bio"] == "Bio"
    assert response.json()["display_name"] == "Juan"
    assert "<" not in response.text


def test_profile_update_counts_text_before_html_entity_encoding(
    client: TestClient,
    mailer: FakeMailer,
    repository: FakeAccountsRepository,
) -> None:
    headers = authenticated_headers(client, mailer)
    bio = "x" * 158 + " &"
    display_name = "x" * 48 + " <"

    response = client.patch(
        "/api/v1/accounts/me",
        headers=headers,
        json={"bio": bio, "display_name": display_name},
    )

    assert response.status_code == 200
    assert response.json()["bio"] == bio
    assert response.json()["display_name"] == "x" * 48 + " &lt;"
    assert repository.accounts[0].bio == bio
    assert repository.accounts[0].display_name == "x" * 48 + " &lt;"


def test_profile_update_accepts_its_escaped_response_again(
    client: TestClient, mailer: FakeMailer
) -> None:
    headers = authenticated_headers(client, mailer)
    first = client.patch(
        "/api/v1/accounts/me",
        headers=headers,
        json={"bio": "x" * 158 + " <", "display_name": "x" * 48 + " <"},
    )
    assert first.status_code == 200
    returned_profile = {
        "bio": first.json()["bio"],
        "display_name": first.json()["display_name"],
    }

    second = client.patch(
        "/api/v1/accounts/me",
        headers=headers,
        json=returned_profile,
    )

    assert second.status_code == 200
    assert second.json()["bio"] == returned_profile["bio"]
    assert second.json()["display_name"] == returned_profile["display_name"]


def test_profile_update_can_clear_optional_text_fields(
    client: TestClient, mailer: FakeMailer
) -> None:
    headers = authenticated_headers(client, mailer)
    client.patch(
        "/api/v1/accounts/me",
        headers=headers,
        json={"bio": "Bio", "display_name": "Juan"},
    )

    response = client.patch(
        "/api/v1/accounts/me",
        headers=headers,
        json={"bio": "   ", "display_name": ""},
    )

    assert response.status_code == 200
    assert response.json()["bio"] is None
    assert response.json()["display_name"] is None


def test_profile_update_rejects_a_handle_that_is_already_taken(
    client: TestClient,
    mailer: FakeMailer,
    repository: FakeAccountsRepository,
) -> None:
    headers = authenticated_headers(client, mailer)
    repository.accounts.append(Account(email="otro@udesa.edu.ar", handle="otro"))

    response = client.patch(
        "/api/v1/accounts/me",
        headers=headers,
        json={"handle": "@otro"},
    )

    assert response.status_code == 409
    assert response.json()["type"].endswith("/handle-taken")


@pytest.mark.parametrize(
    "payload",
    [
        {"handle": ""},
        {"handle": "   "},
        {"handle": None},
        {"handle": "@abc"},
        {"handle": "@" + "x" * 16},
        {"bio": "x" * 161},
        {"display_name": "x" * 51},
    ],
)
def test_profile_update_rejects_invalid_profile_values(
    client: TestClient, mailer: FakeMailer, payload: dict[str, object]
) -> None:
    headers = authenticated_headers(client, mailer)

    response = client.patch("/api/v1/accounts/me", headers=headers, json=payload)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


def test_profile_update_rejects_email_and_unknown_fields(
    client: TestClient, mailer: FakeMailer
) -> None:
    headers = authenticated_headers(client, mailer)

    response = client.patch(
        "/api/v1/accounts/me",
        headers=headers,
        json={"email": "nuevo@udesa.edu.ar"},
    )

    assert response.status_code == 422
    assert response.json()["type"].endswith("/validation-error")


def test_profile_update_requires_a_valid_bearer_token(client: TestClient) -> None:
    response = client.patch("/api/v1/accounts/me", json={"bio": "Bio"})

    assert response.status_code == 401
    assert response.json()["type"].endswith("/invalid-access-token")
