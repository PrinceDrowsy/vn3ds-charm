# AGENTS.md — VN3DS-CHARM Agent Factory

> This file is the root configuration for the Agent Factory as applied to
> VN3DS-CHARM. Every agent session (lead or teammate) loads this file
> automatically. It defines the system of record for how agents collaborate,
> what they can touch, and how the loop works.
>
> This is VN3DS-CHARM's adapted copy of the `agent-factory` template
> (see `C:\Source\agent-factory`). Project-specific content lives here;
> generic factory mechanics are inherited from the template's design.
> Full technical detail lives in `VN3DS-spec.md` — this file is the
> factory-facing summary.
>
> **The rework in `docs/REWORK-PLAN.md` is the active queue.** Its decision
> log overrides `VN3DS-spec.md`, `base/ARCHITECTURE.md` and the `stack/` docs
> wherever they still describe the old LÖVE Potion/MoonScript pipeline; those
> are rewritten in rework phase R9.

## System Overview

VN3DS-CHARM uses a multi-agent autonomous development loop. Multiple specialized
agents collaborate to build a two-part toolchain — Witch, a Python converter,
and Enchantment, a native C engine for 3DS with embedded MicroPython — each
agent constrained to its role, looping until acceptance criteria are met.

**The three primitives that govern every cycle:**
1. **Editable Asset** — `/src` (converter, engine, triage-ui) and `/tests`
2. **Scalar Metrics** — Build success (bool), test pass rate (%), security issues (count), memory-budget compliance (bool, Old 3DS)
3. **Time-boxed Cycle** — Each agent gets a fixed task scope per cycle; the orchestrator evaluates after all agents complete

## File Hierarchy — READ THIS FIRST

```
base/                   ← Layer 1: WHAT to build (immutable during runs)
  PROJECT.md            ← Product vision, user stories, Definition of Done
  ARCHITECTURE.md       ← System design, component boundaries, data contracts
  RULES.md              ← Global constraints (language boundary, hardware, content)
  ENVIRONMENT.md        ← Dev machine, toolchains, Azahar, devkitPro

stack/                  ← Layer 2: WITH WHAT to build
  STACK-CONVERTER.md    ← Python converter: parser, emitters, asset pipeline
  STACK-ENGINE.md       ← old MoonScript engine (frozen; rewritten for C in R9)
  STACK-TRIAGE-UI.md    ← Python Triage Workbench (Phase 5.5+)
  STACK-TESTING.md      ← pytest (converter) + busted (engine), regression corpora

agents/                 ← Layer 3: HOW each agent behaves (role definitions)
  AGENT-ORCHESTRATOR.md
  AGENT-DEVELOPER.md
  AGENT-TESTER.md
  AGENT-SECURITY.md
  AGENT-DOCUMENTATION.md

learning/               ← Layer 4: REMEMBER across cycles
  RETROSPECTIVE.md      ← Post-phase lessons learned
  SKILLS-LOG.md         ← Patterns and techniques discovered
  METRICS-HISTORY.md    ← Scalar metrics over time

orchestrator/           ← Loop control and evaluation logic
  PLANNING.md           ← Phase P: grill-first planning (already complete for this project)
  CUTOVER.md            ← BUILD → MAINTENANCE handoff (pre-marked for end of rework phase R4)
  loop-config.md        ← Loop parameters: max cycles, metric thresholds
  SKILLS-DISCOVERY.md   ← Phase 0: find and install relevant skills

src/                    ← Production code (agent WRITE target)
  converter/            ← Python converter (old pipeline, frozen; Witch replaces it)
  engine/               ← MoonScript engine (old pipeline, frozen; removed in R9)
  triage-ui/            ← Python Triage Workbench (Phase 5.5+, not yet scaffolded)
                          Witch's and Enchantment's own directories are laid out
                          in R0 (bundle schema) and R3 (engine core).

tests/                  ← Test code (Tester WRITE target)
  security-reports/     ← Security agent output directory
```

No UI-Reviewer role or `/design` reference-mockup layer — VN3DS-CHARM has no
traditional web frontend. Visual/gameplay validation happens via Azahar
(Old 3DS profile) at phase boundaries, per `stack/STACK-TESTING.md`.

## Agent Access Control Matrix

| Agent         | /src | /tests | /docs | /base | /stack | /learning | Root trackers | Can run builds | Can run tests |
|---------------|------|--------|-------|-------|--------|-----------|----------------|----------------|---------------|
| Orchestrator  | READ | READ   | READ  | READ  | READ   | WRITE     | WRITE to PHASES.md, GAME-PLAN.md | YES | YES |
| Developer     | WRITE| READ   | NO    | READ  | READ   | READ      | NO             | YES            | NO            |
| Tester        | READ | WRITE  | NO    | READ  | READ   | READ      | NO             | NO             | YES           |
| Security      | READ | WRITE to security-reports only | NO | READ | READ | READ | NO | NO | YES |
| Documentation | READ | READ   | WRITE | READ  | READ   | READ      | WRITE to README.md, CHANGELOG.md | NO | NO |

**CRITICAL RULE**: If an agent modifies a file outside its WRITE permissions, the
orchestrator MUST reject that cycle's output and revert the change.

> **Orchestrator tracker exception:** The Orchestrator may write the root-level
> progress trackers `PHASES.md` and `GAME-PLAN.md` during the LOG phase only.
> These are bookkeeping, not cycle output, and do NOT count as access violations.

## Project Lifecycle — Two Modes, One Cutover

```
  PLANNING → BUILD mode ──cutover──▶ MAINTENANCE mode
  (done)     (factory drives)         (issues + Ralph loop drive)
```

**Current status: BUILD mode.** See the `## Project Mode` marker at the top of
`GAME-PLAN.md`. `GAME-PLAN.md` / `PHASES.md` is canonical; GitHub Issues are NOT
the queue yet.

**Planned cutover: end of rework phase R4** (Jisei, Mice Tea and Life After
Magic playable end to end on Enchantment). At that point Witch and Enchantment
are proven on three real games, and R5 onward becomes incremental
per-feature/per-game work suited to issue-sliced execution.
See `orchestrator/CUTOVER.md` for the full trigger and checklist. The cutover is
Orchestrator-only; no teammate agent flips the mode marker.

## The Loop Protocol (BUILD mode)

P. **PLAN THE PROJECT** (Phase P) — **Already complete for this project.**
   `base/PROJECT.md`, `base/ARCHITECTURE.md`, three ADRs (`docs/adr/ADR-001`
   through `ADR-003`), and `GAME-PLAN.md` (opening `## Project Mode: BUILD`)
   were generated from `VN3DS-spec.md` and the pre-existing `docs/ai/` planning
   docs. See `orchestrator/PLANNING.md` for the gate definition (for reference —
   it does not need to be re-run).
0. **DISCOVER** (Phase 0, once) — Search skills registries for Python/MoonScript/
   Lua/LÖVE Potion relevant skills. Install approved skills. See
   `orchestrator/SKILLS-DISCOVERY.md`.
1. **PLAN** — Orchestrator reads `base/PROJECT.md` + `docs/REWORK-PLAN.md` +
   `GAME-PLAN.md`, selects the next unchecked work item.
2. **BUILD** — Developer agent implements the work item, commits to a feature
   branch. (Witch is Python; Enchantment is C — see `base/RULES.md` language
   boundary rule.)
3. **VERIFY** — Tester and Security run in parallel after Developer commits.
4. **EVALUATE** — Orchestrator collects metrics from all agents.
5. **DECIDE** — KEEP or REVERT (see `orchestrator/loop-config.md` thresholds).
6. **DOCUMENT** — Documentation agent updates changelog/docs (ONLY on KEEP).
7. **LOG** — Append cycle results to `learning/METRICS-HISTORY.md` + `SKILLS-LOG.md`.
8. **LOOP OR STOP / CUT OVER** — Check phase exit criteria. If R4 completes,
   evaluate cutover per `orchestrator/CUTOVER.md`.

## How to Start a Session

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
# The orchestrator is always the lead session.
# It reads this file, then base/PROJECT.md, then GAME-PLAN.md, then spawns teammates.
# See agents/AGENT-ORCHESTRATOR.md for the full startup protocol.
```

If Claude usage limits are reached, stop only at a clean checkpoint: after a
cycle decision has been logged and `GAME-PLAN.md` / `PHASES.md` checkoffs are
current. Another runner can resume from this file and the current target in
`GAME-PLAN.md`.

## Conventions

- All agent communication goes through the shared task list, never direct file mutation
- Every code change is a single atomic commit with a descriptive message
- Metrics are always appended, never overwritten
- When in doubt, the orchestrator decides
- No agent may modify files in `/base` or `/stack` during a run
- Read the `## Project Mode` marker at the top of `GAME-PLAN.md` before doing anything
- Witch (Python) and Enchantment (C) are separate languages — never blur the boundary (`base/RULES.md`)
- The old MoonScript engine and old parser/emitter are frozen: no fixes or features (D22)
- All hardware budgets are tested against Old 3DS, not New 3DS (`base/RULES.md`)
