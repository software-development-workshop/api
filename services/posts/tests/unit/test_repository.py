import uuid
from datetime import UTC, datetime

from posts.models import Post
from posts.repository import PostsRepository


class FakeSession:
    def __init__(self, recent_count: int) -> None:
        self.recent_count = recent_count
        self.added: list[Post] = []
        self.committed = False
        self.rolled_back = False

    def execute(self, statement: object) -> None:
        return None

    def scalar(self, statement: object) -> int:
        return self.recent_count

    def add(self, post: Post) -> None:
        self.added.append(post)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def refresh(self, post: Post) -> None:
        post.id = uuid.uuid4()
        post.created_at = datetime.now(UTC)
        post.like_count = 0
        post.repost_count = 0
        post.reply_count = 0


def test_repository_persists_when_the_author_is_below_the_limit() -> None:
    session = FakeSession(recent_count=29)
    author_id = uuid.uuid4()

    stored = PostsRepository(session).create_within_hourly_limit(author_id, "hello")

    assert stored is session.added[0]
    assert stored.author_id == author_id
    assert stored.content == "hello"
    assert session.committed is True
    assert session.rolled_back is False


def test_repository_rolls_back_without_inserting_at_the_limit() -> None:
    session = FakeSession(recent_count=30)

    stored = PostsRepository(session).create_within_hourly_limit(uuid.uuid4(), "blocked")

    assert stored is None
    assert session.added == []
    assert session.committed is False
    assert session.rolled_back is True
