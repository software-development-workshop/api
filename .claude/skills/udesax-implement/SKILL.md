---
name: udesax-implement
description: Use after a person has approved a design, to take it to open pull requests. Never run it before udesax-design — an approved design is its only valid input.
---

# Take an approved design to open pull requests

Your input is a design someone approved. If there is no such design, stop and use the
udesax-design skill instead.

## Start from the board

Convert the draft card into an issue in this repository, assign it, and move it to
**In progress**. Branch as `<type>/<slug>`; the issue number is not part of the name.

## Split into pull requests that each run

Cut **vertically**. A pull request that adds only a repository, or only a model, delivers
nothing anyone can exercise, and a reviewer cannot judge it on anything but style.

Each pull request should deliver a capability that can be tried, even if the story is not
finished. Between two of them the trunk can be in a partial state — an endpoint whose
follow-up does not exist yet — and that is the normal price of small pull requests. Say so in
the body rather than hiding it.

Do not split what nobody can review separately. Two pull requests are better than one when
each stands alone, and worse when the second only makes sense after reading the first.

## Split into commits that stand alone

One commit, one logical change. **A commit must pass the whole gate by itself**, not merely
leave the branch green at the end.

That is a real constraint, not a formality: it is what makes `revert` and `bisect` work. It
also rules out the shortcut of writing everything and tidying up afterwards — a commit whose
only content is cleaning up the previous one means the previous one was wrong. When rewriting
history, write each file in its final form inside the commit that introduces it.

Verify it: check out each commit in turn and run the gate against what **that commit's**
workflow defines. A commit that only passes with later commits applied is not atomic.

## Run the gate before every commit

```bash
cd services/<service>
uv run ruff format --check . && uv run ruff check .
uv run pytest tests/unit --cov=src --cov-fail-under=85
uv run pytest tests/integration
```

Never lower the threshold and never delete a failing test to get past it. If coverage falls
short, the code that is missing tests either needs them or should not be in this commit. If
the change is genuinely blocked, say it is blocked.

## Verify end to end, not only through tests

Green tests prove the code does what the tests say, not what the story needs. Run it for
real: start the stack, drive the actual flow, look at the database, open the link the way a
user would.

This is where the failures that tests are blind to show up — a link that cannot be opened
from where it is sent, a value stored in a shape nothing downstream expects. Every
acceptance criterion gets exercised this way, and what you did goes in the pull request body
so someone else can repeat it.

## Write the pull request body

In Spanish. What changed, **why this option and not the others**, and how it was verified —
with the end-to-end run, not just a test count.

Link the issue and leave the design inventory there. What belongs here is what the inventory
could not know: why the work was split into these pull requests, why this order, and any
decision that only came up while building. If one of those turns out to outlive the sprint
and to have had real alternatives, it earns an ADR like any other.

Name what you deliberately left undone, and why.

Never reference repositories outside this one. The reasoning has to stand on its own here.

## Then stop

Move the card to **In review**. You do not approve and you do not merge: approval is a person
assigning responsibility for having read the code, and it is not yours to give.

## Red flags

| Thought | Reality |
|---|---|
| "I will split the commits at the end" | Then the split follows the diff, not the reasoning. Commit as you go |
| "The tests pass, it works" | The tests pass. Whether it works is a separate question, and you have to go look |
| "This commit is small, it can ride along" | Unrelated work in a commit makes the revert drag it with it |
| "Coverage is just below, I will drop the threshold" | The threshold is the requirement. The missing tests are the work |
| "A cleanup commit at the end will tidy this" | A cleanup commit is evidence the earlier ones were wrong |
