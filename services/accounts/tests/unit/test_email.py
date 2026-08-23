from collections.abc import Iterator
from email.message import EmailMessage
from typing import ClassVar

import pytest

from accounts import email as email_module
from accounts.config import get_settings
from accounts.email import SmtpMailer
from accounts.main import app

ENV = {
    "DB_HOST": "db",
    "DB_PORT": "5432",
    "DB_NAME": "accounts",
    "DB_USER": "accounts",
    "DB_PASSWORD": "accounts",
    "SMTP_HOST": "smtp",
    "SMTP_PORT": "1025",
    "SMTP_FROM": "no-reply@udesa-x.dev",
    "PUBLIC_BASE_URL": "https://api.udesa-x.dev",
}


class FakeSmtp:
    sent: ClassVar[list[EmailMessage]] = []
    connections: ClassVar[list[tuple[str, int]]] = []

    def __init__(self, host: str, port: int) -> None:
        FakeSmtp.connections.append((host, port))

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def send_message(self, message: EmailMessage) -> None:
        FakeSmtp.sent.append(message)


@pytest.fixture
def smtp(monkeypatch: pytest.MonkeyPatch) -> Iterator[type[FakeSmtp]]:
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    FakeSmtp.sent, FakeSmtp.connections = [], []
    monkeypatch.setattr(email_module.smtplib, "SMTP", FakeSmtp)
    yield FakeSmtp
    get_settings.cache_clear()


def test_sends_from_the_configured_address_to_the_account(smtp: type[FakeSmtp]) -> None:
    SmtpMailer().send_verification("juan@udesa.edu.ar", "a-token")

    message = smtp.sent[0]
    assert message["From"] == "no-reply@udesa-x.dev"
    assert message["To"] == "juan@udesa.edu.ar"
    assert message["Subject"]


def test_link_points_at_the_public_url_not_at_this_service(smtp: type[FakeSmtp]) -> None:
    SmtpMailer().send_verification("juan@udesa.edu.ar", "a-token")

    body = smtp.sent[0].get_content()
    assert "https://api.udesa-x.dev/api/v1/verifications/a-token" in body


def test_the_emailed_link_matches_a_route_this_service_serves(smtp: type[FakeSmtp]) -> None:
    """A link nobody answers leaves the account unusable, and nothing else would catch it.

    Read off the message rather than rebuilt from the same constant: the point is that the
    two ends still agree, which a test deriving both from one place cannot show.
    """
    SmtpMailer().send_verification("juan@udesa.edu.ar", "a-token")

    body = smtp.sent[0].get_content()
    link = next(word for word in body.split() if word.startswith("http"))
    path = link.removeprefix("https://api.udesa-x.dev").replace("a-token", "{token}")

    assert path in app.openapi()["paths"]


def test_connects_to_the_configured_server(smtp: type[FakeSmtp]) -> None:
    SmtpMailer().send_verification("juan@udesa.edu.ar", "a-token")

    assert smtp.connections == [("smtp", 1025)]
