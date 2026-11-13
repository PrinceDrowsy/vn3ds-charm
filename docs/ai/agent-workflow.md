# AI Agent Workflow

> **Scope note (added when the Agent Factory / BUILD-MAINTENANCE lifecycle was
> adopted):** This workflow describes **MAINTENANCE mode**. It becomes
> canonical **from the project's cutover onward** (planned: end of Phase 2 —
> see `orchestrator/CUTOVER.md`), not from project start. Before cutover, the
> project runs in **BUILD mode**, where `GAME-PLAN.md` / `PHASES.md` is
> canonical and the Agent Factory loop (see `AGENTS.md`) drives work — GitHub
> Issues are not yet the queue. Read the `## Project Mode` marker at the top of
> `GAME-PLAN.md` to know which regime is currently active.

GitHub Issues are the source of truth for this project **once in MAINTENANCE
mode**.

Hermes Kanban may mirror issue state, but the issue body, labels, linked docs, branches, and pull requests are canonical.

## Labels

- ai:triage - Needs planning or clarification.
- ai:planned - Plan exists but task is not ready for autonomous work.
- ai:ready - Ready for agent execution.
- ai:afk - Safe for unattended work.
- ai:blocked - Agent is blocked and needs human input.
- ai:needs-review - Agent completed work and needs human review.

## AFK rule

Only issues with both labels may be worked by the night loop:

- ai:ready
- ai:afk

Issues labeled ai:blocked or risk:high must not be worked unattended.

## Agent branch rule

Use this branch format:

ai/issue-<number>-<short-slug>

## Agent PR rule

Every PR must include:

Fixes #<issue-number>

## Failure behavior

If the agent cannot complete the issue after two focused repair attempts, it must stop, comment on the issue, and apply ai:blocked.
