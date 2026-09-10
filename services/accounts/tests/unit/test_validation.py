import pytest

from accounts.validation import (
    BIO_MAX_LENGTH,
    DISPLAY_NAME_MAX_LENGTH,
    normalise_handle,
    sanitise_profile_text,
    validate_password,
)


@pytest.mark.parametrize("value", ["@juan", "@a_b_1", "@" + "x" * 15])
def test_accepts_a_well_formed_handle(value: str) -> None:
    assert normalise_handle(value) == value[1:]


@pytest.mark.parametrize(
    "value",
    [
        "juan",  # no leading @
        "@abc",  # three characters, one short
        "@" + "x" * 16,  # one over
        "@with-dash",
        "@with space",
        "@acentué",  # letters outside ASCII
        "@",
        "",
    ],
)
def test_rejects_a_malformed_handle(value: str) -> None:
    with pytest.raises(ValueError, match="must start with"):
        normalise_handle(value)


def test_strips_the_at_sign_because_it_is_presentation() -> None:
    assert normalise_handle("@juan") == "juan"


def test_sanitises_profile_text_and_removes_markup() -> None:
    assert sanitise_profile_text(" <b>Hello</b><script>alert(1)</script> ", 160) == "Hello"


def test_keeps_encoded_markup_escaped_after_normalising_entities() -> None:
    assert (
        sanitise_profile_text("&lt;script&gt;alert(1)&lt;/script&gt;", 160)
        == "&lt;script&gt;alert(1)&lt;/script&gt;"
    )


@pytest.mark.parametrize(
    ("value", "max_length", "expected"),
    [
        ("x" * 158 + " &", BIO_MAX_LENGTH, "x" * 158 + " &"),
        ("x" * 158 + " <", BIO_MAX_LENGTH, "x" * 158 + " &lt;"),
        ("x" * 48 + " &", DISPLAY_NAME_MAX_LENGTH, "x" * 48 + " &"),
        ("x" * 48 + " <", DISPLAY_NAME_MAX_LENGTH, "x" * 48 + " &lt;"),
    ],
)
def test_counts_profile_text_before_html_entity_encoding(
    value: str, max_length: int, expected: str
) -> None:
    assert sanitise_profile_text(value, max_length) == expected


@pytest.mark.parametrize("value", [None, "", "  \r\n  ", "<script></script>"])
def test_empty_profile_text_is_stored_as_null(value: str | None) -> None:
    assert sanitise_profile_text(value, BIO_MAX_LENGTH) is None


@pytest.mark.parametrize(
    ("value", "max_length"),
    [
        ("x" * (BIO_MAX_LENGTH + 1), BIO_MAX_LENGTH),
        ("x" * (DISPLAY_NAME_MAX_LENGTH + 1), DISPLAY_NAME_MAX_LENGTH),
    ],
)
def test_rejects_profile_text_over_its_limit(value: str, max_length: int) -> None:
    with pytest.raises(ValueError, match="at most"):
        sanitise_profile_text(value, max_length)


@pytest.mark.parametrize("value", ["Passw0rd", "A1" + "x" * 126])
def test_accepts_a_password_meeting_the_policy(value: str) -> None:
    assert validate_password(value) == value


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("Pass0", "at least 8"),
        ("A1" + "x" * 127, "at most 128"),
        ("password1", "uppercase"),
        ("PasswordX", "number"),
        ("", "at least 8"),
    ],
)
def test_rejects_a_password_breaking_the_policy(value: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        validate_password(value)
