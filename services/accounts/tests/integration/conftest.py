from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import Session

from accounts.db import get_engine
from tests.fakes import FakeMailer


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Run the real migrations, so these tests exercise the schema production gets."""
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
def session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
        session.rollback()
        session.execute(text("truncate table accounts cascade"))
        session.commit()


@pytest.fixture
def mailer() -> FakeMailer:
    return FakeMailer()
