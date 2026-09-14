from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

PROBLEM_BASE = "https://udesa-x.dev/problems"
CONTENT_TYPE = "application/problem+json"


class DomainError(Exception):
    """Something the caller asked for that the rules do not allow.

    Subclasses carry the HTTP status because this is the only place that maps a rule to a
    response; the service layer raises them without knowing HTTP exists.
    """

    status = 400
    slug = "domain-error"
    title = "Request rejected"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class EmailAlreadyRegisteredError(DomainError):
    status = 409
    slug = "email-already-registered"
    title = "Email already registered"


class HandleTakenError(DomainError):
    status = 409
    slug = "handle-taken"
    title = "Handle taken"


class InvalidCredentialsError(DomainError):
    status = 401
    slug = "invalid-credentials"
    title = "Invalid credentials"


class UnverifiedAccountError(DomainError):
    status = 403
    slug = "unverified-account"
    title = "Account not verified"


class SuspendedAccountError(DomainError):
    status = 403
    slug = "suspended-account"
    title = "Suspended account"


class AccountTemporarilyLockedError(DomainError):
    status = 423
    slug = "account-temporarily-locked"
    title = "Account temporarily locked"


class InvalidAccessTokenError(DomainError):
    status = 401
    slug = "invalid-access-token"
    title = "Invalid access token"


class InvalidProfileError(DomainError):
    status = 422
    slug = "invalid-profile"
    title = "Invalid profile"


def _problem(status: int, slug: str, title: str, detail: str, **extra: object) -> JSONResponse:
    body = {
        "type": f"{PROBLEM_BASE}/{slug}",
        "title": title,
        "status": status,
        "detail": detail,
        **extra,
    }
    return JSONResponse(status_code=status, content=body, media_type=CONTENT_TYPE)


async def domain_error_handler(_: Request, error: DomainError) -> JSONResponse:
    return _problem(error.status, error.slug, error.title, error.detail)


async def validation_error_handler(_: Request, error: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": ".".join(str(p) for p in e["loc"][1:]) or "body", "message": e["msg"]}
        for e in error.errors()
    ]
    return _problem(
        422,
        "validation-error",
        "Validation failed",
        "One or more fields are invalid.",
        errors=errors,
    )


class InvalidVerificationTokenError(DomainError):
    status = 400
    slug = "invalid-verification-token"
    title = "Invalid verification token"


class ExpiredVerificationTokenError(DomainError):
    status = 410
    slug = "expired-verification-token"
    title = "Verification token expired"


class InvalidPasswordResetTokenError(DomainError):
    status = 400
    slug = "invalid-password-reset-token"
    title = "Invalid password reset token"


class ExpiredPasswordResetTokenError(DomainError):
    status = 410
    slug = "expired-password-reset-token"
    title = "Password reset token expired"


class PasswordUnchangedError(DomainError):
    status = 400
    slug = "password-unchanged"
    title = "Password unchanged"


class VerificationEmailNotSentError(DomainError):
    """The account is registered and its link was issued; only the delivery failed.

    502 rather than 503: the mail provider is what broke, and retrying the request that
    raised this cannot help, because the address it carries is taken by then.
    """

    status = 502
    slug = "verification-email-not-sent"
    title = "Verification email not sent"
