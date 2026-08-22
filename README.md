# UdeSA-X

Mobile-first social platform, built for Taller de Desarrollo de Software (UdeSA).

The services live here, one directory each under `services/`. Every service is
containerised and owns its own database; they share a repository, not a runtime.

## Services

| Service | Stack | Port |
|---|---|---|
| [accounts](services/accounts) | Python 3.13 + FastAPI | 8000 |

## Run it

From a clean clone, with Docker running:

```bash
docker compose up --build
```

The API docs are then at <http://localhost:8000/docs>.

## Work on a service

Each service is a self-contained `uv` project.

```bash
cd services/accounts
cp .env.template .env      # then fill it in; the compose values below work locally
uv sync
uv run pytest tests/unit
```

The integration tests need the database. `compose.yaml` publishes it on **5433**, so it does
not collide with a Postgres already running on the default port:

```bash
docker compose up -d accounts-db
cd services/accounts
DB_HOST=localhost DB_PORT=5433 DB_NAME=accounts DB_USER=accounts DB_PASSWORD=accounts \
  uv run pytest tests/integration
```

To run the service against that database, with migrations applied:

```bash
uv run alembic upgrade head
uv run uvicorn accounts.main:app --reload
```

## How we work

Short-lived branches off `main`, one per issue, named `<type>/<issue>-<slug>`. Nothing
reaches `main` without a pull request approved by someone other than its author, and CI has
to be green: format, lint, 85% unit coverage, integration tests.

A pull request body says what changed, why that option and not the others, and how it was
tested. Design decisions with real alternatives and consequences that outlive the sprint get
an ADR under [`docs/adr/`](docs/adr); everything else lives in the pull request that made
the decision.

Pending work is tracked on the
[Tasks board](https://github.com/orgs/software-development-workshop/projects/1). A task that
is not on the board does not exist.
