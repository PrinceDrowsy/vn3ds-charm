# CUTOVER.md — The BUILD → MAINTENANCE Handoff (VN3DS-CHARM)

> The cutover is the one-way event that ends factory-driven BUILD mode and hands
> execution to the issues-driven Ralph loop in MAINTENANCE mode. It is performed
> by the Orchestrator only.

## This project's planned cutover point

**End of Phase 2** (Hustle Cat playable end-to-end, Old 3DS profile, Azahar).
This is pre-marked in the header comment at the top of `GAME-PLAN.md`.

Rationale: by the end of Phase 2, the converter+engine pipeline will have been
proven on two real games (Jisei in Phase 1, Hustle Cat in Phase 2) across the
full core feature set — parsing, conversion, Problem Report, dual-screen
rendering, expression evaluation, save/load, and audio. Everything from Phase 3
onward (animation system, Live2D replacement, additional game ports, Phase 6
multi-engine converters) is naturally incremental and independently verifiable
— each is its own sliceable unit of work well suited to issue-based, overnight
Ralph-loop execution, rather than requiring the coordinating factory loop's
whole-picture view.

This is a plan, not an automatic trigger — the Orchestrator (or a human) still
evaluates the actual state of the project against the checklist below when
Phase 2's exit criteria are met, rather than cutting over blindly on a date.

## Cutover checklist (Orchestrator performs)

1. **Confirm green baseline.**
   - Converter `pytest` suite green; Engine `busted` suite green.
   - Hustle Cat's definition-of-done (`VN3DS-spec.md` §11.2) fully checked.
   - Memory in use stays under 70MB throughout an Azahar Old 3DS profile
     playthrough of at least one full Hustle Cat route.
   - `GAME-PLAN.md` / `PHASES.md` checkboxes for Phases 0–2 match reality.

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
   - For every unchecked item in Phases 3, 4, 5, 5.5, and 6 (a–e) in
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
   - Append a cutover note to `learning/METRICS-HISTORY.md`: date, final Phase
     0–2 metrics, number of issues generated, first batch marked `ai:ready`+`ai:afk`.

6. **Stop driving.**
   - The Orchestrator stops running BUILD cycles against this tree. The Ralph
     loop reading GitHub Issues owns execution from here.

## After cutover

- `GAME-PLAN.md` remains as the historical build record and mode marker; it is
  no longer the work queue.
- New work (Phase 3+ items, bug fixes, new game ports) is filed as issues,
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
