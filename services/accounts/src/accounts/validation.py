import re

import nh3

HANDLE_MIN_LENGTH = 4
HANDLE_MAX_LENGTH = 15
BIO_MAX_LENGTH = 160
DISPLAY_NAME_MAX_LENGTH = 50
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

_HANDLE = re.compile(rf"^@\w{{{HANDLE_MIN_LENGTH},{HANDLE_MAX_LENGTH}}}$", re.ASCII)


def normalise_handle(value: str) -> str:
    """Validate a handle as the user typed it and return its stored form, without the '@'.

    The length bounds apply to the identifier, not to the '@': the prefix is presentation,
    so counting it would leave a handle of 3 real characters passing a rule that reads as 4.
    """
    if not _HANDLE.match(value):
        raise ValueError(
            f"must start with '@' followed by {HANDLE_MIN_LENGTH} to {HANDLE_MAX_LENGTH} "
            "letters, numbers or underscores"
        )
    return value[1:].lower()


def sanitise_profile_text(value: str | None, max_length: int) -> str | None:
    """Strip markup from optional profile text and enforce its final size.

    Empty values intentionally become NULL so clearing a profile field has the same
    representation whether the client sends whitespace or an empty string.
    """
    if value is None:
        return None

    normalised = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalised:
        return None
    if len(normalised) > max_length:
        raise ValueError(f"must be at most {max_length} characters long")

    sanitised = nh3.clean(normalised, tags=set()).strip()
    if not sanitised:
        return None
    if len(sanitised) > max_length:
        raise ValueError(f"must be at most {max_length} characters after sanitisation")
    return sanitised


def validate_password(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"must be at least {PASSWORD_MIN_LENGTH} characters long")
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"must be at most {PASSWORD_MAX_LENGTH} characters long")
    if not any(c.isupper() for c in value):
        raise ValueError("must contain an uppercase letter")
    if not any(c.isdigit() for c in value):
        raise ValueError("must contain a number")
    return value
