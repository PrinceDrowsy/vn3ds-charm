# CUTOVER.md — The BUILD → MAINTENANCE Handoff (VN3DS-CHARM)

> The cutover is the one-way event that ends factory-driven BUILD mode and hands
> execution to the issues-driven Ralph loop in MAINTENANCE mode. It is performed
> by the Orchestrator only.

## This project's planned cutover point

**End of rework phase R4** (`docs/REWORK-PLAN.md` §15): Jisei, Mice Tea and
Life After Magic play end to end on Enchantment on Old 3DS hardware. This is
pre-marked in the header comment at the top of `GAME-PLAN.md`.

Rationale: by the end of R4, Witch and Enchantment will have been proven on
three real games across the whole core: harvest, logic, scene, rendering,
text, audio, saves and rollback, displayables and framing. Everything after
(the full screen runtime and dual-screen layouts, video, puppets, packaging,
new front ends, new ports) is incremental and independently verifiable. Each
is its own sliceable unit of work, well suited to issue-based, overnight
Ralph-loop execution, rather than needing the coordinating factory loop's
whole-picture view.

This is a plan, not an automatic trigger — the Orchestrator (or a human) still
evaluates the actual state of the project against the checklist below when
R4's exit criteria are met, rather than cutting over blindly on a date.

## Cutover checklist (Orchestrator performs)

1. **Confirm green baseline.**
   - Witch's and Enchantment's test suites green; the bundle verifier passes
     on all three games' bundles.
   - R4's exit criteria (`docs/REWORK-PLAN.md` §15) met.
   - Memory stays within the §11 budgets on Old 3DS throughout a full
     playthrough of each of the three games, measured on hardware.
   - `GAME-PLAN.md` / `PHASES.md` checkboxes match reality.

2. **Confirm the maintenance workflow docs exist.**
   - `docs/ai/agent-workflow.md` already exists in this project (pre-dates the
     factory) and defines GitHub Issues as canonical, branch naming (`ai/issue-
     <number>-<slug>`), PR rules, and the AFK eligibility labels (`ai:ready` +
     `ai:afk`). Confirm it's still accurate; update the "GitHub Issues are
     canonical" line to explicitly note it's canonical **from cutover onward**,
     not from project start (it was written before the BUILD/MAINTENANCE
     distinction existed).
   - `docs/ai/vn3ds-issue-slicing-plan.md` already exists and can inform how
     Phase 3+ work items get sliced into issues.

3. **Generate the initial issue backlog from remaining plan items.**
   - For every unchecked item in rework phases R5–R9 and the front ends after
     them (`docs/REWORK-PLAN.md` §14–15), plus any still-relevant item in
     `GAME-PLAN.md`, create a GitHub Issue.
   - Use `to-issues` / `prd-to-issues` if available, referencing
     `VN3DS-spec.md`'s relevant section and the `GAME-PLAN.md` item.
   - Apply `ai:ready` + `ai:afk` only to issues that are genuinely unattended-safe:
     clear acceptance criteria, no proprietary game-asset acquisition step, no
     hardware-only validation as a blocking step. Issues requiring source
     acquisition for a new target game (`base/RULES.md` rule 12) or real Old
     3DS hardware validation should stay `ai:planned`/`ai:triage` until that
     precondition is met by a human.
   - Each issue links back to `VN3DS-spec.md` and the relevant ADR if applicable.

4. **Flip the mode marker.**
   - Change the header at the top of `GAME-PLAN.md` to:
     `## Project Mode: MAINTENANCE (cutover: <YYYY-MM-DD>)`

5. **Log the cutover.**
   - Append a cutover note to `learning/METRICS-HISTORY.md`: date, final
     R0–R4 metrics, number of issues generated, first batch marked `ai:ready`+`ai:afk`.

6. **Stop driving.**
   - The Orchestrator stops running BUILD cycles against this tree. The Ralph
     loop reading GitHub Issues owns execution from here.

## After cutover

- `GAME-PLAN.md` remains as the historical build record and mode marker; it is
  no longer the work queue.
- New work (R5+ items, bug fixes, new game ports) is filed as issues,
  grilled/sliced as needed, labelled, and picked up by the Ralph loop.
- If a large new BUILD-mode push is ever needed again (e.g. the Phase 5.5
  Triage Workbench turns out to need cross-cutting factory-style coordination),
  a human may explicitly revert the marker to `## Project Mode: BUILD`, run a
  focused Phase P pass for that scope (see `orchestrator/PLANNING.md`), and
  re-enter the factory loop — then cut over again when that push is done.

## Reversibility

One-way by default, reversible only by explicit human action. No teammate
agent, and no autonomous Orchestrator decision, may flip MAINTENANCE back to
BUILD without a human in the loop.
