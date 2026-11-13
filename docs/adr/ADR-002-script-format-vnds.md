# ADR-002 — Canonical Runtime Script Format: `script.vnds`

**Status:** Superseded in part by ADR-004 (runtime VNDS compatibility dropped;
the `script.vnds` format stays in use until its replacement ADR)
**Date:** 2026-07-04
**Deciders:** Scott, PrinceDrowsy

## Context

The engine consumes a converted script at runtime. The spec (`VN3DS-spec.md`)
overwhelmingly refers to this artifact as **`script.vnds`** (plain-text extended
VNDS, one command per line, `@label` markers), and §12 defines its concrete shape.
However, a few spots in the spec — the §8 converter P0 list and the Phase 1 engine
bullets — referred to `script.json`, and `docs/ai/vn3ds-planning-questions.md` §3
flagged the inconsistency as needing an explicit decision before implementation.

Leaving both names in play risks the converter emitting one artifact while the
engine reads for another, and forces every future engine converter (Phase 6) to
guess which contract is real.

## Decision

The canonical runtime script artifact is **`script.vnds`** — plain-text extended
VNDS format.

- The stray `script.json` references in the spec were slips and have been corrected
  to `script.vnds`.
- An internal converter **IR may be used during conversion** but is not persisted
  and is not an engine dependency.
- `manifest.json` points to the entry label within `script.vnds`.
- `manifest.json` and `problems.json` remain JSON — the *script* is VNDS plain text;
  the *metadata* and *Problem Report* are JSON. This ADR concerns only the runtime
  script stream.

## Consequences

- The engine parses a plain-text command stream top-to-bottom, matching the original
  VNDS design and the IF/FI counter pattern borrowed from the original VN3DS project.
- Plain text is diffable, hand-editable, and inspectable — important for the Triage
  Workbench and for hand-authored fixes via `fixes/overrides.json`.
- Every Phase 6 engine converter (NScripter, KiriKiri, TyranoScript, RealLive) emits
  the **same** `script.vnds` contract, so the engine never needs per-source-engine
  runtime branches.
- Keeps the 3DS-side parser trivial (no JSON parser needed on the runtime hot path
  for the script itself), which matters on the 268MHz Old 3DS CPU.

## Alternatives considered

- **`script.json`** — a structured JSON script would be easier to emit precisely and
  validate, but adds a JSON parse cost on the 3DS runtime path, breaks compatibility
  with the existing VNDS community script corpus used for Phase 0 smoke-testing, and
  loses the plain-text hand-editability the triage workflow depends on. Rejected.
- **Dual-format (emit both)** — rejected as two sources of truth; the converter would
  have to keep them in sync and the engine would still need one canonical reader.
