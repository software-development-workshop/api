from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from accounts import recovery
from accounts.api import get_mailer, get_repository
from accounts.config import get_settings
from accounts.main import app
from tests.fakes import FakeMailer
from tests.unit.fakes import FakeAccountsRepository
from tests.unit.helpers import JWT_SECRET


@pytest.fixture
def repository(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeAccountsRepository]:
    fake = FakeAccountsRepository()
    monkeypatch.setattr(recovery, "get_engine", lambda: None)
    monkeypatch.setattr(recovery, "AccountsRepository", lambda session: fake)
    app.dependency_overrides[get_repository] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def mailer(repository: FakeAccountsRepository) -> FakeMailer:
    fake = FakeMailer()
    app.dependency_overrides[get_mailer] = lambda: fake
    return fake


@pytest.fixture
def client(mailer: FakeMailer) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(jwt_secret=JWT_SECRET)
    return TestClient(app)
