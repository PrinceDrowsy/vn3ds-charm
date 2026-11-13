# PROJECT.md — VN3DS-CHARM

**Project name:** VN3DS-CHARM
**Status:** Phase P complete; entering BUILD mode
**Authors:** Scott & PrinceDrowsy
**Full design reference:** `VN3DS-spec.md` (this file summarizes it into factory-consumable form; the spec remains authoritative on detail)

---

## Vision

Take a Ren'Py visual novel with available `.rpy` source and produce a playable
Nintendo 3DS build, targeting Old 3DS as the binding hardware constraint. A
desktop-side Converter (Python) transpiles the game's declarative script subset
into an extended VNDS format; a forked Engine (ajusa/VNDS-LOVE, MoonScript → Lua
on LÖVE Potion) plays it back with art on the top screen and dialogue/touch input
on the bottom screen. What can't be converted (arbitrary Python, custom screens,
mesh-deformation animation) is surfaced explicitly via a Problem Report, not
silently dropped or miscompiled.

The project ships against a phased catalogue of real target games (see
`VN3DS-spec.md` §11) and eventually extends the converter to non-Ren'Py VN engines
(§Phase 6).

## Who this is for

Scott and PrinceDrowsy, as a shared homebrew hobby project. Not for commercial
distribution — this is a personal toolchain for source-available or owned games.

## Core user stories

1. **As a developer**, I can point the Converter at a Ren'Py game's `game/` folder
   and get back a bundle (`script.vnds` + `manifest.json` + assets) plus a
   `problems.json` Problem Report enumerating everything that needs manual work.
2. **As a developer**, I can triage a Problem Report top-to-bottom, hand-fix only
   the flagged spots, and re-run the converter without re-reading the whole script.
3. **As a player**, I can load a converted bundle in Azahar (Old 3DS profile) or on
   real Old 3DS hardware and play the game start to finish — dual-screen layout,
   touch-to-advance, touch-selectable choices, save/load, streamed audio.
4. **As a developer**, I can see exactly why something didn't convert (source file,
   line, original snippet, suggested fix) rather than a silent miscompile or crash.
5. **(Phase 5.5) As a non-developer (e.g. PrinceDrowsy working solo on triage)**, I can
   resolve a Problem Report to zero blocking items using the Triage Workbench GUI
   without opening a terminal or hand-editing any file.

## Definition of Done (per phase)

Each phase in `GAME-PLAN.md` has its own exit criteria (mirrored from
`VN3DS-spec.md` §13). The project-level Definition of Done for the **BUILD-mode
portion** (Phases 0–2, ending at cutover) is:

| Metric | Target |
|---|---|
| Jisei (Phase 1) plays start-to-credits, Old 3DS profile, Azahar | Pass, zero `blocking` Problem Report items |
| Hustle Cat (Phase 2) plays ≥1 full route, Old 3DS profile, Azahar | Pass, zero `blocking` Problem Report items |
| Memory in use during gameplay | ≤ 70MB hard ceiling (target ≤45MB) on Old 3DS |
| Converter regression corpus ("The Question") | Zero `blocking` items |
| VNDS community scripts (via the VNDS converter, ADR-004) | Play correctly after conversion |
| Build | `.3dsx` boots cleanly in Azahar Old 3DS profile |
| Test coverage | Converter: `pytest` suite passing; Engine: `busted` suite passing |

Phases 3 onward (animation system, Live2D replacement, Phase 6 multi-engine
converters, etc.) continue under the same factory loop unless/until a cutover to
MAINTENANCE mode is declared — see `GAME-PLAN.md` mode marker and
`orchestrator/CUTOVER.md`.

## Explicit non-goals (v1)

See `VN3DS-spec.md` §4 for full detail. Summary:
- Universal "any game" conversion — v1 requires available `.rpy` source.
- A Python interpreter on the 3DS — the engine ships a tiny expression evaluator.
- Full custom-screen fidelity — screens are stubbed/flagged, not auto-translated.
- Live2D/mesh deformation — architecturally impossible on PICA200; replaced by the
  multi-layer + bone/puppet system (spec §9.2/§9.3).
- Non-Ren'Py engines in v1 — addressed in Phase 6, after the Ren'Py pipeline works.
- Commercial distribution.
- RPG Maker / WOLF / Unity / Godot titles — out of scope entirely (see spec §16).

## Known risks / unknowns

- Old 3DS LÖVE Potion baseline RAM consumption is an estimate (~25–30MB) pending
  Phase 0 stress-test measurement.
- MoonScript authoring fluency is a new skill for the Developer agent (ADR-003).
- Am I Nima?'s engine/scope is unknown until its Oct 2026 release.
- Custom-screen runtime (Phase 5) vs. per-game native reimplementation — decide
  after Phase 4 experience.
- Legal/personal: source acquisition for each target game confirmed per-game before
  its converter run.

## Source documents

- `VN3DS-spec.md` — full design spec (authoritative on all technical detail)
- `docs/ai/vn3ds-initial-plan.md` — original planning narrative
- `docs/ai/vn3ds-issue-slicing-plan.md` — issue-slicing plan (used post-cutover)
- `docs/ai/vn3ds-planning-questions.md` — planning Q&A, now resolved into ADRs
- `docs/ai/agent-workflow.md` — MAINTENANCE-mode workflow (issues, labels, PR rules)
- `docs/adr/ADR-001-converter-language-python.md`
- `docs/adr/ADR-002-script-format-vnds.md`
- `docs/adr/ADR-003-engine-fork-vnds-love-moonscript.md`
