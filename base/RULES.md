# RULES.md — VN3DS-CHARM Project Rules

> These are project-specific constraints layered on top of the Agent Factory
> template's own `base/RULES.md` (source-of-truth/lifecycle rules, file access
> rules). This file adds rules specific to VN3DS-CHARM's two-language, hardware-
> constrained shape.

## Source of Truth & Lifecycle Mode

Same as the factory template: read the `## Project Mode` marker at the top of
`GAME-PLAN.md` before any work. **This project currently opens in BUILD mode.**
`GAME-PLAN.md` / `PHASES.md` is canonical until cutover (planned: end of rework
phase R4 — see `orchestrator/CUTOVER.md`). `docs/REWORK-PLAN.md` is the active
queue and its decision log overrides older decisions where they differ.

## Language boundary rule

1. **Witch (the converter) is Python. Enchantment (the engine) is C (C17).**
   Game logic runs on the 3DS as MicroPython bytecode compiled by Witch,
   together with the `renpy` shim package (`docs/REWORK-PLAN.md` §6). The
   engine core is C; Python on the device is limited to game code and the
   shim. Anything both sides need to agree on belongs in the bundle schema
   (ADR-007), one definition shared by both, not duplicated.
2. **The old pipeline is frozen** (the MoonScript engine under `src/engine/`
   and the old parser/emitter, ADR-003, superseded by ADR-005). No fixes or
   features go into it; it is removed in R9.
3. **The 3DS never parses `.rpy` or any other source-engine format** (Ren'Py,
   KiriKiri KAG, NScripter, TyranoScript, RealLive `.seen`). All parsing happens in
   Witch on desktop. This applies to every front end too.

## Hardware constraint rules

4. **All memory/CPU budgets are written and tested against Old 3DS**, not New 3DS.
   Old 3DS: 64MB app memory by default, 72/80/96MB modes for a CIA; 268MHz ARM11;
   PICA200 GPU. New 3DS gets the upside (more memory, faster CPU, H.264 video)
   but every feature must run well on Old 3DS.
5. **Memory budgets are the per-pool figures in `docs/REWORK-PLAN.md` §11**, set
   from hardware measurements in phase H and R3. Any engine change that risks
   exceeding them must be flagged for review, not merged silently.
6. **The PICA200 has no programmable fragment shaders, but that doesn't make
   effects impossible.** Its texture combiners, blend modes, stencil and render
   targets cover most 2D effects (`docs/REWORK-PLAN.md` §7.3). An effect is only
   flagged in the Problem Report after the routes there have been ruled out.
7. **Azahar Old 3DS profile is the default test target** for every iteration,
   after the desktop runner. New 3DS and real hardware validation happen at
   phase boundaries, and in phase H.

## Problem Report integrity rules

8. **Never silently drop or miscompile an unsupported construct.** Every
   unsupported construct must produce a Problem Report entry with its source
   location, the source snippet, a message and a suggestion.
9. **Witch must exit non-zero if the bundle verifier fails**: a damaged bundle,
   or any reachable crash, stuck or missing-content item (`docs/REWORK-PLAN.md`
   §13). This gates build scripts and CI.
10. **DLC and multi-engine front ends follow the same merge-at-convert-time model**
    (spec §8.1) — no runtime DLC/engine-detection logic in Enchantment.

## Content rules

11. **Nekopara work targets the SFW Steam version only.** The NSFW patch is out of
    scope; do not reference, extract, or plan around it (see spec §11.9).
12. **Source acquisition is confirmed per-game before that game's converter run.**
    Do not fetch, download, or reference pirated copies of any target game.

## Git identity rule (carried from agent-factory template)

13. Repo-level git identity only, confirmed against the intended GitHub owner
    before any push. This machine has more than one GitHub account in use.
