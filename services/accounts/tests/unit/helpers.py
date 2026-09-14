from fastapi.testclient import TestClient

from tests.fakes import FakeMailer

VALID = {"email": "juan@udesa.edu.ar", "handle": "@juan", "password": "Passw0rd"}
JWT_SECRET = "unit-test-jwt-secret-longer-than-32-bytes"


def verify_registered_account(client: TestClient, mailer: FakeMailer) -> None:
    client.post("/api/v1/registrations", json=VALID)
    client.get(f"/api/v1/verifications/{mailer.last_token}")
