import uuid
from typing import Protocol

import nh3

from posts.errors import InvalidPostContentError, PostRateLimitExceededError
from posts.models import Post

MAX_POST_LENGTH = 280
HOURLY_POST_LIMIT = 30


class IdentityProvider(Protocol):
    def introspect(self, token: str) -> uuid.UUID: ...


class PostWriter(Protocol):
    def create_within_hourly_limit(
        self,
        author_id: uuid.UUID,
        content: str,
        limit: int = HOURLY_POST_LIMIT,
    ) -> Post | None: ...


def create_post(
    repository: PostWriter,
    identity_provider: IdentityProvider,
    token: str,
    content: str,
) -> Post:
    author_id = identity_provider.introspect(token)
    sanitised = sanitise_content(content)
    post = repository.create_within_hourly_limit(author_id, sanitised, HOURLY_POST_LIMIT)
    if post is None:
        raise PostRateLimitExceededError("A user cannot publish more than 30 posts per hour.")
    return post


def sanitise_content(content: str) -> str:
    normalised = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    _require_valid_length(normalised)
    sanitised = nh3.clean(normalised, tags=set()).strip()
    _require_valid_length(sanitised)
    return sanitised


def _require_valid_length(content: str) -> None:
    if not content or len(content) > MAX_POST_LENGTH:
        raise InvalidPostContentError("Post content must be between 1 and 280 characters.")
