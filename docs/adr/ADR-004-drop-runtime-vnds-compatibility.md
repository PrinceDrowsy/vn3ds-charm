# ADR-004 — Drop Runtime VNDS Compatibility; VNDS Becomes a Converter Source

**Status:** Accepted
**Date:** 2026-11-13
**Deciders:** PrinceDrowsy
**Supersedes in part:** ADR-002 (its compatibility rationale; the `script.vnds`
format itself stays in use until a follow-up ADR replaces it)

## Context

ADR-002 made extended VNDS the runtime script format, partly so the engine could
play the existing VNDS community library (Tsukihime, Saya no Uta, Higurashi,
Fate/stay night and others) unmodified, and `base/PROJECT.md` made that a
Definition of Done item.

Real conversions have shown that keeping original VNDS semantics alive inside the
engine costs more than it gives. Original VNDS and converted Ren'Py content
disagree on basic rules, and the engine currently tries to honour both at once:

- Sprites: VNDS anchors by top-left corner in a 256×192 space; Ren'Py uses
  pos/anchor/align on the game's own resolution.
- `bgload` wipes every sprite, which matches `scene` but not `show bg`.
- Sprite replacement: VNDS matches by file path or screen position; Ren'Py
  replaces by image tag. `setimg` carries a position-matching fallback purely for
  hand-written VNDS.
- `$var` interpolation, `if`/`fi` forward scanning, `x1b[..m` colour codes, and
  VNDS keywords reused as engine event names (the source of the `play` crash
  found in hardware testing).

Several hardware bugs this year were VNDS-era assumptions quietly breaking
converted games: background size treated as screen size, top-left anchoring, a
background-relative sprite offset. And the format choices that cause the worst
performance problem (the whole script parsed into tables at startup, roughly
40 MB for Mice Tea measured in desktop Lua 5.1) can't change while the engine has
to read standard VNDS files directly.

Most of the VNDS library also isn't the best source for these games anyway. Many
of those novels are DS-era downconversions of NScripter/KiriKiri originals at
256×192, and Phase 6 already plans converters for the originals.

## Decision

1. The engine no longer reads original VNDS scripts. It plays only bundles the
   converter produces.
2. VNDS becomes one more converter input, alongside Ren'Py and the Phase 6
   engines. A VNDS front end translates each command into the engine's own model
   explicitly (a top-left anchor on a 256×192 canvas, `bgload` as a scene change,
   and so on), so nothing in those novels is approximated.
3. The runtime script format is now the project's own to design, free of VNDS
   constraints. Until a follow-up ADR replaces it, the converter keeps emitting
   today's `script.vnds`. The format's design (compiled Lua loaded on demand is
   the leading candidate) gets its own ADR.
4. VNDS-specific compatibility code in the engine (position-based sprite
   matching, standard VNDS-only commands, VNDS conventions that conflict with
   converted content) is removed when the new format lands, not piecemeal before.

## Consequences

- The engine has one set of rules, modelled on what converted games actually
  need. Fixes stop having to keep a second set of semantics working.
- The runtime format, save format and instruction set can be designed for the Old
  3DS: loading on demand, stable save positions, one shared opcode list checked
  on both sides.
- A VNDS novel can no longer be copied straight onto the SD card and played. It
  has to go through the converter on a PC first, like every other source.
- The VNDS community library stops being an engine regression corpus. It becomes
  a test corpus for the VNDS converter instead.
- New work: a VNDS converter front end (Phase 6g). VNDS is a small language of
  about 20 commands, so this is expected to be small.
- The upstream VNDS-LOVE specs in `tests/engine/upstream/` stop being a
  compatibility target and are retired when the old interpreter is removed.

## Alternatives considered

- **Keep VNDS compatibility in the engine (status quo).** Rejected: two
  conflicting sets of rules in one engine are behind a recurring class of bugs,
  and they block the format changes the Old 3DS memory budget needs.
- **Keep VNDS as a separate load-time front end inside the engine**, translating
  VNDS into the new model when a novel loads. Keeps direct SD-card play, but puts
  parsing and translation work back on the 3DS and keeps a second front end in the
  engine to maintain. Rejected, because converting on the PC costs one extra step
  and keeps the engine single-purpose.
