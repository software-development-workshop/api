# UdeSA-X

Mobile-first social platform, built for a university software development workshop.

The services live here, one directory each under `services/`. Every service is
containerised and owns its own database; they share a repository, not a runtime.

## Services

| Service | Stack | Port |
|---|---|---|
| [accounts](services/accounts) | Python 3.13 + FastAPI | 8000 |
| [posts](services/posts) | Python 3.13 + FastAPI | 8001 |

## Run it

From a clean clone, with Docker running:

Get your per-developer Resend key with sending access from the team's password manager.
Replace the placeholder below in your shell, not in this file. Never commit the key.

PowerShell:

```powershell
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$env:JWT_SECRET = [Convert]::ToBase64String($bytes)
$env:RESEND_API_KEY = "<your per-developer Resend key>"
docker compose up --build
```

POSIX shell:

```sh
export JWT_SECRET="$(openssl rand -base64 32)"
export RESEND_API_KEY="<your per-developer Resend key>"
docker compose up --build
```

Both variables must be set before invoking Compose; it validates the whole configuration
even when starting only one service. A service's `.env` file is not automatically loaded
by Compose from the repository root.

The Accounts API docs are at <http://localhost:8000/docs> and the Posts API docs are at
<http://localhost:8001/docs>. Verification emails go out through Resend and arrive in a real
inbox. Send to `delivered@resend.dev` to
exercise the flow without filling your own inbox.

## Work on a service

### Recovery responses

`POST /api/v1/password-resets` and `POST /api/v1/verifications/resend` return an empty `202`
after validating the request, before looking up the account or sending mail. A task in the
API process then checks eligibility and sends the link using its own database session.
`202` does not confirm that an account exists or that an email was delivered.

These tasks are not durable: a process crash can interrupt them, and the user must request
another link. A handled password-reset delivery failure invalidates that attempt's token.
Registration still waits for its email and returns `502` Problem Details if delivery fails.
See [ADR-0011](docs/adr/0011-recuperacion-despues-de-la-respuesta.md) for the tradeoffs.

### Local development

Each service is a self-contained `uv` project.

```bash
cd services/accounts
uv sync
uv run pytest tests/unit          # no configuration needed
```

The integration tests need the database. `compose.yaml` publishes it on **5433**, so it does
not collide with a Postgres already running on the default port:

```bash
RESEND_API_KEY=not-a-real-key \
  JWT_SECRET=integration-test-jwt-secret-32-bytes-minimum docker compose up -d accounts-db
cd services/accounts
DB_HOST=localhost DB_PORT=5433 DB_NAME=accounts DB_USER=accounts DB_PASSWORD=accounts \
  RESEND_API_KEY=not-a-real-key MAIL_FROM=no-reply@udesax.app \
  PUBLIC_BASE_URL=http://localhost:8000 \
  JWT_SECRET=integration-test-jwt-secret-32-bytes-minimum \
  uv run pytest tests/integration
```

To run the service against that database, with migrations applied:

```bash
uv run alembic upgrade head
uv run uvicorn accounts.main:app --reload
```

Posts is another self-contained `uv` project. Its integration database is published on 5434:

For this database-only command, a fake key satisfies Compose interpolation without sending
mail. The snippet preserves an already exported key; replace the fake value with your real
key before running Accounts or the full stack.

```powershell
$env:JWT_SECRET = "integration-test-jwt-secret-32-bytes-minimum"
if (-not $env:RESEND_API_KEY) {
    $env:RESEND_API_KEY = "not-a-real-key"
}
docker compose up -d posts-db
Set-Location services/posts
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "5434"
$env:DB_NAME = "posts"
$env:DB_USER = "posts"
$env:DB_PASSWORD = "posts"
$env:ACCOUNTS_BASE_URL = "http://localhost:8000"
$env:ACCOUNTS_TIMEOUT_SECONDS = "2"
uv sync
uv run pytest tests/unit --cov=src --cov-fail-under=85
uv run pytest tests/integration
```

To run Posts outside Compose against those local services:

```powershell
uv run alembic upgrade head
uv run uvicorn posts.main:app --host 127.0.0.1 --port 8001
```

Given an already verified account, the authenticated publish request is:

```powershell
$loginBody = @{ identifier = "@juan"; password = "Passw0rd" } | ConvertTo-Json
$session = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/sessions `
  -ContentType "application/json" -Body $loginBody
$headers = @{ Authorization = "Bearer $($session.access_token)" }
$postBody = @{ content = "Mi primera publicación" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8001/api/v1/posts `
  -Headers $headers -ContentType "application/json" -Body $postBody
```

## Delete the authenticated account

With the Bearer headers from the Login example above, confirm the account's current password:

```powershell
$deletionBody = @{ password = "Passw0rd" } | ConvertTo-Json
Invoke-WebRequest -Method Post -Uri http://localhost:8000/api/v1/account-deletions `
  -Headers $headers -ContentType "application/json" -Body $deletionBody
```

Success returns `204` with no body. The account is selected from the JWT, never a client-supplied
account ID. The password is checked exactly, including spaces. The transaction preserves the
account UUID and references, sets `deleted_at`, increments `session_version`, and invalidates
all pending verification and password-reset links. Existing JWTs fail introspection and new
Posts requests with `401`; Login can no longer issue sessions for the deleted account.

Login and deletion share five consecutive wrong-password attempts and a 15-minute lockout.
The fifth failed confirmation returns `401 invalid-credentials` and starts the lock; subsequent
confirmations return `423 account-temporarily-locked` without checking the password or extending
the window. Wrong confirmations only modify the failure counter and lock. A successful Login
or password recovery resets the shared budget; recovery also invalidates the old JWTs.

Invalid, revoked or obsolete JWTs and suspended/deleted accounts return `401 invalid-access-token`.
An unverified account returns `403 unverified-account`; an invalid body returns `422 validation-error`.
Retrying a successful deletion with an old JWT returns `401`. Errors use `application/problem+json`.

This is the Accounts-only slice of [#20](https://github.com/software-development-workshop/udesa-x/issues/20):
email, handle and password hash are retained and the identifiers stay reserved. It does not
implement complete erasure, mobile confirmation, follow cleanup, feed filtering, or deleted-author
display in replies/reposts. The [approved design](docs/designs/account-deletion.md) records the
remaining scope and retention decision; [ADR-0012](docs/adr/0012-limite-compartido-de-login-y-baja.md)
explains the shared lockout and its tradeoff.

The unit and PostgreSQL integration commands above cover deletion, old-session and link rejection,
shared failure budgets and races. Run integration tests only against a disposable test database;
the fixtures truncate its account tables. To exercise the running services, issue two sessions
for a verified test account and create a post, submit an incorrect confirmation, then confirm
with the current password. Both sessions must fail introspection and publishing afterward,
and the retained database row must have `deleted_at` set and `session_version` incremented.

## How we work

[`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) has the principles, the workflow, the
definition of done and what the assignment fixes for us. Read it before opening a pull
request. Decisions already taken live in [`docs/adr/`](docs/adr).

Pending work is tracked on the
[Tasks board](https://github.com/orgs/software-development-workshop/projects/1). A task that
is not on the board does not exist.
