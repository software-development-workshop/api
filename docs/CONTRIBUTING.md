# Contributing

How code gets written here, and how it reaches `main`. Read this before opening a pull
request. It is loaded on demand, not on every turn, so it can afford to be specific — but
every line still competes with the task, so it stays as short as it can be.

## Principles

### Where simplicity does not apply

Read this first or the rest will argue against the requirements. The assignment fixes the
shape of the system, and none of it is open to simplification:

- The end-user application is **mobile only**. The backoffice is a **web** application, for
  administrators only.
- The backend is **microservices**, decoupled and independently deployable.
- **At least two kinds of database** across the system. Which two, and which data lives in
  each, is ours to choose and ours to defend.
- The backend **cannot be a single technology**. At least two languages or frameworks.
- Every service is **containerised** and deployed to a cloud environment.
- Security follows the **OWASP Top 10** as its reference.
- Testing at three levels: **unit, integration and load**. Unit coverage is **at least 85%
  per service**, frontend included, enforced in CI.
- **CI/CD on GitHub Actions**, covering build, test and deployment.
- **Observability**: metrics, logs and traces, reachable by someone outside the team.
- **Rate limiting** in at least one service.
- **At least one queue** carrying asynchronous traffic between two services.
- At least one feature built on **AI**, agreed beforehand.

Proposing a modular monolith because it is simpler is not a win, it is a failed requirement.
The same goes for putting everything in one database because one is easier to operate.

Simplicity applies **inside** a service. The shape of the system does not bend to it.

Several of these are still unmet — the queue and the rate limiter among them. That is fine
while it is deliberate and written down, and a problem the moment it is an oversight. When a
design defers one, say which and where it will land.

### Separation of concerns

Each layer does one job and calls only the layer below. `api` speaks HTTP, `service` holds
the rules, `repository` touches data. The service never returns a 404 — it does not know
HTTP exists, and that is what lets it be tested without a web server.

It pays off twice: swapping storage touches one file, and a small file is a small amount of
context to load before changing ten lines.

### KISS

Choose the simplest thing that satisfies the requirement. The requirement is the floor, not
the ceiling: above it, prefer the boring option — a table over a cache nobody asked for, a
synchronous call over an event bus, one query over a generic query builder.

Forbidden: abstractions with a single caller, configuration for something that never varies,
patterns added because they are good practice in general rather than because something here
needs them.

Exception: when the simple version breaks a stated non-functional requirement, the
requirement wins and the reason goes in the pull request.

### YAGNI

Build what the story asks for. Nothing for the story you imagine next. No interface with one
implementation, no plugin system for one provider, no flag nothing sets, no migration path
for a database you are not using.

When a rule is deliberately not applied yet, say so where someone will look, or the absence
reads as an oversight and gets "fixed".

### DRY

One fact lives in one place. It bites hardest on what has to agree between services that
share no code: the error contract, the shape of a token, a validation rule.

Exception: duplication across a service boundary is sometimes the right trade, because a
shared library couples deployments. Copy on purpose and write down that you did.

### Comments

Names carry the explanation. A variable called `d` pushes its meaning into a comment, and
comments rot while names get refactored.

Worth writing: a constraint that lives outside the file, why the obvious approach was not
taken, deliberate non-action. Not worth writing: what the next line does, history — git has
it — or a docstring because a linter wants one.

Agents over-comment by default. Deleting comments is part of reviewing generated code.

### You have to be able to explain it

Everything that reaches `main` has to be explainable by the person whose name is on the pull
request. A solution you can explain beats a better one you cannot. The bar is architecture
and flow — which layer calls which, how a request moves, why the data is shaped that way —
not line by line.

If a solution needs an abstraction you would struggle to defend, choose the simpler one.

## Workflow

### Branches

Trunk-based. `main` is the only long-lived branch. Everything else is `<type>/<slug>` —
`feat/user-registration`, `fix/jwt-expiry`, `docs/contributing-guide`.

No issue number in the name. The link to the issue is the `Closes #N` in the pull request,
which is where GitHub already shows it and where nobody has to copy it by hand.

A branch must not outlive the one-week sprint. If a story cannot land in a week it was
estimated wrong: split it.

### Commits

Conventional Commits, with the service as the scope: `feat(accounts): register an account`.

One commit, one logical change. A commit must build and pass the full gate **on its own**,
and be revertable without dragging unrelated work with it.

- Split unrelated work, even when it landed in the same sitting.
- Never bundle a refactor with a change in behaviour: land the refactor first.
- Mechanical sweeps — formatting, import order, mass renames — go in their own commit.
- The subject is imperative. The body says why, not what.

### Pull requests

Nothing reaches `main` without a pull request approved by someone who is not its author.

Split a story into pull requests that each deliver something that runs. Cut vertically, never
by layer: a pull request that adds only a repository delivers nothing anyone can try.

The body says what changed, **why this option and not the others**, and how it was tested.
The why is the part that matters: it is the same answer you will give out loud in the weekly
meeting.

Design decisions belong on the issue, not here — see below. A pull request explains how the
work was carried out; the issue records what was decided and why.

Anything decided in a call or in person gets written back into the pull request. It is the
only copy that survives.

### Definition of done

- [ ] Every acceptance criterion in the issue is met. They are graded individually.
- [ ] CI is green: format, lint, 85% unit coverage, integration tests.
- [ ] Integration tests cover the new interaction, if it crosses a boundary.
- [ ] The change was exercised end to end, not only through its tests.
- [ ] `README.md` still gets the service running from a clean clone.
- [ ] Every new environment variable is in `.env.template`. No secrets committed.
- [ ] The board card is in Done and the issue is closed.
- [ ] Approved by someone other than the author.

### Language

Spanish for what two people discuss: pull request bodies, review comments, ADRs. The why of
a change is argued out loud in Spanish, so writing it in English means writing it twice.

English for what an agent consumes and for code: source, names, comments, commit messages,
issues and their acceptance criteria, tests, and this file.

Product-facing text follows the product, not this rule: an email a user reads is in Spanish.

### ADRs

Most decisions belong in a comment on the issue, posted once the design is approved and
before implementation starts. The issue is the unit of the story: decisions are taken before
a branch exists, a story usually ships as several pull requests, and some decisions — what
was deliberately deferred — change no code at all and so fit in no diff.

A decision earns an ADR on top of that only when it has **defensible alternatives** and
**consequences that outlive the sprint**. Both halves are required: a choice with no real
alternative is a default, and a consequence that dies with the branch does not need its own
document.

The condition is strict because a log that grows on reflex goes stale, costs context on
every agent run, and eventually contradicts itself.

They live in `docs/adr/NNNN-titulo.md`, are numbered and immutable, carry a status
(propuesto / aceptado / rechazado), link the issue they came from, and are superseded by a
new one rather than edited.
