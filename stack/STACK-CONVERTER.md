# STACK-CONVERTER.md — Converter Technology Stack

**Language: Python** (ADR-001)

## Core stack

- **Language:** Python 3.x (version to be pinned in `base/ENVIRONMENT.md` during
  Phase 0/1 setup)
- **Parsing approach:** targeted subset parser, hand-written — not a full Ren'Py
  parser library. Only parses the declarative subset defined in `VN3DS-spec.md` §6.
  Reuse Python's own `ast`/tokenizer where helpful for `$`-expression and
  `init python:` detection (since Ren'Py source is itself Python).
- **Output emission:**
  - `script.vnds` — plain text, hand-rolled writer (ADR-002)
  - `manifest.json`, `problems.json` — Python's `json` module, sorted keys for
    determinism
- **Asset pipeline:**
  - Images → `.t3x` via `tex3ds` (devkitPro), invoked as a subprocess
  - Audio → OGG/Vorbis re-encode, tool TBD (ffmpeg or similar), invoked as a
    subprocess
  - Archive extraction (Phase 6+): `KrkrExtract`/`GARbro` (KiriKiri), `nsadec`/
    `sarconv` (NScripter), `FreeMoteToolkit` (E-mote models) — installed per-phase
- **Testing:** `pytest`
- **Determinism requirement:** same input → same bundle, byte-for-byte where
  feasible. Sort all JSON keys; normalize path separators; avoid embedding
  timestamps in output except the explicit `generated` field in `problems.json`.

## Project layout (`src/converter/`)

```
src/converter/
  parser/           # .rpy subset parser → internal IR
  emitters/         # script.vnds writer, manifest.json writer, problems.json writer
  assets/           # image/audio re-encoding pipeline
  dlc/              # DLC archive merge logic (spec §8.1)
  problem_report/   # Problem Report schema, severity logic, category enum
  cli.py            # command-line entrypoint
tests/
  converter/        # pytest suite
  fixtures/         # sample .rpy snippets exercising each flagged category (spec §14)
```

## Phase 6 extension pattern

Each Phase 6 engine converter (NScripter, KiriKiri, TyranoScript, RealLive) is a
sibling module under `src/converter/` (e.g. `src/converter/kirikiri/`), sharing the
`emitters/` and `problem_report/` code, with its own parser and archive-extraction
logic. All emit the same `script.vnds`/`manifest.json`/`problems.json` contract.

## Dependencies (add as needed, keep minimal)

- No heavy frameworks. This is a CLI tool, not a service.
- Avoid adding a full Ren'Py parsing library (ADR-001 rejected this approach) —
  if a dependency is ever considered here, it needs a new ADR.
