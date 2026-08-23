---
name: udesax-design
description: Use before writing any code — a new feature, a change in behaviour, a bug with more than one plausible cause, a spike. Turns a board card into a design a person has approved, and stops there.
---

# Turn a card into an approved design

Your output is an approved design, not code. Nothing gets implemented until a person says
yes to what you propose.

<HARD-GATE>
Do NOT write code, scaffold anything, create a branch or invoke the udesax-implement skill until
you have stated what you intend to build and a person has approved it. The size of the
design scales with the task. The approval never does.
</HARD-GATE>

## Before the first question

**The card has to be on the board.** Work that is not on
[Tasks](https://github.com/orgs/software-development-workshop/projects/1) does not exist. If
there is no card, the first thing to settle is whether to open one — not how to build it.

Then read, in this order: the issue and every one of its acceptance criteria, the code the
change touches, and `docs/CONTRIBUTING.md`. Acceptance criteria are graded individually, so
never merge or paraphrase them.

## Classify, and say it out loud

State the classification in your first message so it can be overridden.

| | When | Output |
|---|---|---|
| **Spike** | A feasibility question. "Can we", "is it possible", throwaway is fine | An answer and a recommendation. Anything built stays labelled throwaway |
| **Bounded** | A well-scoped change to a flow that already exists **in this repo** and you can read | A short design in chat, then implementation |
| **Architectural** | A new service, a new subsystem, anything that changes an interface others depend on | Questions, alternatives, a sectioned design, then implementation |

Bounded measures the repo, not your familiarity. If there is no existing flow to change, it
is not bounded. When torn between two, take the heavier one — and hidden complexity found
mid-task upgrades the path: stop and say so. Nothing ever downgrades.

## Ask one question per message

Prefer questions with concrete options, and lead with your recommendation and why. An
option is only worth listing with its real cost stated; an alternative presented without its
downside is not a choice, it is decoration.

Do not spend questions on details of something that should be decomposed first. If the
request is several independent pieces, say so before anything else and settle the order.

## Inventory the decisions before designing the solution

This is the step that matters most, and the one most easily skipped.

A feature hides a dozen decisions that never appear in the acceptance criteria: which
hashing function and with which parameters, which HTTP verb, what an error response looks
like, what the primary key is, what gets logged. **Any of them can be asked about out loud,
and "the agent chose it" is not an answer.**

So: list them, explicitly, before writing anything. For each one, decide and give the reason
in a sentence. Then sort them:

- **Earns an ADR** — only with defensible alternatives *and* consequences that outlive the
  sprint. Two halves, both required.
- **Stays in the inventory** — most of them.
- **Not a decision at all** — it follows mechanically from an acceptance criterion.

Where the assignment is ambiguous, do not pick silently. Name the ambiguity, choose, and say
why that reading.

## Post the inventory on the issue

Once a person has approved the design, post the inventory as a **comment on the issue**,
in Spanish, before any implementation starts.

The issue, not a pull request body. The inventory exists before there is a branch, so
holding it until a pull request leaves it living only in a chat log for as long as that
takes. And a story usually ships as several pull requests, which would scatter decisions
by wherever the code happened to land — while the ones that change no code at all, like
something deliberately deferred, would have nowhere to go.

The issue is the unit of the story and the thing the board points at, so that is where the
record of what was decided belongs. How it was carried out belongs in the pull requests.

## Present the design

Scale each section to its complexity. Cover: what changes, which files, how the work splits
into pull requests, how it will be verified, and the decision inventory above.

Say what you are deliberately **not** doing and why, or the omission reads as an oversight.

Then stop. Presenting a design and starting to build it in the same breath is skipping the
gate, however obvious the design looks.

## Red flags

| Thought | Reality |
|---|---|
| "Too simple to need approval" | Simple means a short design, not no design |
| "I understand this kind of app, so it is bounded" | Bounded measures the repo. A flow that does not exist yet is not bounded |
| "The design is obvious, I will start while they read" | The gate is the approval, not the design |
| "It grew, but I am almost done" | Hidden complexity upgrades the path. Stop and reclassify |
| "They approved the spike, so the follow-up is approved" | Every task gets its own classification and its own approval |
| "I will note the open decisions in the PR later" | A decision you did not notice is one you cannot defend |
