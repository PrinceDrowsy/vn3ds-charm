# RULES.md — VN3DS-CHARM Project Rules

> These are project-specific constraints layered on top of the Agent Factory
> template's own `base/RULES.md` (source-of-truth/lifecycle rules, file access
> rules). This file adds rules specific to VN3DS-CHARM's two-language, hardware-
> constrained shape.

## Source of Truth & Lifecycle Mode

Same as the factory template: read the `## Project Mode` marker at the top of
`GAME-PLAN.md` before any work. **This project currently opens in BUILD mode.**
`GAME-PLAN.md` / `PHASES.md` is canonical until cutover (planned: end of Phase 2,
once Hustle Cat is playable — see `orchestrator/CUTOVER.md`).

## Language boundary rule

1. **The Converter is Python. The Engine is MoonScript (compiled to Lua).** Never
   write engine logic in Python or converter logic in MoonScript/Lua. If a piece of
   logic seems to want to live in both, it belongs in the bundle contract
   (`script.vnds` / `manifest.json` / `problems.json`), not duplicated.
2. **Engine agents edit `.moon` source files only.** The generated Lua under any
   build/compile output directory is a build artifact, never hand-edited, and
   should be gitignored. See ADR-003.
3. **The 3DS never parses `.rpy` or any other source-engine format** (Ren'Py,
   KiriKiri KAG, NScripter, TyranoScript, RealLive `.seen`). All parsing happens in
   the Converter on desktop. This applies to every Phase 6 converter module too.

## Hardware constraint rules

4. **All memory/CPU budgets are written and tested against Old 3DS**, not New 3DS.
   Old 3DS: 128MB total RAM (~80–90MB usable), 268MHz ARM11, PICA200 GPU. New 3DS
   runs the same content with headroom and needs no separate budget analysis.
5. **Hard memory ceiling: 70MB in use during gameplay. Target: ≤45MB.** Any engine
   change that risks exceeding this must be flagged for review, not merged silently.
6. **No shader/fragment effects.** PICA200 is fixed-function. Blur, glow, colour
   grading, mesh deformation are hardware-impossible — do not attempt to implement
   them; flag as `manual` in the Problem Report instead (spec §6, §9.2).
7. **Azahar Old 3DS profile is the default test target** for every iteration. New
   3DS profile and real hardware validation happen at phase boundaries only.

## Problem Report integrity rules

8. **Never silently drop or miscompile an unsupported construct.** Every construct
   outside the supported subset (spec §6) must produce a `problems.json` entry with
   `source`, `ren_py` (or equivalent source snippet), `message`, and `suggestion`.
9. **The converter must exit non-zero if any `blocking` Problem Report item
   exists.** This gates build scripts and CI.
10. **DLC and multi-engine converters follow the same merge-at-convert-time model**
    (spec §8.1) — no runtime DLC/engine-detection logic in the Engine.

## Content rules

11. **Nekopara work targets the SFW Steam version only.** The NSFW patch is out of
    scope; do not reference, extract, or plan around it (see spec §11.9).
12. **Source acquisition is confirmed per-game before that game's converter run.**
    Do not fetch, download, or reference pirated copies of any target game.

## Git identity rule (carried from agent-factory template)

13. Repo-level git identity only, confirmed against the intended GitHub owner
    before any push. This machine has more than one GitHub account in use.
