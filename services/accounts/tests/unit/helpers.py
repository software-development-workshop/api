from datetime import UTC, datetime

from fastapi.testclient import TestClient

from accounts.models import Account
from accounts.service import register
from tests.fakes import FakeMailer
from tests.unit.fakes import FakeAccountsRepository

VALID = {"email": "juan@udesa.edu.ar", "handle": "@juan", "password": "Passw0rd"}
JWT_SECRET = "unit-test-jwt-secret-longer-than-32-bytes"
LOGIN_TIME = datetime(2030, 1, 2, 3, 4, 5, tzinfo=UTC)


def verify_registered_account(client: TestClient, mailer: FakeMailer) -> None:
    client.post("/api/v1/registrations", json=VALID)
    client.get(f"/api/v1/verifications/{mailer.last_token}")


def sign_up(
    repository: FakeAccountsRepository, mailer: FakeMailer, email: str = "juan@udesa.edu.ar"
) -> Account:
    return register(repository, mailer, email, "juan", "Passw0rd")


def active_account(repository: FakeAccountsRepository, mailer: FakeMailer) -> Account:
    account = sign_up(repository, mailer)
    account.verified_at = datetime.now(UTC)
    return account
