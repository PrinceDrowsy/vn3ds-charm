# ADR-001 — Converter Implementation Language: Python

**Status:** Accepted
**Date:** 2026-07-04
**Deciders:** Scott, PrinceDrowsy

## Context

VN3DS-CHARM has two build targets in different languages: the **engine** (a fork of
ajusa/VNDS-LOVE, authored in MoonScript, running as Lua on LÖVE Potion — see
ADR-003) and the desktop-side **converter** that transpiles Ren'Py `.rpy` source
into the extended VNDS bundle. The spec (`VN3DS-spec.md`) defines the converter's
behaviour in detail but never fixed its implementation language. The planning docs
(`docs/ai/vn3ds-planning-questions.md` §4) flagged this as an open ADR-worthy
decision blocking Phase 1 converter work.

The converter must: parse a subset of Ren'Py, emit `script.vnds` + `manifest.json`
+ `problems.json`, drive external asset tools (`tex3ds`, audio encoders, archive
extractors), and produce deterministic output across operating systems.

## Decision

The converter is implemented in **Python**.

- Parsing starts with a **targeted subset parser**, not a full Ren'Py parser
  library. The converter only needs the declarative subset in spec §6; a bespoke
  parser keeps the Problem Report precise and avoids dragging in Ren'Py's runtime.
- External asset tools are invoked as **subprocesses**, located via config/PATH.
- Output must be **deterministic** across OSes and path separators (sorted keys,
  normalised path handling, stable ordering) so bundles are diffable.

## Consequences

- Ren'Py source is itself Python, so a Python converter can reuse Python's own
  `ast`/tokenizer where helpful for `$`-expressions and `init python:` detection.
- Matches the developer's existing tooling comfort (Python is already used across
  the homelab and n8n work), lowering friction for both Scott and PrinceDrowsy.
- Strong ecosystem for the surrounding work: Pillow for image pre-processing before
  `tex3ds`, subprocess orchestration, JSON handling, and `pytest` for the converter
  regression corpus.
- The engine (MoonScript/Lua) and converter (Python) are different languages — a
  deliberate split. The bundle format (`script.vnds` + JSON) is the language-neutral
  contract between them, so neither side constrains the other.
- The Triage Workbench (Phase 5.5) is also specified as Python, so converter and
  triage UI share a language and can share the `fixes/overrides.json` handling code.

## Alternatives considered

- **.NET/C#** — the Higurashi 3DS port's converter was C#, and it's the developer's
  professional stack. Rejected because Python's Ren'Py-adjacency (Ren'Py *is*
  Python), lighter subprocess/scripting ergonomics, and shared language with the
  Triage UI outweigh familiarity.
- **Lua** — would share a language with the engine runtime, but Lua is a poor fit
  for a desktop parser/asset-pipeline tool and has a weaker library ecosystem for
  this work. Rejected.
- **A full Ren'Py parser library** — rejected in favour of a targeted subset parser;
  full-fidelity parsing pulls in the runtime and undermines the "flag what we can't
  convert" Problem Report model.
