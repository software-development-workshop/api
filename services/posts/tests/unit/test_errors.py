from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel

from posts import errors


class EchoRequest(BaseModel):
    content: str


def _client() -> TestClient:
    app = FastAPI()
    app.add_exception_handler(errors.DomainError, errors.domain_error_handler)
    app.add_exception_handler(RequestValidationError, errors.validation_error_handler)

    @app.get("/invalid-content")
    def invalid_content() -> None:
        raise errors.InvalidPostContentError("Post content must be between 1 and 280 characters.")

    @app.post("/echo")
    def echo(body: EchoRequest) -> EchoRequest:
        return body

    return TestClient(app)


def test_invalid_post_content_uses_problem_details_with_422() -> None:
    response = _client().get("/invalid-content")

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json() == {
        "type": "https://udesa-x.dev/problems/invalid-post-content",
        "title": "Invalid post content",
        "status": 422,
        "detail": "Post content must be between 1 and 280 characters.",
    }


def test_request_validation_lists_the_invalid_field() -> None:
    response = _client().post("/echo", json={})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"].endswith("/validation-error")
    assert response.json()["errors"] == [{"field": "content", "message": "Field required"}]
