import uuid

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from posts.models import Post


class PostsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_within_hourly_limit(
        self,
        author_id: uuid.UUID,
        content: str,
        limit: int = 30,
    ) -> Post | None:
        lock = select(func.pg_advisory_xact_lock(func.hashtextextended(str(author_id), 0)))
        self._session.execute(lock)

        recent_count = self._session.scalar(
            select(func.count(Post.id)).where(
                Post.author_id == author_id,
                Post.created_at >= func.now() - text("interval '1 hour'"),
            )
        )
        if recent_count is not None and recent_count >= limit:
            self._session.rollback()
            return None

        post = Post(author_id=author_id, content=content)
        self._session.add(post)
        self._session.commit()
        self._session.refresh(post)
        return post
