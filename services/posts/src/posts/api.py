import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from posts.accounts_client import AccountsClient
from posts.config import API_PREFIX
from posts.db import get_session
from posts.errors import InvalidAccessTokenError
from posts.repository import PostsRepository
from posts.service import IdentityProvider, create_post

router = APIRouter(prefix=API_PREFIX)

SessionDep = Annotated[Session, Depends(get_session)]


def get_repository(session: SessionDep) -> PostsRepository:
    return PostsRepository(session)


def get_identity_provider(request: Request) -> AccountsClient:
    return request.app.state.accounts_client


RepositoryDep = Annotated[PostsRepository, Depends(get_repository)]
IdentityProviderDep = Annotated[IdentityProvider, Depends(get_identity_provider)]
BearerDep = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(HTTPBearer(auto_error=False)),
]


class PostCreationRequest(BaseModel):
    content: str


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author_id: uuid.UUID
    content: str
    created_at: datetime
    like_count: int
    repost_count: int
    reply_count: int


@router.post("/posts", status_code=status.HTTP_201_CREATED)
def publish_post(
    body: PostCreationRequest,
    credentials: BearerDep,
    repository: RepositoryDep,
    identity_provider: IdentityProviderDep,
) -> PostResponse:
    token = credentials.credentials if credentials is not None else None
    if token is None:
        raise InvalidAccessTokenError("Invalid access token.")
    post = create_post(repository, identity_provider, token, body.content)
    return PostResponse.model_validate(post)
