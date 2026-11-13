# VN3DS-CHARM Issue Slicing Plan

Source: `VN3DS-spec.md` (reviewed 2026-07-03)  
Issue: #2 — `[AI] Convert VN3DS spec into implementation plan`

This document proposes GitHub issue slices that can be created after the planning PR lands. The slices are intentionally small enough for agent work and use labels compatible with `docs/ai/agent-workflow.md`.

## Labeling guidance

Recommended labels per issue:

- `ai:ready` only when requirements and acceptance criteria are clear.
- `ai:afk` when the issue can be worked unattended.
- `type:planning` for docs/decision issues.
- `type:feature` for implementation slices.
- `type:test` for fixtures/validation automation.
- `risk:low` for docs/tests/small isolated code.
- `risk:medium` for implementation that touches runtime/converter architecture.
- Avoid `ai:afk` for issues requiring proprietary game assets, hardware-only validation, or ambiguous product decisions.

## Epic 0 — Project decisions and setup

### 0.1 Record engine fork and toolchain decision

Labels: `type:planning`, `risk:low`, `ai:ready`, `ai:afk`

Scope:
- Identify upstream VNDS-LOVE repo/commit.
- Identify target LÖVE Potion release.
- Document required 3DS build tools.
- Document Azahar O3DS profile setup.

Acceptance criteria:
- A doc exists under `docs/` with chosen versions and setup notes.
- Any unresolved setup blockers are listed explicitly.

### 0.2 Decide canonical script artifact

Labels: `type:planning`, `risk:low`, `ai:ready`, `ai:afk`

Scope:
- Resolve `script.vnds` vs `script.json` inconsistency.
- Document runtime artifact and any internal converter IR.

Acceptance criteria:
- ADR or planning doc states the canonical runtime script artifact.
- Future issues reference that decision.

### 0.3 Define Problem Report schema contract

Labels: `type:planning`, `risk:low`, `ai:ready`, `ai:afk`

Scope:
- Finalize severity values.
- Finalize category enum, including whether `missing-dlc` is formal.
- Define exit-code behavior.
- Define snippet truncation rules.
- Decide whether `problems.md` is P0 or P1.

Acceptance criteria:
- Schema examples are documented.
- At least one clean and one blocking report example is included.

### 0.4 Define proprietary test asset policy

Labels: `type:planning`, `risk:low`, `ai:ready`, `ai:afk`

Scope:
- Document what can be committed.
- Document how owned commercial games are used manually.
- Define fixture strategy for CI.

Acceptance criteria:
- A repository policy doc states that proprietary assets are not committed.
- Manual validation paths are documented separately from automated tests.

## Epic 1 — Phase 0 engine spike

### 1.1 Create minimal VNDS-LOVE fork skeleton

Labels: `type:feature`, `risk:medium`

Scope:
- Add/fork the minimal engine project structure.
- Build a `.3dsx` with LÖVE Potion.
- Keep runtime minimal; no converter.

Acceptance criteria:
- Build instructions run from a clean checkout.
- Generated build artifacts are ignored or documented.
- No converter code is introduced.

### 1.2 Render top and bottom screens

Labels: `type:feature`, `risk:medium`

Scope:
- Draw a static top-screen image area.
- Draw a bottom-screen dialogue box and placeholder nameplate.

Acceptance criteria:
- Azahar screenshot/manual check shows correct dual-screen layout.
- Coordinates match 400×240 top and 320×240 bottom expectations.

### 1.3 Implement input advance and touch choices

Labels: `type:feature`, `risk:medium`

Scope:
- A button advances dialogue.
- Bottom-screen tap advances dialogue.
- Touch buttons select from at least two choices.

Acceptance criteria:
- Minimal scenario can advance through three lines and branch on a choice.
- Manual validation notes are committed.

### 1.4 Run Phase 0 O3DS stress scene

Labels: `type:test`, `risk:medium`

Scope:
- Load one 400×240 background.
- Load two alpha sprites.
- Stream one OGG music file.
- Record memory reporting approach and result.

Acceptance criteria:
- Stress scene runs in Azahar O3DS profile without crash/stutter.
- Memory reading is documented.
- Fallback contingency status is documented.

## Epic 2 — Runtime command interpreter

### 2.1 Standard VNDS command loop

Labels: `type:feature`, `risk:medium`

Scope:
- Parse and execute standard VNDS commands: `text`, `bgload`, `setimg`, `sound`, `music`, `choice`, `jump`, `delay`, `if`, `fi`.

Acceptance criteria:
- Existing or synthetic VNDS script plays through a small branching scenario.
- Unknown commands fail visibly or log an actionable error.

### 2.2 Extended VN3DS flow commands

Labels: `type:feature`, `risk:medium`

Scope:
- Implement `clearimg`, `nameplate`, `setvar`, `ifvar`, `call`, `return`, `voiceover`, `stopmusic`, `stopsound`, `window`.

Acceptance criteria:
- Synthetic script exercises variables, conditional branch, call stack, and channel stops.
- Call stack underflow is handled safely.

### 2.3 Text rendering behavior

Labels: `type:feature`, `risk:medium`

Scope:
- Word wrapping.
- Typewriter reveal.
- Basic nameplate rendering.
- Overflow handling.

Acceptance criteria:
- Long dialogue wraps without leaving the bottom screen.
- User can advance past typewriter reveal predictably.

### 2.4 Save and load baseline

Labels: `type:feature`, `risk:medium`

Scope:
- Save current label/instruction index.
- Save variables and call stack.
- Reload and continue.

Acceptance criteria:
- Synthetic scenario can save before a branch, reload, and continue correctly.
- Save file format/version is documented.

## Epic 3 — Converter core and Problem Report

### 3.1 Converter project skeleton

Labels: `type:feature`, `risk:medium`, `ai:ready`, `ai:afk`

Scope:
- Create converter project structure in the chosen language.
- Add CLI entry point and deterministic output directory handling.
- No full parser yet.

Acceptance criteria:
- CLI help runs.
- Empty/minimal input produces a clear validation error.
- Generated outputs are deterministic in path ordering.

### 3.2 Problem Report writer

Labels: `type:feature`, `risk:low`, `ai:ready`, `ai:afk`

Scope:
- Implement report data model and JSON writer.
- Include summary counts.
- Include exit-code behavior for `blocking`.

Acceptance criteria:
- Unit tests cover zero-item, manual-only, and blocking reports.
- Summary counts match item array.

### 3.3 Human-readable Problem Report rendering

Labels: `type:feature`, `risk:low`, `ai:ready`, `ai:afk`

Scope:
- Emit `problems.md` or console table depending on schema decision.
- Group by severity/category.

Acceptance criteria:
- Sample reports render in a readable format.
- The JSON remains the source of truth.

### 3.4 Parse Ren'Py labels and flow

Labels: `type:feature`, `risk:medium`, `ai:ready`, `ai:afk`

Scope:
- Parse `label`, `jump`, `call`, and `return` from simple `.rpy` fixtures.
- Emit equivalent `script.vnds` flow labels/commands.

Acceptance criteria:
- Fixture with two labels and a jump converts correctly.
- Invalid target labels become Problem Report flow items.

### 3.5 Parse dialogue and characters

Labels: `type:feature`, `risk:medium`, `ai:ready`, `ai:afk`

Scope:
- Parse `Character()` definitions for name/color.
- Parse say statements.
- Emit `manifest.json` character metadata and dialogue commands.

Acceptance criteria:
- Named and narrator dialogue fixtures convert.
- Unsupported character definitions are reported.

### 3.6 Parse scenes, sprites, and menus

Labels: `type:feature`, `risk:medium`, `ai:ready`, `ai:afk`

Scope:
- Convert `scene`, `show`, `hide` with left/center/right positions.
- Convert `menu:` choices to choice/jump command pattern.

Acceptance criteria:
- Fixture with a background, sprite, and two-choice menu converts.
- Custom positions become `approximated` items.

### 3.7 Flag unsupported Ren'Py constructs

Labels: `type:feature`, `risk:medium`, `ai:ready`, `ai:afk`

Scope:
- Detect `init python`, non-trivial `$`, `screen`, custom displayables, `renpy.*`, movies, Live2D/spine, and `persistent.*`.
- Emit placeholder/no-op where appropriate.

Acceptance criteria:
- Each unsupported category has at least one fixture.
- `blocking` vs `manual` severities match the schema decision.

## Epic 4 — Asset pipeline

### 4.1 Image conversion spike

Labels: `type:feature`, `risk:medium`

Scope:
- Convert a generated/static image to `.t3x`.
- Document required external tools.
- Handle top-screen and bottom-screen target sizes.

Acceptance criteria:
- A tiny sample texture is generated from a fixture image.
- Conversion command is documented for Windows.

### 4.2 Audio conversion and streaming fixture

Labels: `type:feature`, `risk:medium`

Scope:
- Convert/normalize sample audio to OGG if needed.
- Verify engine can stream it without loading whole file into RAM.

Acceptance criteria:
- Sample audio plays in the engine.
- Memory behavior is noted in validation docs.

### 4.3 Bundle manifest and asset index

Labels: `type:feature`, `risk:medium`, `ai:ready`, `ai:afk`

Scope:
- Define and emit `manifest.json` with metadata, entry label, characters, assets, and channel configuration.

Acceptance criteria:
- Manifest schema is documented.
- Engine loads entry label/assets from manifest instead of hardcoded paths.

## Epic 5 — Phase 1 validation targets

### 5.1 Convert Ren'Py sample/synthetic equivalent

Labels: `type:test`, `risk:low`

Scope:
- Run converter against "The Question" if available, otherwise synthetic committed fixture covering Phase 1 subset.

Acceptance criteria:
- Conversion reaches zero `blocking` items.
- Output bundle is committed only if it contains no proprietary assets, otherwise validation notes only.

### 5.2 Jisei first converter run

Labels: `type:test`, `risk:medium`

Scope:
- Run converter on a locally owned/extracted Jisei source folder.
- Capture Problem Report summary only; do not commit game assets/source.

Acceptance criteria:
- `problems.json` summary is documented.
- Hot spots are classified for follow-up issues.

### 5.3 Jisei playable proof checklist

Labels: `type:test`, `risk:medium`

Scope:
- Triage Jisei to zero `blocking` items.
- Play start-to-credits in Azahar O3DS profile.

Acceptance criteria:
- Dual-screen layout works.
- Touch advance/choices work.
- Voiced lines audible.
- Save/load mid-investigation works.
- Memory remains under 70MB.

Do not mark `ai:afk` unless the agent has access to the required local game source and validation environment.

## Epic 6 — Phase 2 state and Hustle Cat

### 6.1 Expression evaluator

Labels: `type:feature`, `risk:medium`, `ai:ready`, `ai:afk`

Scope:
- Support int/bool/string values.
- Support arithmetic, comparisons, and `and/or/not`.
- Reject functions, attributes, lists, dicts, and `renpy.*`.

Acceptance criteria:
- Accepted/rejected expression matrix is tested.
- Rejected flow-dependent expressions create `blocking` items.

### 6.2 Variable assignment and conditionals

Labels: `type:feature`, `risk:medium`, `ai:ready`, `ai:afk`

Scope:
- Convert `default`, literal `define`, simple `$ var = expr`, `if/elif/else`.

Acceptance criteria:
- Synthetic route-gating fixture converts and plays correctly.

### 6.3 Audio command conversion and channels

Labels: `type:feature`, `risk:medium`, `ai:ready`, `ai:afk`

Scope:
- Convert `play`, `stop`, and `queue` for music/sound/voice.
- Engine manages separate channels.

Acceptance criteria:
- Fixture demonstrates BGM loop, sfx, and voice line.

### 6.4 Hustle Cat one-route validation

Labels: `type:test`, `risk:medium`

Scope:
- Convert owned/extracted Hustle Cat source.
- Triage to zero `blocking`.
- Play one route to ending.

Acceptance criteria:
- Route completes in Azahar O3DS profile.
- Save/reload mid-route works.
- Memory remains under 70MB.

## Epic 7 — Phase 3 fidelity and animation

### 7.1 ATL-to-animation preset conversion

Labels: `type:feature`, `risk:medium`, `ai:ready`, `ai:afk`

Scope:
- Convert common ATL/static transforms to `anim` presets.
- Emit `approximated` Problem Report items for nearest-safe fallbacks.

Acceptance criteria:
- Fixtures cover fade, slide, zoom, shake, unknown ATL, and shader/impossible cases.

### 7.2 Flux tween runtime

Labels: `type:feature`, `risk:medium`

Scope:
- Integrate tween update loop.
- Implement `anim` presets and keyframe command block execution.

Acceptance criteria:
- Synthetic script shows visible fade/slide/shake animations.
- O3DS active tween guardrail warning is implemented or logged.

### 7.3 Multi-layer sprite runtime

Labels: `type:feature`, `risk:medium`

Scope:
- Implement `deflayer`, `showlayer`, `swaplayer`, `hidelayer`, `motion`.
- Add idle breathing/blinking behavior.

Acceptance criteria:
- Synthetic layered character fixture swaps expression layers and blinks.
- More than two layered characters on O3DS is flagged or documented as unsupported.

### 7.4 Touch scene hook

Labels: `type:feature`, `risk:medium`

Scope:
- Implement `touchscene <file>` loading for bespoke Lua interaction modules.

Acceptance criteria:
- Synthetic touchscene receives touch input and returns to script execution.

## Epic 8 — Later phase placeholders

These should not be marked `ai:ready` until earlier phases prove the base pipeline.

### 8.1 CIA packaging

Scope:
- Add makerom pipeline, icon/banner metadata, installable build output.

### 8.2 Texture atlas packing

Scope:
- Bin-pack sprites into fewer `.t3x` atlases and update manifest lookups.

### 8.3 Bone/puppet animation runtime

Scope:
- Implement bone hierarchy, spring physics, and `loadpuppet`/`showpuppet`/`puppet_motion` commands.

### 8.4 Fix overrides sidecar

Scope:
- Implement `fixes/overrides.json` and converter re-run behavior before Triage Workbench UI.

### 8.5 Triage Workbench UI

Scope:
- Build the desktop UI for reviewing and resolving Problem Report items.

### 8.6 Multi-engine converter modules

Scope:
- Add NScripter, TyranoScript, KiriKiri/KAG, RealLive converter modules after Ren'Py path is stable.

## Suggested first batch of GitHub issues

Create these first, in order:

1. Record engine fork and toolchain decision.
2. Decide canonical script artifact.
3. Define Problem Report schema contract.
4. Define proprietary test asset policy.
5. Create minimal VNDS-LOVE fork skeleton.
6. Render top and bottom screens.
7. Implement input advance and touch choices.
8. Run Phase 0 O3DS stress scene.
9. Create converter project skeleton.
10. Implement Problem Report writer.

Only start broad Ren'Py converter work after the Phase 0 stress scene confirms the LÖVE Potion path is viable on the Old 3DS target.
