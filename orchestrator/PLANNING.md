# PLANNING.md — Phase P: Project Planning (grill-first)

> **Status for this project: Phase P is complete.** This file is kept for
> reference (e.g. if a future major addition needs its own mini-planning pass)
> and to document how the existing Phase P artifacts came to exist.

## What Phase P produced for VN3DS-CHARM

| Artifact | Status |
|---|---|
| `base/PROJECT.md` | ✅ Done |
| `base/ARCHITECTURE.md` | ✅ Done |
| `docs/adr/ADR-001-converter-language-python.md` | ✅ Done |
| `docs/adr/ADR-002-script-format-vnds.md` | ✅ Done |
| `docs/adr/ADR-003-engine-fork-vnds-love-moonscript.md` | ✅ Done |
| `GAME-PLAN.md` (opens `## Project Mode: BUILD`) | ✅ Done |

## How it was produced

VN3DS-CHARM's planning pass was somewhat non-standard relative to a from-scratch
`grill-with-docs` run: the project already had a very detailed design spec
(`VN3DS-spec.md`, built iteratively across many planning conversations) plus a
set of pre-factory planning docs (`docs/ai/vn3ds-initial-plan.md`,
`vn3ds-issue-slicing-plan.md`, `vn3ds-planning-questions.md`). Phase P here
consisted of:

1. **Resolving the open questions** in `vn3ds-planning-questions.md` — three of
   these were genuinely ADR-worthy blocking decisions (converter language,
   script format, engine fork base) and were resolved with the human in the loop,
   then written up as formal ADRs.
2. **Correcting a factual error surfaced during ADR-003's research** — the spec
   described the engine fork as "Lua," but the actual upstream repository
   (ajusa/VNDS-LOVE) is authored in MoonScript, which compiles to Lua. This was
   corrected across the spec and planning docs before the ADR was finalized.
3. **Deriving `base/PROJECT.md` and `base/ARCHITECTURE.md`** from the now-accurate
   spec, summarizing it into factory-consumable form without duplicating detail.
4. **Deriving `GAME-PLAN.md`** from the spec's existing Phase 0–6 roadmap
   (§13), converting narrative phase descriptions into checkbox work items.

This is a reasonable pattern for **any future project that starts from an
existing detailed spec** rather than a blank idea: the grill-style questioning
still happens, but it's targeted at the specific open questions the spec left
unresolved, rather than a from-scratch interview.

## If a future Phase P-style pass is needed

For a genuinely new sub-project or major pivot within VN3DS-CHARM (e.g. if the
project ever needed to re-plan a phase from scratch), follow the general
protocol in the `agent-factory` template's own `orchestrator/PLANNING.md` —
run `grill-with-docs` against the new idea, produce/update the relevant `base/`
docs and ADRs, and update `GAME-PLAN.md` accordingly. The gate check (base docs
+ ≥1 ADR + valid mode marker) still applies.
