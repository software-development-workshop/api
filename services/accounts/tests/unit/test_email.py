from collections.abc import Iterator

import pytest
import resend
import resend.exceptions
from fastapi.testclient import TestClient

from accounts import recovery
from accounts.api import get_repository
from accounts.config import get_settings
from accounts.email import ResendMailer
from accounts.errors import VerificationEmailNotSentError
from accounts.main import app
from accounts.models import Account
from tests.unit.fakes import FakeAccountsRepository

ENV = {
    "DB_HOST": "db",
    "DB_PORT": "5432",
    "DB_NAME": "accounts",
    "DB_USER": "accounts",
    "DB_PASSWORD": "accounts",
    "RESEND_API_KEY": "re_a_test_key",
    "MAIL_FROM": "no-reply@udesax.app",
    "PUBLIC_BASE_URL": "https://api.udesax.app",
    "JWT_SECRET": "unit-test-jwt-secret-longer-than-32-bytes",
}


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, str]]]:
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()

    captured: list[dict[str, str]] = []

    def capture(params: dict[str, str]) -> dict[str, str]:
        captured.append(params)
        return {"id": "a-message-id"}

    # The key is module-level state on the SDK, so it is restored along with the send.
    monkeypatch.setattr(resend, "api_key", None)
    monkeypatch.setattr(resend.Emails, "send", capture)

    yield captured
    get_settings.cache_clear()


def test_sends_from_the_configured_address_to_the_account(sent: list[dict[str, str]]) -> None:
    ResendMailer().send_verification("juan@udesa.edu.ar", "a-token")

    message = sent[0]
    assert message["from"] == "no-reply@udesax.app"
    assert message["to"] == "juan@udesa.edu.ar"
    assert message["subject"]


def test_link_points_at_the_public_url_not_at_this_service(sent: list[dict[str, str]]) -> None:
    ResendMailer().send_verification("juan@udesa.edu.ar", "a-token")

    assert "https://api.udesax.app/api/v1/verifications/a-token" in sent[0]["text"]


def test_the_emailed_link_matches_a_route_this_service_serves(sent: list[dict[str, str]]) -> None:
    """A link nobody answers leaves the account unusable, and nothing else would catch it.

    Read off the message rather than rebuilt from the same constant: the point is that the
    two ends still agree, which a test deriving both from one place cannot show.
    """
    ResendMailer().send_verification("juan@udesa.edu.ar", "a-token")

    body = sent[0]["text"]
    link = next(word for word in body.split() if word.startswith("http"))
    path = link.removeprefix("https://api.udesax.app").replace("a-token", "{token}")

    assert path in app.openapi()["paths"]


def test_authenticates_with_the_configured_key(sent: list[dict[str, str]]) -> None:
    """The SDK also picks a key up off the process environment, which never sees the .env."""
    ResendMailer().send_verification("juan@udesa.edu.ar", "a-token")

    assert resend.api_key == "re_a_test_key"


def test_password_reset_uses_the_configured_addresses_and_subject(
    sent: list[dict[str, str]],
) -> None:
    ResendMailer().send_password_reset("juan@udesa.edu.ar", "a-token")

    message = sent[0]
    assert message["from"] == "no-reply@udesax.app"
    assert message["to"] == "juan@udesa.edu.ar"
    assert message["subject"] == "Restablecé tu contraseña de UdeSA-X"


def test_password_reset_link_points_at_the_client_and_states_its_life(
    sent: list[dict[str, str]],
) -> None:
    """The reset link is a client route, unlike the verification one this service serves."""
    ResendMailer().send_password_reset("juan@udesa.edu.ar", "a-token")

    body = sent[0]["text"]
    assert "https://api.udesax.app/reset-password?token=a-token" in body
    assert "10 minutos" in body


def test_a_refused_send_is_reported_in_the_language_of_the_domain(
    sent: list[dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Letting the SDK's own exception escape reaches the caller as an unexplained 500."""

    def refuse(_: dict[str, str]) -> dict[str, str]:
        raise resend.exceptions.ResendError(
            code=403,
            error_type="validation_error",
            message="The udesax.app domain is not verified.",
            suggested_action="Verify the domain.",
        )

    monkeypatch.setattr(resend.Emails, "send", refuse)

    with pytest.raises(VerificationEmailNotSentError):
        ResendMailer().send_verification("juan@udesa.edu.ar", "a-token")


@pytest.fixture
def null_provider_response(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    monkeypatch.setattr(resend, "api_key", None)

    def respond(**_: object) -> tuple[bytes, int, dict[str, str]]:
        return b"null", 200, {"content-type": "application/json"}

    # Keep SDK decoding and exception handling real; replace only the network boundary.
    monkeypatch.setattr(resend.default_http_client, "request", respond)
    yield
    get_settings.cache_clear()


def test_registration_maps_null_provider_response_to_problem_details(
    null_provider_response: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = FakeAccountsRepository()
    monkeypatch.setitem(app.dependency_overrides, get_repository, lambda: repository)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/registrations",
            json={"email": "juan@udesa.edu.ar", "handle": "@juan", "password": "Passw0rd"},
        )

    assert response.status_code == 502
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"].endswith("/verification-email-not-sent")
    account = repository.find_by_email("juan@udesa.edu.ar")
    assert account is not None
    assert account.verified_at is None


@pytest.mark.parametrize("email", ["juan@udesa.edu.ar", "unknown@udesa.edu.ar"])
def test_resend_keeps_generic_response_when_provider_returns_null(
    null_provider_response: None, monkeypatch: pytest.MonkeyPatch, email: str
) -> None:
    repository = FakeAccountsRepository()
    monkeypatch.setattr(recovery, "get_engine", lambda: None)
    monkeypatch.setattr(recovery, "AccountsRepository", lambda session: repository)
    repository.add(Account(email="juan@udesa.edu.ar", handle="juan"))
    monkeypatch.setitem(app.dependency_overrides, get_repository, lambda: repository)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/verifications/resend", json={"email": email})

    assert response.status_code == 202
    assert response.content == b""
