from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from posts.accounts_client import AccountsClient
from posts.api import router
from posts.config import get_settings
from posts.errors import DomainError, domain_error_handler, validation_error_handler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    with httpx.Client(
        base_url=str(settings.accounts_base_url),
        timeout=settings.accounts_timeout_seconds,
    ) as http_client:
        app.state.accounts_client = AccountsClient(http_client)
        yield


app = FastAPI(title="UdeSA-X Posts", lifespan=lifespan)
app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
