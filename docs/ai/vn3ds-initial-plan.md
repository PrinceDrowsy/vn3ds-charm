# VN3DS-CHARM Initial Implementation Plan

Source: `VN3DS-spec.md` (reviewed 2026-07-03)  
Issue: #2 — `[AI] Convert VN3DS spec into implementation plan`

This plan turns the specification into an implementation sequence suitable for GitHub issue slicing. It intentionally does not implement application code.

## Guiding principles

1. **Engine-first validation.** Prove LÖVE Potion, dual-screen rendering, touch input, audio streaming, and O3DS memory baseline before investing heavily in converter code.
2. **Converter outputs are the product.** The converter should emit deterministic bundles: `manifest.json`, `script.vnds`, `problems.json`, textures, audio, fonts, and optional manual scene modules.
3. **Problem Report is mandatory.** Unsupported features must be reported explicitly. Do not silently miscompile Ren'Py behavior.
4. **Small vertical slices.** Each phase should end with a playable or inspectable artifact, not only library code.
5. **Old 3DS first.** Azahar O3DS profile is the iteration target, with real Old 3DS validation at phase boundaries.
6. **No proprietary assets in repo.** Commit synthetic fixtures and docs only; validate commercial titles manually from owned/extracted copies.

## Proposed repository workstreams

### Workstream A — Engine fork and runtime

Owns the VNDS-LOVE/LÖVE Potion player.

Core responsibilities:
- Fork/trim VNDS-LOVE ([ajusa/VNDS-LOVE](https://github.com/ajusa/VNDS-LOVE), MIT, @ 0.0.13). **Source is MoonScript** (compiles to Lua); edit `.moon` files, never the generated Lua.
- Build with LÖVE Potion for 3DS via the alfons/lovebrew toolchain (LuaRocks → moonscript / busted / alfons).
- Draw top-screen background/sprites and bottom-screen dialogue/choices.
- Interpret standard VNDS and VN3DS-CHARM extended commands.
- Provide save/load, audio streaming, animation, touch scenes, and later packaging.

### Workstream B — Converter core

Owns desktop-side source parsing and bundle emission.

Core responsibilities:
- Parse supported Ren'Py subset.
- Emit canonical extended VNDS script and manifest.
- Emit Problem Report for unsupported/approximated constructs.
- Manage deterministic output and converter exit codes.
- Support archive/DLC merge-at-convert-time behavior in later phases.

### Workstream C — Asset pipeline

Owns images, audio, font conversion, atlasing, and memory-budget enforcement.

Core responsibilities:
- Convert images to 3DS-friendly `.t3x` textures.
- Convert/normalize audio to streamed OGG.
- Enforce target dimensions and texture formats.
- Track per-bundle working-set estimates.
- Add atlas packing and partial reconvert later.

### Workstream D — Validation and fixtures

Owns repeatable tests and manual validation playbooks.

Core responsibilities:
- Synthetic `.rpy` fixtures for each supported/flagged construct.
- Engine smoke-test scripts and minimal bundles.
- Manual validation checklists for Azahar O3DS profile and hardware.
- Problem Report schema tests and regression corpus.

### Workstream E — Triage/manual-fix tooling

Owns human-facing triage flows after the core converter exists.

Core responsibilities:
- Define `fixes/overrides.json` sidecar contract.
- Add converter support for applying overrides.
- Build the Triage Workbench UI in Phase 5.5 if still valuable.

## Phase 0 — Engine fork spike

Goal: prove the runtime can boot and handle the baseline 3DS VN loop before any converter is built.

### Deliverables

- A VNDS-LOVE fork builds as a `.3dsx` under LÖVE Potion.
- A minimal hardcoded script or bundled text file shows:
  - image on top screen,
  - dialogue/name box on bottom screen,
  - A-button advance,
  - tap-to-advance,
  - touch-selectable choice buttons.
- A stress scene loads:
  - one 400×240 background,
  - two alpha sprites,
  - one streamed OGG track.
- A short engine validation doc records:
  - upstream fork source/commit,
  - LÖVE Potion version,
  - Azahar O3DS settings,
  - measured memory baseline,
  - pass/fail result for fallback contingency.

### Exit criteria

- `.3dsx` boots in Azahar O3DS profile.
- The minimal VN loop is usable by button and touch.
- Stress scene does not crash or visibly stutter.
- Memory measurement path is documented.

## Phase 1 — Walking skeleton and Jisei proof port

Goal: wire converter and engine end-to-end for a small real Ren'Py game.

### Converter scope

- Parse:
  - `label`, `jump`, `call`, `return`,
  - `scene`, `show`, `hide`,
  - `say` statements,
  - `Character()` definitions,
  - `menu:` choices.
- Emit:
  - `manifest.json`,
  - `script.vnds`,
  - `problems.json`,
  - converted image/audio assets.
- Flag unsupported constructs using the Problem Report.

### Engine scope

- Interpret standard VNDS and Phase 1 extended commands needed by the walking skeleton.
- Word-wrap text and show a typewriter reveal.
- Support bottom-screen choices.
- Stream OGG music/sfx/voice as needed.
- Maintain enough script state to advance, branch, call, and return.

### Validation sequence

1. Convert Ren'Py sample "The Question" or synthetic equivalent; expect zero `blocking` items.
2. Convert Jisei; inspect and triage `problems.json` to zero `blocking` items.
3. Play Jisei start-to-credits in Azahar O3DS profile.

### Exit criteria

- Jisei meets the spec's Phase 1 definition of done.
- Problem Report has actionable source locations for every unsupported construct.
- Memory remains under the 70MB hard ceiling during normal play.

## Phase 2 — Logic, state, audio, and Hustle Cat

Goal: support common full-route Ren'Py VN logic and prove the first full game route.

### Converter additions

- `default` and literal `define` values.
- Simple `$ var = <expr>` assignments.
- `if` / `elif` / `else` with supported expressions.
- `with dissolve` / `with fade`.
- `play` / `stop` / `queue` for music, sound, and voice.
- `pause`, `window show`, `window hide`.
- Supported text tags: `{b}`, `{i}`, `{color}`, `{w}`, `{p}`, `{size}`.

### Engine additions

- Safe expression evaluator: int/bool/string; arithmetic; comparisons; `and/or/not`.
- Variable state and conditional branching.
- Save/load: script position, variables, and call stack at minimum.
- Audio channel management.
- Pause/window toggles.

### Validation

- Convert Hustle Cat.
- Triage to zero `blocking` items.
- Play at least one full route to an ending.
- Verify save/reload mid-route.

## Phase 3 — Fidelity, animation, and first bespoke touch scenes

Goal: improve player fidelity and support titles with more custom interaction.

### Converter additions

- ATL pattern matching for common transforms.
- Emit `anim` presets or keyframe blocks for supported/approximated ATL.
- Flag shader/particle/impossible effects as `manual`.
- Flag unknown text tags and custom positions as `approximated` where playable.

### Engine additions

- Flux-based tween animation runtime.
- `anim`, `anim_begin`, `keyframe`, `anim_end`, `anim_wait`.
- Multi-layer sprite system:
  - `deflayer`, `showlayer`, `swaplayer`, `hidelayer`, `motion`.
- Dissolve/fade transitions.
- Colored name boxes.
- Bounded rollback/history.
- Settings screen.
- `nvlmode` routing.
- Touch scene module hook for bespoke scenes.

### Validation

- Sucker for Love: at least one route with ritual/interaction segments reimplemented as native bottom-screen touch scenes.
- Am I Nima? only if released and confirmed suitable.

## Phase 4 — Packaging, optimization, and heavier titles

Goal: production-quality packaging, asset optimization, and initial advanced animation.

### Toolchain additions

- CIA packaging with `makerom`.
- Per-game icon/banner/title metadata.
- Texture atlas packing.
- Partial reconvert.
- Multi-VN launcher/library screen if still desired.

### Engine additions

- Bone/puppet animation system:
  - `loadpuppet`, `showpuppet`, `hidepuppet`, `puppet_motion`,
  - bone hierarchy files in `scenes/bones/`,
  - per-bone spring physics,
  - integration with existing layer/swap system.

### Validation

- At least two of Slay the Princess, Kansei, and Yousei playable end-to-end on Old 3DS hardware.
- CIA builds install from SD.
- Bone/puppet test character runs on O3DS.

## Phase 5 — Complex ports and custom screen runtime

Goal: determine whether reusable custom-screen runtime support is worthwhile for games with bespoke systems.

### Scope

- Minimal custom-screen runtime or per-game native reimplementation path.
- `persistent.*` stub layer for gallery/unlock systems where useful.
- Ports: Our Life and/or Royal Alchemist.

### Exit criteria

- At least one full route in Our Life or Royal Alchemist is playable with core game systems functional.

## Phase 5.5 — Triage Workbench

Goal: make Problem Report resolution usable without hand-editing JSON and scripts.

### Scope

- Open a converted project folder.
- Display sorted Problem Report items.
- Show source context and suggested fixes.
- Write `fixes/overrides.json` sidecar entries.
- Re-run converter and refresh issue counts.
- Export bundle only when `blocking == 0`.

### Dependency

Before building the UI, the converter should already support reading and applying `fixes/overrides.json`.

## Phase 6 — Multi-engine converters

Goal: add new input parsers that emit the same extended VNDS bundle format.

Suggested order:

1. NScripter/ONScripter.
2. TyranoScript.
3. KiriKiri/KAG.
4. RealLive.
5. NVL-Maker as a KAG derivative.

Shared rule: every converter emits the same `script.vnds`, `manifest.json`, asset bundle, and Problem Report contract.

## Cross-cutting acceptance criteria

For every implementation issue, include applicable checks from this list:

- Output is deterministic for the same input.
- Unsupported behavior is reported, not silently dropped.
- `blocking` Problem Report items gate build success.
- No commercial/proprietary assets are committed.
- Manual validation instructions are documented when automation is not possible.
- Old 3DS memory budget impact is considered.
- New commands are documented with example script snippets.
- Tests include at least one positive fixture and one flagged/error fixture.

## Immediate next implementation sequence

1. Decide/document engine fork source and toolchain versions.
2. Create Phase 0 minimal engine boot issue.
3. Create Phase 0 dual-screen/touch issue.
4. Create Phase 0 stress-test/memory measurement issue.
5. Create converter architecture/schema issues, but do not start converter implementation until the Phase 0 fallback decision is known.
