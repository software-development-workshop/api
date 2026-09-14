import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from posts import api, main
from posts.models import Post
from tests.fakes import FakeIdentityProvider


def test_publishing_a_post_stores_it_in_the_database(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Accounts is not running in this job, so the identity provider is the only double.
    # The repository and the database are real.
    identity = FakeIdentityProvider()
    monkeypatch.setitem(main.app.dependency_overrides, api.get_identity_provider, lambda: identity)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/posts",
            headers={"Authorization": "Bearer access-token"},
            json={"content": " <strong>Hola</strong> "},
        )

    assert response.status_code == 201
    stored = session.execute(select(Post)).scalar_one()
    assert stored.author_id == identity.account_id
    assert stored.content == "Hola"
    assert response.json()["id"] == str(stored.id)
