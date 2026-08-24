import re

HANDLE_MIN_LENGTH = 4
HANDLE_MAX_LENGTH = 15
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
