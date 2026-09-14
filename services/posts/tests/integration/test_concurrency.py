import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from posts.db import get_engine
from posts.models import Post
from posts.repository import PostsRepository


def test_concurrent_requests_cannot_exceed_the_hourly_limit(session: Session) -> None:
    author_id = uuid.uuid4()
    session.add_all(
        Post(author_id=author_id, content=f"existing post {number}") for number in range(29)
    )
    session.commit()
    barrier = Barrier(2)

    def publish(content: str) -> bool:
        with Session(get_engine()) as worker_session:
            barrier.wait()
            stored = PostsRepository(worker_session).create_within_hourly_limit(
                author_id,
                content,
            )
            return stored is not None

    with ThreadPoolExecutor(max_workers=2) as executor:
        accepted = list(executor.map(publish, ["concurrent one", "concurrent two"]))

    count = session.scalar(
        select(func.count()).select_from(Post).where(Post.author_id == author_id)
    )
    assert sorted(accepted) == [False, True]
    assert count == 30
