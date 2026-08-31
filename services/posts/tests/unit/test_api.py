from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from posts import api, errors, main
from tests.fakes import FakeIdentityProvider, FakePostsRepository


@contextmanager
def _client(
    repository: FakePostsRepository | None = None,
    identity: FakeIdentityProvider | None = None,
) -> Iterator[TestClient]:
    app = main.app
    app.dependency_overrides[api.get_repository] = lambda: repository or FakePostsRepository()
    app.dependency_overrides[api.get_identity_provider] = lambda: identity or FakeIdentityProvider()
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_creates_an_authenticated_post_with_the_approved_response() -> None:
    repository = FakePostsRepository()
    identity = FakeIdentityProvider()

    with _client(repository, identity) as client:
        response = client.post(
            "/api/v1/posts",
            headers={"Authorization": "Bearer access-token"},
            json={"content": " <strong>Hello</strong> "},
        )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(repository.posts[0].id),
        "author_id": str(identity.account_id),
        "content": "Hello",
        "created_at": repository.posts[0].created_at.isoformat().replace("+00:00", "Z"),
        "like_count": 0,
        "repost_count": 0,
        "reply_count": 0,
    }


def test_rejects_a_missing_bearer_token_with_problem_details() -> None:
    with _client() as client:
        response = client.post("/api/v1/posts", json={"content": "Hello"})

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"].endswith("/invalid-access-token")


def test_propagates_an_access_token_rejected_by_accounts() -> None:
    identity = FakeIdentityProvider(error=errors.InvalidAccessTokenError("Invalid access token."))

    with _client(identity=identity) as client:
        response = client.post(
            "/api/v1/posts",
            headers={"Authorization": "Bearer rejected-token"},
            json={"content": "Hello"},
        )

    assert response.status_code == 401
    assert response.json()["type"].endswith("/invalid-access-token")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"content": ""},
        {"content": "   \t\r\n"},
        {"content": "<script></script>"},
        {"content": "a" * 281},
    ],
)
def test_rejects_missing_blank_markup_only_or_oversized_content(
    body: dict[str, str],
) -> None:
    with _client() as client:
        response = client.post(
            "/api/v1/posts",
            headers={"Authorization": "Bearer access-token"},
            json=body,
        )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


def test_reports_the_hourly_rate_limit() -> None:
    with _client(repository=FakePostsRepository(limited=True)) as client:
        response = client.post(
            "/api/v1/posts",
            headers={"Authorization": "Bearer access-token"},
            json={"content": "Hello"},
        )

    assert response.status_code == 429
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"].endswith("/post-rate-limit-exceeded")


def test_fails_closed_when_accounts_is_unavailable() -> None:
    identity = FakeIdentityProvider(
        error=errors.AccountsUnavailableError("Posts could not confirm the account identity.")
    )

    with _client(identity=identity) as client:
        response = client.post(
            "/api/v1/posts",
            headers={"Authorization": "Bearer access-token"},
            json={"content": "Hello"},
        )

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"].endswith("/accounts-unavailable")
