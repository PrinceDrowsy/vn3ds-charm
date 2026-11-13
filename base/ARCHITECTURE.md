# ARCHITECTURE.md — VN3DS-CHARM

> Full technical detail lives in `VN3DS-spec.md`. This file gives the Orchestrator
> and agents the component map, folder structure, and boundaries needed to plan
> and route work without re-reading the entire spec each cycle.

## System shape

Two independent build targets connected by a language-neutral bundle contract.
Neither side needs to know the other's implementation language.

```
  DESKTOP                                    3DS / AZAHAR
  ┌─────────────────────┐                    ┌─────────────────────┐
  │  CONVERTER (Python)  │   bundle/          │  ENGINE               │
  │  parses .rpy subset  │ ─────────────────▶ │  VNDS-LOVE fork        │
  │  emits:              │  script.vnds       │  MoonScript src →      │
  │   - script.vnds      │  manifest.json     │  Lua runtime,          │
  │   - manifest.json    │  tex/*.t3x         │  LÖVE Potion           │
  │   - problems.json    │  audio/*.ogg       │  reads bundle only —   │
  │   - tex/, audio/     │                    │  never parses .rpy     │
  └─────────────────────┘                    └─────────────────────┘
```

**Hard rule:** the 3DS never parses `.rpy`. All parsing/transpilation/asset
crunching happens in the Converter. The Engine only ever consumes a pre-digested
bundle (spec §5).

## Components

### 1. Converter (`src/converter/`) — Python (ADR-001)

- Parses the Ren'Py subset defined in spec §6 into an internal IR.
- Emits `script.vnds` (ADR-002), `manifest.json`, `problems.json` (the Problem
  Report, spec §7).
- Re-encodes assets: images → `.t3x` via `tex3ds`, audio → streamed OGG.
- Merges DLC archives at convert time (spec §8.1) — no runtime DLC concept.
- Deterministic output: same input → same bundle, for diffable runs.
- Phase 6 adds sibling converter modules (NScripter, KiriKiri, TyranoScript,
  RealLive) — each independent, each emitting the same bundle contract.

### 2. Engine (`src/engine/`) — MoonScript → Lua, LÖVE Potion (ADR-003)

- Fork of [ajusa/VNDS-LOVE](https://github.com/ajusa/VNDS-LOVE) @ 0.0.13 (MIT).
- **Authored in MoonScript** (`.moon` files), compiled to Lua via `alfons`. Agents
  edit `.moon` source, never the generated Lua.
- Interprets `script.vnds` — standard + extended VNDS commands (spec §5.1).
- Dual-screen render: top screen (400×240) = backgrounds/sprites; bottom screen
  (320×240) = dialogue box, name box, choices, touch input.
- Subsystems added across phases: expression evaluator (§6.1), animation/tween
  system via `flux` (§9.1), multi-layer sprite system (§9.2 Option A), bone/puppet
  system (§9.2 Option B), save/load, audio streaming, custom touch scenes.
- Test framework: `busted` (inherited from upstream).

### 3. Triage Workbench (`src/triage-ui/`) — Python, Phase 5.5

- Desktop GUI (tkinter/PySimpleGUI/local web UI — TBD in STACK-TRIAGE-UI.md) that
  reads `problems.json`, shows source context, and writes fixes to
  `fixes/overrides.json` (spec §Phase 5.5).
- Shares language and some code with the Converter (both Python).

## Data contracts (the boundary between components)

These three files are the entire interface between Converter and Engine. Changing
their shape is a cross-cutting decision requiring an ADR, not a routine code change.

- **`script.vnds`** — plain-text extended VNDS script. One command per line,
  `@label` markers. See spec §12 for the concrete grammar.
- **`manifest.json`** — game metadata, entry label, asset index, channel config.
- **`problems.json`** — the Problem Report. Schema in spec §7.2. `category` enum:
  `python | screen | atl | displayable | video | text-tag | audio | asset | flow |
  live2d | missing-dlc | unknown`.
- **`fixes/overrides.json`** (Phase 5.5+) — sidecar fix persistence, keyed by
  Problem Report item ID. Converter reads and applies on every run.

## Folder structure (target repo layout)

```
vn3ds-charm/
  VN3DS-spec.md          ← authoritative design spec
  CLAUDE.md               ← factory root config (this project's copy)
  AGENTS.md               ← provider-neutral entrypoint
  GAME-PLAN.md             ← phased work queue + mode marker
  PHASES.md                ← live checkbox tracker (mirrors GAME-PLAN.md)
  base/                    ← this file, PROJECT.md, RULES.md, ENVIRONMENT.md
  stack/                   ← STACK-CONVERTER.md, STACK-ENGINE.md, STACK-TRIAGE-UI.md, STACK-TESTING.md
  agents/                  ← role definitions
  orchestrator/            ← loop-config.md, SKILLS-DISCOVERY.md, PLANNING.md, CUTOVER.md
  learning/                ← METRICS-HISTORY.md, SKILLS-LOG.md, RETROSPECTIVE.md
  docs/
    adr/                   ← ADR-001, 002, 003, and future decisions
    ai/                    ← pre-factory planning docs (initial plan, issue slicing, planning Q&A, agent-workflow)
  src/
    converter/             ← Python converter
    engine/                ← MoonScript/Lua engine fork
    triage-ui/              ← Python Triage Workbench (Phase 5.5+)
  tests/
    security-reports/       ← Security agent output
```

## Phase-to-component map

| Phase | Converter work | Engine work | New component |
|---|---|---|---|
| 0 | — | fork spike, dual-screen hello world, O3DS stress test | — |
| 1 | Ren'Py subset parser, `script.vnds`/`manifest.json`/`problems.json` emission, asset pipeline | interpret core VNDS + extended flow ops | — |
| 2 | logic/state/audio converter additions | expression evaluator, save/load, audio channels | — |
| 3 | ATL → animation preset mapping | flux animation system, multi-layer sprites (§9.2 Option A) | — |
| 4 | — | bone/puppet system (§9.2 Option B), CIA packaging | — |
| 5 | — | custom-screen runtime stretch | — |
| 5.5 | fixes/overrides.json read path | — | Triage Workbench |
| 6a–6e | sibling converter modules (NScripter, KiriKiri, TyranoScript, RealLive) | — | — |

## Boundaries agents must respect

- Converter and Engine are separate languages (Python vs. MoonScript/Lua) — do not
  blur this. Shared logic goes in the bundle contract, not cross-language calls.
- No agent hand-edits generated Lua in the engine — only `.moon` source (ADR-003).
- The 3DS engine never parses `.rpy` or any other source-engine format — that is
  exclusively the Converter's job, on desktop, before the bundle is produced.
- `base/` and `stack/` are read-only to all agents during a run (factory-wide rule).
