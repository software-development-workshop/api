import json
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import httpx
import pytest

from posts import accounts_client, errors

ACCOUNT_ID = uuid.UUID("c6a8f8cf-9f92-48e9-a391-2c2deff8e32f")


def _client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler, base_url="http://accounts.test")


class IntrospectionHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        authorised = (
            self.path == "/api/v1/sessions/introspect"
            and self.headers.get("Authorization") == "Bearer socket-token"
        )
        status = 200 if authorised else 401
        body = json.dumps({"account_id": str(ACCOUNT_ID)}).encode() if authorised else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *args: object) -> None:
        return None


def test_introspection_returns_the_account_id_for_a_valid_bearer_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("Authorization") != "Bearer access-token":
            return httpx.Response(401)
        return httpx.Response(200, json={"account_id": str(ACCOUNT_ID)})

    with _client(httpx.MockTransport(handler)) as http_client:
        account_id = accounts_client.AccountsClient(http_client).introspect("access-token")

    assert account_id == ACCOUNT_ID


def test_introspection_maps_accounts_401_to_an_invalid_access_token() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(401))

    with _client(transport) as http_client:
        with pytest.raises(errors.InvalidAccessTokenError, match="Invalid access token"):
            accounts_client.AccountsClient(http_client).introspect("rejected-token")


@pytest.mark.parametrize("status_code", [204, 500])
def test_introspection_fails_closed_for_an_unexpected_accounts_status(status_code: int) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(status_code))

    with _client(transport) as http_client:
        with pytest.raises(errors.AccountsUnavailableError, match="confirm the account"):
            accounts_client.AccountsClient(http_client).introspect("access-token")


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={}),
        httpx.Response(200, json={"account_id": "not-a-uuid"}),
        httpx.Response(200, text="not-json"),
    ],
)
def test_introspection_fails_closed_for_an_invalid_accounts_response(
    response: httpx.Response,
) -> None:
    transport = httpx.MockTransport(lambda _: response)

    with _client(transport) as http_client:
        with pytest.raises(errors.AccountsUnavailableError, match="confirm the account"):
            accounts_client.AccountsClient(http_client).introspect("access-token")


def test_introspection_fails_closed_when_accounts_cannot_be_reached() -> None:
    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with _client(httpx.MockTransport(unavailable)) as http_client:
        with pytest.raises(errors.AccountsUnavailableError, match="confirm the account"):
            accounts_client.AccountsClient(http_client).introspect("access-token")


def test_introspection_crosses_a_real_http_socket_with_the_bearer_token() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), IntrospectionHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        host, port = server.server_address
        with httpx.Client(base_url=f"http://{host}:{port}", timeout=1) as http_client:
            account_id = accounts_client.AccountsClient(http_client).introspect("socket-token")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert account_id == ACCOUNT_ID
