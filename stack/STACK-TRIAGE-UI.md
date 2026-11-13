# STACK-TRIAGE-UI.md — Triage Workbench Technology Stack

**Phase:** 5.5 (not needed until Phases 0–5 are complete)
**Language: Python** — shares language with the Converter (see ADR-001, spec §Phase 5.5)

## Core stack

- **Language:** Python 3.x, same version as the Converter
- **UI framework:** TBD at Phase 5.5 kickoff — candidates from spec: `tkinter`
  (zero extra dependency, ships with Python), `PySimpleGUI`, or a small local web
  UI (Flask/FastAPI + browser). Decision deferred until Phase 5.5 planning; record
  the choice here and as an ADR once made.
- **Shared code with Converter:** `problem_report/` schema/parsing logic and
  `fixes/overrides.json` read/write logic should be shared modules, not duplicated,
  since both the Converter and the Triage UI read/write the same fix sidecar.

## Core UI panels (spec §Phase 5.5)

- Problem list panel (severity + category filtered)
- Source context panel (read-only, syntax-highlighted snippet at file:line)
- Fix panel (editable stub, "Apply Fix" writes to `fixes/overrides.json`)
- Animation preset dropdown with live preview (for `atl`/`approximated` items)
- Re-run converter button, blocking-count display, export-bundle button

## Project layout (`src/triage-ui/`)

```
src/triage-ui/
  app.py                 # entrypoint
  panels/
    problem_list.py
    source_context.py
    fix_editor.py
    preview.py
  fixes/
    overrides.py          # fixes/overrides.json read/write (shared w/ converter)
tests/
  triage-ui/               # pytest suite
```

## Fix persistence contract

`fixes/overrides.json` — sidecar in the project folder, keyed by Problem Report
item ID. Converter reads and applies overrides on every run. Original source files
are never modified (spec §Phase 5.5 "Fix persistence").

## Notes

- This stack file is intentionally light until Phase 5.5 planning begins — the
  Orchestrator should not scaffold `src/triage-ui/` before Phase 5 is complete.
