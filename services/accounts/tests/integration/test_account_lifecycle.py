import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from accounts.api import get_mailer
from accounts.main import app
from accounts.models import Account
from tests.fakes import FakeMailer

REGISTRATION = {"email": "juan@udesa.edu.ar", "handle": "@juan", "password": "Passw0rd"}


def stored_account(session: Session) -> Account:
    session.expire_all()
    return session.execute(select(Account)).scalar_one()


def test_an_account_can_register_verify_log_in_edit_and_log_out(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The mailer is the only double: it stands in for Resend, and it is also the only way to
    # read the token in clear, because the database stores the digest.
    mailer = FakeMailer()
    monkeypatch.setitem(app.dependency_overrides, get_mailer, lambda: mailer)

    with TestClient(app) as client:
        assert client.post("/api/v1/registrations", json=REGISTRATION).status_code == 201

        assert client.get(f"/api/v1/verifications/{mailer.last_token}").status_code == 200
        assert stored_account(session).verified_at is not None

        login = client.post(
            "/api/v1/sessions",
            json={"identifier": REGISTRATION["email"], "password": REGISTRATION["password"]},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        profile = client.patch(
            "/api/v1/accounts/me",
            headers=headers,
            json={"handle": "@juancito", "bio": "Estudiante de UdeSA"},
        )
        assert profile.status_code == 200
        edited = stored_account(session)
        assert (edited.handle, edited.bio) == ("juancito", "Estudiante de UdeSA")

        introspection = client.post("/api/v1/sessions/introspect", headers=headers)
        assert introspection.status_code == 200
        assert introspection.json()["account_id"] == str(edited.id)

        assert client.post("/api/v1/sessions/logout", headers=headers).status_code == 204
        assert client.post("/api/v1/sessions/introspect", headers=headers).status_code == 401
