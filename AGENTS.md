# udesa-x

UdeSA-X is a social platform shaped like X: users post, reply, repost, like, follow and get
notified. A mobile app serves end users, a web backoffice serves administrators, and a set of
microservices sits behind both. It is built over one semester for a university software
development workshop, one week at a time.

The services live under `services/`, one directory each. They share a repository, not a
runtime: each owns its container, its database and its CI job.

This file is a map. It is loaded on every conversation, so it stays short — the rules
themselves live one link away.

## Services

| Service | Stack | Directory | Port |
|---|---|---|---|
| accounts | Python 3.13, FastAPI, PostgreSQL | `services/accounts` | 8000 |

## Commands

From a service directory:

```bash
uv sync
uv run ruff format . && uv run ruff check .
uv run pytest tests/unit --cov=src --cov-fail-under=85
uv run alembic upgrade head
```

Integration tests need a running database and the service settings in the environment;
`README.md` has the exact invocation and the compose setup. Never guess environment
variables — every one a service reads is listed in its `.env.template`.

## How the work is split

The product is cut into five epics, and every user story belongs to one:

| | Epic | | Epic |
|---|---|---|---|
| E.1 | Users | E.4 | Notifications |
| E.2 | Posts | E.5 | Administrators (backoffice) |
| E.3 | Social interactions | | |

Cards are named by epic and story number — `E1S1 User Registration`, `E2S4 Reply to a Post` —
and carry the acceptance criteria as a checklist. **Criteria are graded one by one, so never
merge, reword or skip one.**

Everything lives on the [Tasks board](https://github.com/orgs/software-development-workshop/projects/1).
Work that is not on it does not exist.

| Column | Meaning |
|---|---|
| Backlog | known, not committed to an iteration |
| Ready | committed for this iteration |
| In progress | someone is working on it, and that someone is the assignee |
| In review | the pull request is open |
| Done | the pull request is merged |

Cards also carry `Optional/Mandatory` — every mandatory story has to ship, optional ones earn
points — plus a `Size` from XS to XL and an `Iteration`.

Iterations are one week. The sprint is reviewed and the next one planned every Monday, so a
branch that outlives its iteration is a branch that was estimated wrong. A release is tagged
before each of those meetings.

## How work happens here

1. The card exists on the board, with its acceptance criteria.
2. `.claude/skills/udesax-design/SKILL.md` — turn the card into a design a person approves.
3. A person approves. This step is not yours to skip or to perform.
4. `.claude/skills/udesax-implement/SKILL.md` — take the approved design to open pull requests.

Read those two files even if your tooling does not load skills on its own. They are ordinary
markdown and they are the process, not a suggestion.

## Where the rules live

| Topic | Where |
|---|---|
| Principles, workflow, definition of done, language, what the assignment fixes, when a decision earns an ADR | [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) |
| Decisions already taken, with their alternatives and consequences | [`docs/adr/`](docs/adr) |
| Running the project from a clean clone | [`README.md`](README.md) |

Do not restate those rules here. Two copies of a rule means one of them is stale and nobody
knows which.

## Non-negotiable

- You do not open, approve or merge a pull request. You prepare the branch and the body; a
  person decides. Approval is someone taking responsibility for having read the code.
- No code before a person approves a design. However obvious the change looks.
- Never lower a coverage threshold, delete a failing test, or weaken an assertion to get past
  CI. Fix the code, or say the change is blocked.
- Never commit a secret. Not in code, not in config, not in a test fixture.
- Everything you write has to be explainable by the person whose name goes on the pull
  request. If a solution needs an abstraction they would struggle to defend, choose the
  simpler one.
