import uuid

import httpx
from pydantic import BaseModel, ValidationError

from posts.errors import AccountsUnavailableError, InvalidAccessTokenError

INTROSPECTION_PATH = "/api/v1/sessions/introspect"


class SessionIntrospectionResponse(BaseModel):
    account_id: uuid.UUID


class AccountsClient:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def introspect(self, token: str) -> uuid.UUID:
        try:
            response = self._client.post(
                INTROSPECTION_PATH,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError as error:
            raise AccountsUnavailableError(
                "Posts could not confirm the account identity."
            ) from error

        if response.status_code == 401:
            raise InvalidAccessTokenError("Invalid access token.")
        if response.status_code != 200:
            raise AccountsUnavailableError("Posts could not confirm the account identity.")

        try:
            body = SessionIntrospectionResponse.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            raise AccountsUnavailableError(
                "Posts could not confirm the account identity."
            ) from error
        return body.account_id
