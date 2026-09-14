from fastapi.testclient import TestClient

from accounts import tokens
from accounts.api import get_mailer
from accounts.main import app
from tests.fakes import FakeMailer, RefusingMailer
from tests.unit.fakes import FakeAccountsRepository
from tests.unit.helpers import VALID


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


def test_resend_answers_the_same_when_the_send_fails(
    client: TestClient, repository: FakeAccountsRepository
) -> None:
    """Only a registered address can reach a send, so its failure must not be visible here."""
    client.post("/api/v1/registrations", json=VALID)
    app.dependency_overrides[get_mailer] = RefusingMailer

    known = client.post("/api/v1/verifications/resend", json={"email": VALID["email"]})
    unknown = client.post("/api/v1/verifications/resend", json={"email": "nadie@udesa.edu.ar"})

    assert known.status_code == unknown.status_code == 202
    assert known.content == unknown.content
