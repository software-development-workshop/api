import pytest

from accounts.validation import normalise_handle, validate_password


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
