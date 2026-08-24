# UdeSA-X

Mobile-first social platform, built for a university software development workshop.

The services live here, one directory each under `services/`. Every service is
containerised and owns its own database; they share a repository, not a runtime.

## Services

| Service | Stack | Port |
|---|---|---|
| [accounts](services/accounts) | Python 3.13 + FastAPI | 8000 |

## Run it

From a clean clone, with Docker running:

PowerShell:

```powershell
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$env:JWT_SECRET = [Convert]::ToBase64String($bytes)
docker compose up --build
```

On a POSIX shell, use `export JWT_SECRET="$(openssl rand -base64 32)"` before the same
Compose command. The value is local and must never be committed.

The API docs are then at <http://localhost:8000/docs>, and the verification emails land in
the Mailpit inbox at <http://localhost:8025> — nothing leaves the machine while developing.

## Work on a service

Each service is a self-contained `uv` project.

```bash
cd services/accounts
uv sync
uv run pytest tests/unit          # no configuration needed
```

The integration tests need the database. `compose.yaml` publishes it on **5433**, so it does
not collide with a Postgres already running on the default port:

```bash
JWT_SECRET=integration-test-jwt-secret-32-bytes-minimum docker compose up -d accounts-db
cd services/accounts
DB_HOST=localhost DB_PORT=5433 DB_NAME=accounts DB_USER=accounts DB_PASSWORD=accounts \
  SMTP_HOST=localhost SMTP_PORT=1025 SMTP_FROM=no-reply@udesa-x.dev \
  PUBLIC_BASE_URL=http://localhost:8000 \
  JWT_SECRET=integration-test-jwt-secret-32-bytes-minimum \
  uv run pytest tests/integration
```

To run the service against that database, with migrations applied:

```bash
uv run alembic upgrade head
uv run uvicorn accounts.main:app --reload
```

## How we work

[`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) has the principles, the workflow, the
definition of done and what the assignment fixes for us. Read it before opening a pull
request. Decisions already taken live in [`docs/adr/`](docs/adr).

Pending work is tracked on the
[Tasks board](https://github.com/orgs/software-development-workshop/projects/1). A task that
is not on the board does not exist.
