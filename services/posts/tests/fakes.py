import uuid
from datetime import UTC, datetime

from posts.models import Post


class FakeIdentityProvider:
    def __init__(
        self,
        account_id: uuid.UUID | None = None,
        error: Exception | None = None,
    ) -> None:
        self.account_id = account_id or uuid.uuid4()
        self.error = error

    def introspect(self, token: str) -> uuid.UUID:
        if self.error is not None:
            raise self.error
        return self.account_id


class FakePostsRepository:
    def __init__(self, limited: bool = False) -> None:
        self.limited = limited
        self.posts: list[Post] = []

    def create_within_hourly_limit(
        self,
        author_id: uuid.UUID,
        content: str,
        limit: int = 30,
    ) -> Post | None:
        if self.limited:
            return None
        post = Post(
            id=uuid.uuid4(),
            author_id=author_id,
            content=content,
            created_at=datetime.now(UTC),
            like_count=0,
            repost_count=0,
            reply_count=0,
        )
        self.posts.append(post)
        return post
