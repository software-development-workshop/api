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
uv sync
uv run uvicorn accounts.main:app --reload
uv run pytest
```

## How we work

Practices, conventions and templates live in
[ai-context](https://github.com/software-development-workshop/ai-context). Read them before
opening a pull request: they cover branching, commit format, the review contract, the
definition of done, and which language each artifact is written in.

Pending work is tracked on the
[Tasks board](https://github.com/orgs/software-development-workshop/projects/1). A task that
is not on the board does not exist.
