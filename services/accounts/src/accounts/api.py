import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from accounts.db import get_session
from accounts.repository import AccountsRepository
from accounts.service import register
from accounts.validation import normalise_handle, validate_password

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


def get_repository(session: SessionDep) -> AccountsRepository:
    return AccountsRepository(session)


RepositoryDep = Annotated[AccountsRepository, Depends(get_repository)]


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


class RegistrationResponse(BaseModel):
    id: uuid.UUID
    email: str
    handle: str


@router.post("/api/v1/registrations", status_code=status.HTTP_201_CREATED)
def register_account(body: RegistrationRequest, repository: RepositoryDep) -> RegistrationResponse:
    account = register(repository, body.email, body.handle, body.password)
    return RegistrationResponse(id=account.id, email=account.email, handle=f"@{account.handle}")
