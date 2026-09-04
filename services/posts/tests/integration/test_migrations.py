import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DataError, IntegrityError


def _database_url() -> str:
    return (
        f"postgresql+psycopg://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
        f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
    )


def _migrated_engine() -> Engine:
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(_database_url())
    with engine.begin() as connection:
        connection.execute(text("truncate table posts"))
    return engine


def test_initial_migration_creates_the_complete_posts_schema() -> None:
    engine = _migrated_engine()
    inspector = inspect(engine)

    assert {column["name"] for column in inspector.get_columns("posts")} == {
        "id",
        "author_id",
        "content",
        "created_at",
        "like_count",
        "repost_count",
        "reply_count",
    }
    assert {index["name"] for index in inspector.get_indexes("posts")} == {
        "ix_posts_author_created_at"
    }


def test_database_stamps_creation_time_and_zero_counters() -> None:
    engine = _migrated_engine()

    with engine.begin() as connection:
        stored = (
            connection.execute(
                text(
                    """
                insert into posts (id, author_id, content)
                values (:id, :author_id, :content)
                returning created_at, like_count, repost_count, reply_count
                """
                ),
                {"id": uuid.uuid4(), "author_id": uuid.uuid4(), "content": "hello"},
            )
            .mappings()
            .one()
        )

    assert stored["created_at"].tzinfo is not None
    assert stored["like_count"] == 0
    assert stored["repost_count"] == 0
    assert stored["reply_count"] == 0


@pytest.mark.parametrize(
    ("invalid", "expected_error"),
    [("", IntegrityError), ("   ", IntegrityError), ("a" * 281, DataError)],
)
def test_database_rejects_blank_or_oversized_content(
    invalid: str,
    expected_error: type[IntegrityError] | type[DataError],
) -> None:
    engine = _migrated_engine()

    with pytest.raises(expected_error), engine.begin() as connection:
        connection.execute(
            text("insert into posts (id, author_id, content) values (:id, :author_id, :content)"),
            {"id": uuid.uuid4(), "author_id": uuid.uuid4(), "content": invalid},
        )


@pytest.mark.parametrize(
    "statement",
    [
        "insert into posts (id, author_id, content, like_count) "
        "values (:id, :author_id, 'hello', -1)",
        "insert into posts (id, author_id, content, repost_count) "
        "values (:id, :author_id, 'hello', -1)",
        "insert into posts (id, author_id, content, reply_count) "
        "values (:id, :author_id, 'hello', -1)",
    ],
)
def test_database_rejects_negative_counters(statement: str) -> None:
    engine = _migrated_engine()

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(statement),
            {"id": uuid.uuid4(), "author_id": uuid.uuid4()},
        )
