import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from posts import repository
from posts.models import Post


def test_creates_a_post_with_database_defaults(session: Session) -> None:
    author_id = uuid.uuid4()

    stored = repository.PostsRepository(session).create_within_hourly_limit(
        author_id,
        "hello",
    )

    assert stored.id is not None
    assert stored.author_id == author_id
    assert stored.content == "hello"
    assert stored.created_at.tzinfo is not None
    assert (stored.like_count, stored.repost_count, stored.reply_count) == (0, 0, 0)


def test_hourly_limit_accepts_thirty_posts_and_rejects_the_thirty_first(
    session: Session,
) -> None:
    posts = repository.PostsRepository(session)
    author_id = uuid.uuid4()

    accepted = [
        posts.create_within_hourly_limit(author_id, f"post {number}") for number in range(30)
    ]
    rejected = posts.create_within_hourly_limit(author_id, "post 31")

    count = session.scalar(select(func.count()).select_from(Post))
    assert all(post is not None for post in accepted)
    assert rejected is None
    assert count == 30


def test_posts_older_than_one_hour_do_not_consume_the_limit(session: Session) -> None:
    author_id = uuid.uuid4()
    session.add_all(
        Post(
            author_id=author_id,
            content=f"old post {number}",
            created_at=datetime.now(UTC) - timedelta(hours=2),
        )
        for number in range(30)
    )
    session.commit()

    stored = repository.PostsRepository(session).create_within_hourly_limit(author_id, "new")

    assert stored is not None
    assert stored.content == "new"


def test_hourly_limit_is_independent_for_each_author(session: Session) -> None:
    posts = repository.PostsRepository(session)
    limited_author = uuid.uuid4()
    other_author = uuid.uuid4()
    for number in range(30):
        assert posts.create_within_hourly_limit(limited_author, f"post {number}") is not None

    stored = posts.create_within_hourly_limit(other_author, "first post")

    assert stored is not None
    assert stored.author_id == other_author
