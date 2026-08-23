import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from accounts.config import API_PREFIX
from accounts.db import get_session
from accounts.email import SmtpMailer
from accounts.models import Account
from accounts.repository import AccountsRepository
from accounts.service import Mailer, register, resend_verification, verify
from accounts.validation import normalise_handle, validate_password

router = APIRouter(prefix=API_PREFIX)

SessionDep = Annotated[Session, Depends(get_session)]


def get_repository(session: SessionDep) -> AccountsRepository:
    return AccountsRepository(session)


def get_mailer() -> Mailer:
    return SmtpMailer()


RepositoryDep = Annotated[AccountsRepository, Depends(get_repository)]
MailerDep = Annotated[Mailer, Depends(get_mailer)]


class RegistrationRequest(BaseModel):
    email: EmailStr
    handle: str
    password: str

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: EmailStr) -> str:
        return str(value).lower()

    @field_validator("handle")
    @classmethod
    def _check_handle(cls, value: str) -> str:
        return normalise_handle(value)

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        return validate_password(value)


class ResendRequest(BaseModel):
    email: EmailStr


class AccountResponse(BaseModel):
    id: uuid.UUID
    email: str
    handle: str
    verified: bool


def _as_response(account: Account) -> AccountResponse:
    return AccountResponse(
        id=account.id,
        email=account.email,
        handle=f"@{account.handle}",
        verified=account.verified_at is not None,
    )


@router.post("/registrations", status_code=status.HTTP_201_CREATED)
def register_account(
    body: RegistrationRequest, repository: RepositoryDep, mailer: MailerDep
) -> AccountResponse:
    return _as_response(register(repository, mailer, body.email, body.handle, body.password))


@router.get("/verifications/{token}")
def verify_account(token: str, repository: RepositoryDep) -> AccountResponse:
    return _as_response(verify(repository, token))


@router.post("/verifications/resend", status_code=status.HTTP_202_ACCEPTED)
def resend(body: ResendRequest, repository: RepositoryDep, mailer: MailerDep) -> Response:
    resend_verification(repository, mailer, body.email)
    return Response(status_code=status.HTTP_202_ACCEPTED)
