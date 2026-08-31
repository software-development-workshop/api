import uuid
from typing import Annotated, Literal, Self

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, StringConstraints, field_validator, model_validator
from sqlalchemy.orm import Session

from accounts import access_tokens
from accounts.config import API_PREFIX, Settings, get_settings
from accounts.db import get_session
from accounts.email import ResendMailer
from accounts.errors import InvalidAccessTokenError
from accounts.models import Account
from accounts.repository import AccountsRepository
from accounts.service import (
    Mailer,
    authenticate,
    register,
    request_password_reset,
    resend_verification,
    reset_password,
    revoke_access_token,
    validate_access_token,
    verify,
)
from accounts.validation import normalise_handle, validate_password

router = APIRouter(prefix=API_PREFIX)

SessionDep = Annotated[Session, Depends(get_session)]


def get_repository(session: SessionDep) -> AccountsRepository:
    return AccountsRepository(session)


def get_mailer() -> Mailer:
    return ResendMailer()


RepositoryDep = Annotated[AccountsRepository, Depends(get_repository)]
MailerDep = Annotated[Mailer, Depends(get_mailer)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
BearerDep = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(HTTPBearer(auto_error=False)),
]

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=254)]
Password = Annotated[str, StringConstraints(min_length=1, max_length=128)]


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


class SessionRequest(BaseModel):
    identifier: Identifier
    password: Password


class SessionResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int


class SessionIntrospectionResponse(BaseModel):
    account_id: uuid.UUID


class PasswordResetRequest(BaseModel):
    identifier: Identifier


class PasswordResetCompletion(BaseModel):
    new_password: Password
    password_confirmation: Password

    @field_validator("new_password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        return validate_password(value)

    @model_validator(mode="after")
    def _passwords_match(self) -> Self:
        if self.new_password != self.password_confirmation:
            raise ValueError("password confirmation must match the new password")
        return self


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


@router.post("/password-resets", status_code=status.HTTP_202_ACCEPTED)
def request_reset(
    body: PasswordResetRequest,
    repository: RepositoryDep,
    mailer: MailerDep,
    background_tasks: BackgroundTasks,
) -> Response:
    background_tasks.add_task(request_password_reset, repository, mailer, body.identifier)
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/password-resets/{token}", status_code=status.HTTP_204_NO_CONTENT)
def complete_reset(
    token: str,
    body: PasswordResetCompletion,
    repository: RepositoryDep,
) -> Response:
    reset_password(repository, token, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions")
def create_session(
    body: SessionRequest, repository: RepositoryDep, settings: SettingsDep
) -> SessionResponse:
    account = authenticate(repository, body.identifier, body.password)
    issued = access_tokens.issue(
        account.id,
        settings.jwt_secret,
        session_version=account.session_version,
    )
    return SessionResponse(access_token=issued.token, expires_in=issued.expires_in)


@router.post("/sessions/introspect")
def introspect_session(
    credentials: BearerDep,
    repository: RepositoryDep,
    settings: SettingsDep,
) -> SessionIntrospectionResponse:
    token = credentials.credentials if credentials is not None else None
    if token is None:
        raise InvalidAccessTokenError("Invalid access token.")
    claims = validate_access_token(repository, token, settings.jwt_secret)
    return SessionIntrospectionResponse(account_id=claims.subject)


@router.post("/sessions/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(credentials: BearerDep, repository: RepositoryDep, settings: SettingsDep) -> Response:
    token = credentials.credentials if credentials is not None else None
    revoke_access_token(repository, token, settings.jwt_secret)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
