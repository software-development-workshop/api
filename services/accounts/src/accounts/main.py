from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from accounts.api import router
from accounts.errors import DomainError, domain_error_handler, validation_error_handler

app = FastAPI(title="UdeSA-X Accounts")

app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
