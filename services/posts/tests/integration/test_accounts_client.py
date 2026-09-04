import json
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import httpx

from posts.accounts_client import AccountsClient

ACCOUNT_ID = uuid.UUID("c6a8f8cf-9f92-48e9-a391-2c2deff8e32f")


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


def test_introspection_crosses_a_real_http_socket_with_the_bearer_token() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), IntrospectionHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        host, port = server.server_address
        with httpx.Client(base_url=f"http://{host}:{port}", timeout=1) as http_client:
            account_id = AccountsClient(http_client).introspect("socket-token")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert account_id == ACCOUNT_ID
