import pytest

from posts import errors, service
from tests.fakes import FakeIdentityProvider, FakePostsRepository


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  hello\r\nworld  ", "hello\nworld"),
        ("<p>Hello <strong>world</strong></p>", "Hello world"),
        ("<script>alert(1)</script><p>Hello</p>", "Hello"),
        ("Tom & Jerry", "Tom &amp; Jerry"),
    ],
)
def test_sanitises_content_before_it_is_stored(raw: str, expected: str) -> None:
    assert service.sanitise_content(raw) == expected


@pytest.mark.parametrize(
    "invalid",
    [
        "",
        "   \t\r\n",
        "a" * 281,
        "<script></script>",
        "a" * 279 + "&",
    ],
)
def test_rejects_content_that_is_blank_or_too_long_before_or_after_sanitising(
    invalid: str,
) -> None:
    with pytest.raises(errors.InvalidPostContentError, match="between 1 and 280"):
        service.sanitise_content(invalid)


def test_create_post_uses_the_authenticated_author_and_sanitised_content() -> None:
    identity = FakeIdentityProvider()
    repository = FakePostsRepository()

    stored = service.create_post(
        repository,
        identity,
        "access-token",
        " <strong>Hello</strong> ",
    )

    assert stored is repository.posts[0]
    assert stored.author_id == identity.account_id
    assert stored.content == "Hello"
    assert (stored.like_count, stored.repost_count, stored.reply_count) == (0, 0, 0)


def test_create_post_reports_the_hourly_limit() -> None:
    with pytest.raises(errors.PostRateLimitExceededError, match="30 posts per hour"):
        service.create_post(
            FakePostsRepository(limited=True),
            FakeIdentityProvider(),
            "access-token",
            "Hello",
        )
