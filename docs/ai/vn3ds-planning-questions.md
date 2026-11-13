# VN3DS-CHARM Planning Questions

Source: `VN3DS-spec.md` (reviewed 2026-07-03)  
Issue: #2 — `[AI] Convert VN3DS spec into implementation plan`

This document captures decisions that should be answered before or during implementation. None of these questions block the planning effort, but each should become either an early spike, an issue acceptance criterion, or an explicit project decision.

## High-priority questions

### 1. Engine fork baseline

- Which exact upstream `VNDS-LOVE` repository and commit should be used as the fork point?
- Which exact LÖVE Potion release should be targeted for Phase 0?
- What build artifacts are required for each milestone: `.3dsx` only at first, or `.cia` later?
- Where should platform/build instructions live so future agents can reproduce an Azahar run?

**PARTIALLY RESOLVED (2026-07-04, ADR-003):** Fork point is **[ajusa/VNDS-LOVE](https://github.com/ajusa/VNDS-LOVE) @ release 0.0.13** (MIT). Source language is **MoonScript** (compiles to Lua); build toolchain is LuaRocks → moonscript / busted / alfons, then lovebrew/LovePotion. `.3dsx` first, `.cia` from Phase 4. Exact LÖVE Potion release version to be pinned during the Phase 0 spike and recorded in the engine STACK doc.

### 2. Old 3DS performance baseline

The spec assumes an O3DS budget of roughly 80–90MB usable RAM, 25–30MB LÖVE Potion baseline RAM, a 45MB normal target, and a 70MB hard ceiling.

- What memory reporting API/function will the engine use under LÖVE Potion?
- What is the actual baseline RAM consumption for the chosen LÖVE Potion release?
- Does the Phase 0 stress scene run without stutter on Azahar O3DS profile and real O3DS hardware?
- At what measured point should the project consider the native C/citro2d fallback?

Recommended handling: make Phase 0 stress-test measurements explicit exit criteria before converter work begins.

### 3. Script output format naming

The spec mostly uses `script.vnds`, but Phase 1 engine bullets mention interpreting `script.json` flow ops.

- Is the canonical runtime script format plain-text extended VNDS (`script.vnds`) or JSON (`script.json`)?
- If an internal IR exists, should it be persisted, or only used during conversion?
- Should `manifest.json` point to the entry label in `script.vnds`?

**RESOLVED (2026-07-04, ADR-002):** Canonical runtime artifact is **`script.vnds`** (plain-text extended VNDS). The `script.json` references in the spec were slips and have been corrected. An internal converter IR may be used during conversion but is not persisted and is not an engine dependency. `manifest.json` points to the entry label in `script.vnds`.

### 4. Converter implementation language and project shape

The spec defines converter behavior but not implementation technology.

- Should the converter be implemented in .NET, Python, Lua, or another language?
- Is a Ren'Py parser library allowed, or should parsing begin with a targeted subset parser?
- How will external asset tools (`tex3ds`, audio encoders, archive extractors) be located and configured?
- Should converter output be deterministic across OSes and path separators?

**RESOLVED (2026-07-04, ADR-001):** Converter is implemented in **Python**. Parsing begins with a targeted subset parser (not a full Ren'Py parser library). External asset tools are invoked as subprocesses, located via config/PATH. Output must be deterministic across OSes and path separators. Remaining sub-questions (exact tool discovery mechanism) become converter-architecture issues.

### 5. Test content acquisition and licensing

The roadmap references Ren'Py's sample "The Question", Jisei, Hustle Cat, community VNDS scripts, and later commercial titles.

- Where will test fixtures live, given commercial game assets cannot be committed?
- What is the accepted source for "The Question" in automated tests?
- How should agents verify owned/extracted source content without exposing proprietary assets?
- Which sample scripts can be committed as tiny synthetic fixtures?

Recommended handling: keep proprietary content out of the repo; use synthetic fixtures for CI and document manual validation paths for owned games.

### 6. Problem Report contract

The spec requires a `problems.json` first-class output with severities, categories, `source`, `ren_py`, messages, suggestions, and non-zero exit for `blocking`.

- Should `missing-dlc` be added to the formal `category` enum? The DLC section uses it, but the earlier enum does not include it.
- What is the maximum length for `ren_py` snippets?
- Should `problems.md` be P0 or P1? The acceptance criteria mention human-readable rendering, while converter P1 lists `problems.md` as nice-to-have.
- Should `manual` items cause a non-zero exit, or only `blocking`?

Recommended handling: create a schema/contract issue before converter implementation.

### 7. Save/load and rollback semantics

- What exact fields are saved: label, instruction index, variables, call stack, audio state, visible sprites, current text state?
- Are save files plain JSON, Lua tables, or another format?
- How are save compatibility/version migrations handled as commands evolve?
- Does rollback include call stack and visible sprite state, or only variable state as currently specified?

Recommended handling: split save/load and rollback into separate issues; do rollback only after the core save format is proven.

### 8. Expression evaluator scope

The evaluator supports primitive values and basic operators, but Ren'Py game logic may use lists, dicts, object attributes, and function calls.

- How strict should parse-time detection be for unsupported expressions?
- Should simple string interpolation be supported in dialogue text?
- Should variable names mirror Ren'Py exactly, including dotted names, or are dotted names always `blocking`/`manual`?
- How are unknown variables reported?

Recommended handling: define an evaluator test matrix with accepted/rejected examples before implementation.

### 9. Asset pipeline details

- Which image formats are accepted as converter input?
- What command-line tools produce `.t3x`, and are they available on Windows for agents?
- How are power-of-two padding and texture atlases described in `manifest.json`?
- How are alpha formats chosen automatically vs. configured manually?
- How will audio loop metadata be preserved when re-encoding to OGG?

Recommended handling: spike image/audio conversion independently with tiny generated assets before integrating the converter.

### 10. UI layout defaults

The spec gives the broad layout: art on top, dialogue/menu bottom.

- What default font, text size, line height, and nameplate dimensions should be used?
- What happens for long lines and bottom-screen overflow?
- How are ADV vs NVL layouts represented in script commands and manifest metadata?
- What is the native default title/save/load UI if custom Ren'Py screens are flagged?

Recommended handling: make a Phase 0/1 UI style guide document or issue once the engine can draw text.

## Phase-specific questions

### Phase 0 — Engine fork spike

- Confirm fork source and license obligations.
- Confirm `Makefile`/toolchain installation path.
- Confirm Azahar automation/manual steps.
- Confirm O3DS profile settings for repeatable validation.

### Phase 1 — Walking skeleton + Jisei proof port

- Does Jisei's investigation UI use convertible `menu:` constructs or custom `screen` language?
- How much Jisei source can be referenced in tests/docs without committing proprietary content?
- Does the converter emit command names matching the extended VNDS command list exactly (`text`, `nameplate`, `ifvar`, etc.)?

### Phase 2 — Logic/state/audio + Hustle Cat

- Which text tags are required by Hustle Cat beyond the initial supported set?
- Does route affection logic require only primitive expressions?
- What audio loop behavior is required for BGM parity?

### Phase 3 — animation and touch scenes

- Should ATL fallback be static, nearest preset, or keyframe output by default?
- What runtime warning/logging mechanism will record exceeded animation guardrails?
- How are native touch scenes registered and packaged?

### Phase 4+ — packaging and heavy assets

- Which CIA metadata fields are configurable per game?
- What atlas format/schema is stable enough for future converters?
- What profiling hooks are needed before asset-heavy titles are attempted?

### Phase 5.5 — Triage Workbench

- Is the workbench in the same repo or a separate tool/repo?
- Which UI framework is acceptable for Windows-first use?
- Is `fixes/overrides.json` part of converter core before the UI exists?

### Phase 6 — multi-engine converters

- Should each converter share one common IR and Problem Report contract?
- Which extractor tools are legally/distribution-wise safe to document or wrap?
- Should NScripter be treated as a converter priority before completing all Ren'Py stretch features?

## Suggested ADR candidates

- Canonical runtime script format: `script.vnds` vs `script.json`.
- Converter implementation language and dependency policy.
- Problem Report schema and exit-code behavior.
- Save file format and compatibility policy.
- Asset conversion toolchain and texture format policy.
- Proprietary test content handling policy.
