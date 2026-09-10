import asyncio
import json
import threading
from datetime import UTC, datetime

import pytest
from anyio.to_thread import current_default_thread_limiter

from accounts import api, recovery
from accounts.api import get_mailer, get_repository
from accounts.errors import VerificationEmailNotSentError
from accounts.main import app
from accounts.models import Account
from tests.fakes import FakeMailer
from tests.unit.fakes import FakeAccountsRepository


async def send_request(
    path: str, body: dict, response_sent: threading.Event, method: str = "POST"
) -> list[dict]:
    messages = []

    async def receive() -> dict:
        return {"type": "http.request", "body": json.dumps(body).encode()}

    async def send(message: dict) -> None:
        messages.append(message)
        if message["type"] == "http.response.body" and not message.get("more_body"):
            response_sent.set()

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
        },
        receive,
        send,
    )
    return messages


@pytest.mark.parametrize("path", ["/api/v1/password-resets", "/api/v1/verifications/resend"])
@pytest.mark.parametrize("fails", [False, True])
def test_response_finishes_before_the_provider_is_released(
    monkeypatch: pytest.MonkeyPatch, path: str, fails: bool
) -> None:
    response_sent = threading.Event()
    release_provider = threading.Event()
    provider_started = threading.Event()
    repository = FakeAccountsRepository()
    monkeypatch.setattr(recovery, "get_engine", lambda: None)
    monkeypatch.setattr(recovery, "AccountsRepository", lambda session: repository)
    repository.add(
        Account(
            email="juan@udesa.edu.ar",
            handle="juan",
            verified_at=datetime.now(UTC) if path.endswith("password-resets") else None,
        )
    )

    class ControlledMailer(FakeMailer):
        def wait_for_provider(self) -> None:
            provider_started.set()
            assert release_provider.wait(5), "test did not release the provider"
            if fails:
                raise VerificationEmailNotSentError("provider unavailable")

        def send_verification(self, to: str, token: str) -> None:
            self.wait_for_provider()
            super().send_verification(to, token)

        def send_password_reset(self, to: str, token: str) -> None:
            self.wait_for_provider()
            super().send_password_reset(to, token)

    mailer = ControlledMailer()
    monkeypatch.setitem(app.dependency_overrides, get_repository, lambda: repository)
    monkeypatch.setitem(app.dependency_overrides, get_mailer, lambda: mailer)
    body = (
        {"identifier": "@JUAN"}
        if path.endswith("password-resets")
        else {"email": "JUAN@udesa.edu.ar"}
    )

    async def exercise() -> list[dict]:
        request = asyncio.create_task(send_request(path, body, response_sent))
        try:
            assert await asyncio.to_thread(provider_started.wait, 2), "provider never started"
            assert response_sent.is_set(), "response is still waiting for the mail provider"
            assert not request.done(), "provider should still be blocked"
        finally:
            release_provider.set()
            await asyncio.wait_for(request, 5)
        return request.result()

    messages = asyncio.run(exercise())
    assert messages[0]["status"] == 202
    assert messages[1]["body"] == b""
    sent = mailer.password_resets if path.endswith("password-resets") else mailer.sent
    assert len(sent) == (0 if fails else 1)
    if fails and path.endswith("password-resets"):
        assert repository.password_reset_tokens[0].used_at is not None


@pytest.mark.parametrize("path", ["/api/v1/password-resets", "/api/v1/verifications/resend"])
@pytest.mark.parametrize("state", ["unknown", "verified", "unverified", "suspended", "deleted"])
def test_all_identities_get_the_response_before_the_account_lookup(
    monkeypatch: pytest.MonkeyPatch, path: str, state: str
) -> None:
    response_sent = threading.Event()

    class ObservedRepository(FakeAccountsRepository):
        def find_by_identifier(self, identifier: str) -> Account | None:
            assert response_sent.is_set(), "account lookup delayed the response"
            return super().find_by_identifier(identifier)

        def find_by_email(self, email: str) -> Account | None:
            assert response_sent.is_set(), "account lookup delayed the response"
            return super().find_by_email(email)

    repository = ObservedRepository()
    if state != "unknown":
        account = repository.add(Account(email="juan@udesa.edu.ar", handle="juan"))
        if state == "verified" or (path.endswith("password-resets") and state != "unverified"):
            account.verified_at = datetime.now(UTC)
        if state in {"suspended", "deleted"}:
            setattr(account, f"{state}_at", datetime.now(UTC))
    mailer = FakeMailer()
    monkeypatch.setattr(recovery, "get_engine", lambda: None)
    monkeypatch.setattr(recovery, "AccountsRepository", lambda session: repository)
    monkeypatch.setattr(api, "ResendMailer", lambda: mailer)
    monkeypatch.setitem(app.dependency_overrides, get_repository, lambda: repository)
    body = (
        {"identifier": "@JUAN"}
        if path.endswith("password-resets")
        else {"email": "JUAN@udesa.edu.ar"}
    )

    messages = asyncio.run(send_request(path, body, response_sent))

    assert messages[0]["status"] == 202
    assert messages[1]["body"] == b""
    if path.endswith("password-resets"):
        assert len(mailer.password_resets) == (1 if state == "verified" else 0)
        assert mailer.sent == []
    else:
        assert len(mailer.sent) == (1 if state == "unverified" else 0)
        assert mailer.password_resets == []


@pytest.mark.parametrize("path", ["/api/v1/password-resets", "/api/v1/verifications/resend"])
@pytest.mark.parametrize("probe", ["recovery", "health"])
def test_slow_recovery_does_not_block_generic_responses_or_public_health(
    monkeypatch: pytest.MonkeyPatch, path: str, probe: str
) -> None:
    provider_started = threading.Event()
    release_provider = threading.Event()
    repository = FakeAccountsRepository()
    repository.add(
        Account(
            email="juan@udesa.edu.ar",
            handle="juan",
            verified_at=datetime.now(UTC) if path.endswith("password-resets") else None,
        )
    )

    class BlockingMailer(FakeMailer):
        def send_verification(self, to: str, token: str) -> None:
            provider_started.set()
            assert release_provider.wait(5)

        send_password_reset = send_verification

    monkeypatch.setattr(recovery, "get_engine", lambda: None)
    monkeypatch.setattr(recovery, "AccountsRepository", lambda session: repository)
    monkeypatch.setattr(api, "ResendMailer", BlockingMailer)
    key = "identifier" if path.endswith("password-resets") else "email"

    async def exercise() -> list[dict]:
        limiter = current_default_thread_limiter()
        original_tokens = limiter.total_tokens
        limiter.total_tokens = 1
        first = asyncio.create_task(
            send_request(path, {key: "juan@udesa.edu.ar"}, threading.Event())
        )
        second_response = threading.Event()
        second = None
        try:
            assert await asyncio.to_thread(provider_started.wait, 2)
            second = asyncio.create_task(
                send_request("/health", {}, second_response, method="GET")
                if probe == "health"
                else send_request(path, {key: "unknown@udesa.edu.ar"}, second_response)
            )
            assert await asyncio.to_thread(second_response.wait, 1), "response waited for a worker"
        finally:
            release_provider.set()
            await asyncio.wait_for(first, 5)
            if second is not None:
                await asyncio.wait_for(second, 5)
            limiter.total_tokens = original_tokens
        return second.result()

    messages = asyncio.run(exercise())
    assert messages[0]["status"] == (200 if probe == "health" else 202)
    assert messages[1]["body"] == (b'{"status":"ok"}' if probe == "health" else b"")
