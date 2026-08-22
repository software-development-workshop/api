import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel

from accounts.errors import (
    DomainError,
    EmailAlreadyRegisteredError,
    domain_error_handler,
    validation_error_handler,
)


class Body(BaseModel):
    number: int


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    @app.get("/boom")
    def boom() -> None:
        raise EmailAlreadyRegisteredError("That email is already registered.")

    @app.post("/echo")
    def echo(body: Body) -> Body:
        return body

    return TestClient(app)


def test_a_domain_error_answers_with_its_own_status_and_type(client: TestClient) -> None:
    response = client.get("/boom")

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"].endswith("/email-already-registered")
    assert body["title"] == "Email already registered"
    assert body["status"] == 409
    assert body["detail"] == "That email is already registered."


def test_validation_failures_are_listed_field_by_field(client: TestClient) -> None:
    response = client.post("/echo", json={"number": "not-a-number"})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"].endswith("/validation-error")
    assert [e["field"] for e in body["errors"]] == ["number"]


def test_a_missing_body_is_reported_against_the_body_itself(client: TestClient) -> None:
    response = client.post("/echo")

    assert [e["field"] for e in response.json()["errors"]] == ["body"]
