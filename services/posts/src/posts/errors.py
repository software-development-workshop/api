from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

PROBLEM_BASE = "https://udesa-x.dev/problems"
CONTENT_TYPE = "application/problem+json"


class DomainError(Exception):
    status = 400
    slug = "domain-error"
    title = "Request rejected"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class InvalidPostContentError(DomainError):
    status = 422
    slug = "invalid-post-content"
    title = "Invalid post content"


class PostRateLimitExceededError(DomainError):
    status = 429
    slug = "post-rate-limit-exceeded"
    title = "Post rate limit exceeded"


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
    invalid_fields = [
        {"field": ".".join(str(part) for part in item["loc"][1:]) or "body", "message": item["msg"]}
        for item in error.errors()
    ]
    return _problem(
        422,
        "validation-error",
        "Validation failed",
        "One or more fields are invalid.",
        errors=invalid_fields,
    )
