# VN3DS-CHARM — Ren'Py → Nintendo 3DS VN Toolchain

**Project name:** VN3DS-CHARM
**Status:** v1 spec, pre-implementation
**Proof target:** *Jisei: The First Case* (Sakevisual, Ren'Py) — Phase 1
**First full target:** *Hustle Cat* (Date Nighto / Pancake Games, Ren'Py) — Phase 2
**Author:** Scott & PrinceDrowsy
**Last updated:** 2026-07-03

> **Name note:** "VN3DS" is already taken by a discontinued LPP-based VNDS interpreter project on GBAtemp (2015, abandoned). "VN3DS-CHARM" is distinct from it (ADR-006 records the rename from VN3DS-LOVE).

---

## 1. Summary

VN3DS-CHARM is a two-part toolchain that takes a Ren'Py visual novel and produces a playable 3DS build. It does **not** run Ren'Py on the 3DS. Instead, a desktop-side **Converter** transpiles the declarative subset of a game's `.rpy` scripts into an extended VNDS-format script and re-encodes its assets, and a forked **Engine** (VNDS-LOVE extended fork, MoonScript source → Lua runtime on LÖVE Potion) plays that format with a dual-screen layout: artwork on the top screen, dialogue box and menus on the bottom screen, touch to advance and choose.

The engine is based on a fork of **VNDS-LOVE** ([ajusa/VNDS-LOVE](https://github.com/ajusa/VNDS-LOVE), MIT, @ 0.0.13), a cross-platform VNDS player whose source is **MoonScript** (a language that compiles to Lua) built for LÖVE. The VNDS command set is extended to support transitions, variable state, branching logic, call stacks, and touch interaction segments — commands the original DS-era VNDS format never needed. The extended format is not compatible with other VNDS players by design; VN3DS-CHARM owns both ends of the pipeline.

> **Authoring vs runtime language.** The engine's *source* is MoonScript (`.moon` files in `src/`), compiled to Lua via `alfons`; the *runtime* is Lua on LÖVE Potion. Throughout this spec, references to "Lua" at the runtime layer (LÖVE API calls, `love.graphics.draw`, flux tweens) remain accurate. But the Developer agent edits `.moon` files and runs the compile step — it must not hand-edit the generated Lua. Toolchain: LuaRocks → moonscript / busted (tests) / alfons (build), then lovebrew/LovePotion for the 3DS `.3dsx`/`.cia`. See ADR-003.

**Prior art confirming platform viability:** Multiple prior homebrew projects confirm that Lua/LÖVE Potion on 3DS is sufficient for full-featured VNs with custom UI, asset-heavy content, voice acting, and desktop-side converters. See §2.1 for full prior art catalogue.

The Converter cannot represent everything Ren'Py can do (arbitrary Python, screen language, ATL animation). Rather than fail or silently miscompile, it emits a **Problem Report** — a first-class output that enumerates exactly what it could not convert, where, and why. The Problem Report is treated as a primary deliverable, equal in importance to the converted bundle. A game is "ported" when its bundle runs **and** its Problem Report has been triaged to zero blocking items.

---

## 2. Problem Statement

The 3DS is an excellent VN device — dual screens map naturally to "art up top, text and touch input down below" — but no path exists to get the thousands of Ren'Py-based VNs onto it. Ren'Py itself cannot be ported: it is CPython plus SDL, and the interpreter runtime alone exceeds the 3DS memory budget (64 MB on Old 3DS, ~124 MB usable on New 3DS) before any game content loads. Feature-stripping a Ren'Py fork does not help, because the cost is the language substrate, not the feature surface.

The viable approach is to translate the game's declarative content into a purpose-built engine, accept that arbitrary Python won't translate, and surface those gaps explicitly so a human can resolve them. VN3DS-CHARM uses **VNDS-LOVE** as its engine base — a cross-platform Lua/LÖVE VN player — with the VNDS command set extended beyond its original DS-era limitations. This avoids rebuilding the 3DS platform layer (dual screen, touch input, audio, `.t3x` texture handling) from scratch in C/C++, while still giving full control over the feature ceiling via format extensions. The Lua + LÖVE Potion runtime has been validated for this class of application by multiple prior homebrew projects.

**Hardware targets.** VN3DS-CHARM targets both Old 3DS and New 3DS as primary platforms, with Old 3DS as the binding constraint for all memory and CPU budgets. The Old 3DS has 128MB total RAM (~80–90MB usable by homebrew after the OS and LÖVE Potion runtime), an ARM11 MPCore at 268MHz, and the PICA200 GPU. The New 3DS has 256MB total RAM (~170MB usable), ARM11 at 804MHz, and the same PICA200. Because the GPU is identical between models, all rendering and GPU-accelerated transforms work the same on both — the binding differences are CPU speed and RAM. Every budget figure in this spec is written against Old 3DS limits; features are defined to run acceptably on O3DS and run better on N3DS automatically.

### 2.1 Prior Art Catalogue

Four prior homebrew projects confirm the viability of the VN3DS-CHARM approach. Each proves something specific.

---

**DDLC-LOVE** (LukeZGD, GPL-3.0)
*Proves: Lua/LÖVE Potion memory headroom for asset-rich VNs on 3DS*

A complete Lua/LÖVE Potion port of Doki Doki Literature Club to 3DS, shipping as both `.3dsx` and `.cia`. DDLC is a moderately asset-rich Ren'Py game with custom UI, multiple sprite sheets with many expressions, CGs, and special rendering effects. DDLC-LOVE reimplements all of this natively in Lua under LÖVE Potion. It runs on hardware and confirms the runtime is viable for real VN content under LÖVE Potion. Note: DDLC-LOVE's own documentation targets New 3DS — O3DS compatibility is not explicitly confirmed by this project, and the note about disabling L2 Cache on N3DS suggests some platform-specific tuning is needed. O3DS performance must be validated in Phase 0.

**Key reference material:** dual-screen layout implementation, LÖVE Potion sprite/audio handling, save state serialization, CIA build setup via `LovePotion.elf`. Source at `github.com/LukeZGD/DDLC-LOVE`.

---

**Higurashi: When They Cry 3DS Port** (MyLegGuy, abandoned 2017)
*Proves: converter + custom engine architecture; PS3-quality voice+graphics on 3DS hardware*

The author describes it explicitly as "a generic visual novel engine I've created from scratch with playing these games in mind" — not a VNDS player. It has a separate desktop-side **C# script and image converter** that takes files directly from the Steam/MangaGamer installation and produces a 3DS-ready bundle. The engine handles updated character graphics, the PS3 Graphics & Voices patch, color filter effects, and fade-in/fade-out transitions for backgrounds and sprites. Ships `.3dsx` and `.cia`. Full chapter navigation and save system.

This is the closest architectural match to VN3DS-CHARM that exists: a purpose-built 3DS VN engine paired with a desktop converter that takes source files from an owned copy of the game. The fact that it handled PS3-quality voice and graphics on 3DS hardware is meaningful confirmation for the asset pipeline.

Abandoned and does not work for the latest Higurashi chapters, but releases and source are on GitHub and the GBAtemp thread remains active. **Key reference material:** C# converter structure, image scaling/conversion approach, chapter/save system design. Source at GBAtemp thread `#492390`.

---

**VN3DS** (anonymous GBAtemp dev, discontinued 2015)
*Proves: VNDS command set in Lua/LPP on 3DS; IF/FI nesting implementation pattern*

An earlier LPP (precursor to LÖVE Potion) implementation of VNDS on 3DS. Implemented: `text`, `cleartext`, `label`/`goto`, `delay`, `jump`, `setvar`, `gsetvar`, `save`/`load`, `bgload`, `setimg`, `choice`, `IF`/`FI`, `random`. Got far enough to display Saya no Uta. The project is the source of the "VN3DS" name conflict — VN3DS-CHARM is named to be distinct.

**Key implementation note:** The author's IF/FI nesting solution is worth borrowing directly: a false IF condition increments a skip-counter by 1; while the counter is greater than 0, all lines are ignored; every FI decrements by 1, eventually returning to 0. This handles arbitrarily nested conditionals without recursion. Applicable directly to VN3DS-CHARM's `ifvar` extended command implementation.

---

**VNDS-CLONE / Higurashi-Vita** (PSX-Place)
*Proves: breadth of existing VNDS library; standard format compatibility*

A PS Vita VNDS player that also powered the Higurashi 3DS port. Confirmed working VNDS titles include: Higurashi When They Cry, Saya no Uta, Wanko to Kurasou, Fate/Stay Night, Cross Channel, Tsukihime, Shikkoku no Sharnoth, Umineko, and others. Phase 0 used these existing VNDS community scripts as free smoke-test content. Since ADR-004 the engine no longer reads VNDS directly: these titles go through the converter's VNDS front end (Phase 6g) like any other source, and serve as that converter's test corpus.

---

## 3. Goals

1. **Play a real Ren'Py VN on 3DS hardware.** Complete *Jisei* end-to-end as the proof of concept, then reach the end of at least one full route of *Hustle Cat* as the first full port — both on an Old 3DS, in the dual-screen layout, with working choices, music, and save/load.
2. **Make the unconvertible visible, not silent.** Every Ren'Py construct the Converter cannot represent produces a Problem Report entry with source location, original snippet, and a suggested fix. No silent miscompiles.
3. **Keep the human in the loop efficiently.** A developer should be able to port a moderately-complex VN by running the Converter, reading the Problem Report top-to-bottom, and hand-fixing only the flagged spots — not by reading the entire script.
4. **Stay within the memory budget on Old 3DS.** All memory, CPU, and asset budgets are written against O3DS limits. N3DS runs all of the same content with headroom to spare.
5. **Iterate in Azahar, not on hardware.** The whole loop (convert → run → inspect) must work in the emulator so the SD card only gets touched at milestones.

---

## 4. Non-Goals (v1)

1. **Universal "drop in any game" conversion.** v1 targets games whose `.rpy` *source* is available and whose logic lives mostly in declarative statements. `.rpyc`-only distributions are out of scope.
2. **A Python interpreter on the 3DS.** The Engine ships a tiny expression evaluator, not Python. Anything needing real Python is a Problem Report item, not an engine feature.
3. **Screen language fidelity.** Custom Ren'Py screens are stubbed and flagged for native reimplementation, not auto-translated. (Default save/load/choice UI is provided natively by the Engine.)
4. **Mesh deformation, Live2D Cubism SDK, spine runtimes.** Real-time mesh deformation is hardware-impossible on PICA200. Replaced by the multi-layer and bone/puppet systems in §9.2, which require a manual art segmentation step.
5. **Non-Ren'Py engines (v1).** KiriKiri, NScripter, TyranoScript, etc. are out of scope for the Ren'Py converter. These are addressed in Phase 6.
6. **Commercial distribution.** This is a personal homebrew toolchain for source-available or owned games.

---

## 5. Architecture

```
  ┌──────────────────────────── DESKTOP ────────────────────────────┐
  │                                                                  │
  │   game/ (.rpy source + assets)                                   │
  │            │                                                     │
  │            ▼                                                     │
  │   ┌─────────────────┐   parses subset, transpiles, re-encodes    │
  │   │   CONVERTER      │──────────────┬──────────────┐             │
  │   │   (Python)       │              │              │             │
  │   └─────────────────┘              │              │             │
  │            │                       │              │             │
  │            ▼                       ▼              ▼             │
  │     problems.json          bundle/script.vnds   bundle/tex/     │
  │   (PROBLEM REPORT)         bundle/manifest.json  bundle/audio/  │
  │                                                                  │
  └────────────────────────────┬─────────────────────────────────────┘
                               │ copy bundle/ to SD or load in Azahar
                               ▼
  ┌──────────────────────────── 3DS / AZAHAR ───────────────────────┐
  │   ┌──────────────────────┐                                       │
  │   │   ENGINE              │  reads manifest → interprets         │
  │   │   VNDS-LOVE fork      │  extended VNDS script                │
  │   │   (MoonScript→Lua,    │  TOP: backgrounds + sprites          │
  │   │    LÖVE Potion)       │  BOTTOM: dialogue box, name,         │
  │   │                       │  choices, touch input                │
  │   └──────────────────────┘                                       │
  └──────────────────────────────────────────────────────────────────┘
```

**Hard rule:** the 3DS never parses `.rpy`. All parsing, transpilation, and asset crunching happen in the Converter. The Engine only ever consumes a pre-digested bundle.

**Engine base:** VNDS-LOVE fork ([ajusa/VNDS-LOVE](https://github.com/ajusa/VNDS-LOVE), MIT, @ 0.0.13). Source is **MoonScript** (compiles to Lua), runtime is Lua on LÖVE Potion. The fork extends the VNDS command set with new commands for transitions, variable state, branching, call stacks, and touch interactions. The extended format is VN3DS-CHARM-specific and not intended to be compatible with other VNDS players. Native C/C++ (devkitPro + citro2d) remains a documented fallback contingency if LÖVE Potion performance proves insufficient for a specific title, but DDLC-LOVE's successful 3DS run makes this unlikely.

### 5.1 Extended VNDS command set

Standard VNDS commands (unchanged):
```
text <string>         # display dialogue line
bgload <file>         # load background image
setimg <file> <pos>   # show sprite at position (left/center/right)
sound <file>          # play sound effect
music <file>          # play/loop music track
choice <opt1> <opt2>  # present choices → touch buttons
jump <label>          # unconditional jump
delay <ms>            # pause execution
if <cond> jump <lbl>  # conditional jump (original, simple)
fi                    # end if block
```

Extended commands (VN3DS additions):
```
transition <type> <duration>   # dissolve / fade between scenes
clearimg <pos>                 # hide sprite at position
nameplate <who>                # set character name box
setvar <name> <value>          # assign variable (int/bool/string)
ifvar <name> <op> <val>        # extended conditional (>=, <=, ==, !=)
call <label>                   # push return address, jump to label
return                         # pop return address, resume
voiceover <file>               # play voiced line on voice channel
stopmusic                      # stop music channel
stopsound                      # stop sfx channel
window <show|hide>             # toggle dialogue box visibility
touchscene <file>              # load touch interaction scene (Lua module)
nvlmode <on|off>               # switch NVL/ADV mode
anim <target> <preset> <dur>   # animate sprite using named preset
anim_begin <target> <dur>      # begin keyframe animation block
  keyframe <t> <prop>=<val>..  # keyframe at normalised time t (0.0–1.0)
anim_end                       # close keyframe block
anim_wait <target>             # pause script until animation completes
```

### 5.2 Bundle layout

```
bundle/
  manifest.json       # game metadata, entry label, asset index, channel config
  script.vnds         # extended VNDS script (plain text, one command per line)
  problems.json        # the Problem Report (also kept desktop-side)
  tex/                 # .t3x texture atlases (backgrounds, sprites, UI)
  audio/               # .ogg, streamed at runtime
  fonts/               # converted/bundled fonts
  scenes/              # Lua modules for touch interaction scenes (manual)
```

---

### 5.3 Distribution: HOME Menu Forwarders

Per-novel visibility on the 3DS HOME Menu, so an installed VN looks and
launches like a real downloaded game rather than something the player has
to reach through the Homebrew Launcher and an in-app picker every time.

**How this differs from §13's Phase 4.1 CIA packaging:** Phase 4.1 packages
the *whole engine* (with one game's bundle embedded) as a single native
CIA per title — a real, standalone executable, built fresh via `makerom`
for each port. That's appropriate for finished, heavyweight ports (Slay
the Princess, Nekopara, etc.) where distributing a real installable title
matters. Forwarders are a lighter-weight, complementary mechanism: one
shared engine binary (the `.3dsx`) lives on the SD card as usual, launched
via the Homebrew Launcher; each installed novel gets a tiny separate
CIA — a "forwarder" — whose only job is to relaunch the Homebrew Launcher
with that novel's folder pre-selected, skipping the in-app picker menu
entirely. The forwarder itself runs no VN logic; it exists purely to give
the novel its own icon, banner, and title on HOME Menu without
rebuilding/repackaging the whole engine per game.

**Why forwarders make sense for this project specifically:** VN3DS-CHARM
already centralizes all installed novels under `sdmc:/novels/<name>/`
behind a single shared engine binary and an in-app picker (`main.moon`'s
`love.load`, which lists `/novels/` and lets the player choose, already
reading each novel's own icon/thumbnail image for the picker UI).
Forwarders let each of those folders *also* surface as its own HOME Menu
icon, without needing a full per-title engine rebuild the way Phase 4.1's
CIA packaging does — appropriate for the common case of "I ported several
visual novels onto one SD card and want each to look like its own game,"
distinct from "I'm shipping one finished, polished, standalone title."

**Mechanism (standard 3DS homebrew forwarder pattern):**
1. A minimal native executable (built with devkitARM + libctru — *not*
   part of the LÖVE Potion/MoonScript engine; a small stub analogous to
   existing community forwarder-generation tools) that uses the Homebrew
   Launcher's argument-passing convention to boot the engine `.3dsx` with
   an argument pointing at a specific `sdmc:/novels/<name>/` folder,
   bypassing the in-app picker and jumping straight into that novel.
2. `bannertool`/`3dstool` (or equivalent, current-at-implementation-time
   tooling) produce the per-novel icon and banner (including the launch
   jingle) from that novel's own icon/thumbnail image — files the in-app
   picker already expects to exist per novel, so no new asset authoring is
   needed.
3. `makerom` packages the stub + icon + banner into a `.cia`, titled with
   the novel's display name (from `manifest.json`), installable via any
   standard CIA installer.

**Scope and sequencing:** This is packaging/distribution polish, not core
engine or converter work — it doesn't change `script.vnds`, the Problem
Report, or any conversion behavior. Targeted for **Phase 4** alongside
`makerom` CIA packaging (§13, item 4.1), since both need the same
signing/packaging toolchain investigation; whether forwarders replace,
complement, or are offered as an alternative to full per-title CIA builds
should be decided there, based on how many titles are typically installed
side by side by that point in the project.

**Open questions, deliberately left unresolved here** (both depend on the
CFW/homebrew-launcher ecosystem at implementation time, which evolves
independently of this project — verify current tooling and conventions
before implementing rather than assuming anything named above is still
current):
- Whether to target the Homebrew Launcher's argv-passing convention
  directly, or use an existing forwarder-generation tool.
- Whether per-novel forwarders are produced by the desktop-side Converter
  (as part of its output bundle) or by a separate packaging step the user
  runs after copying new novels onto the SD card.

---

## 6. Supported Ren'Py Subset (the conversion map)

This table is the heart of the Converter. Everything in "Converts" becomes an instruction; everything in "Flagged" becomes a Problem Report entry plus (where possible) a runtime placeholder.

| Ren'Py construct | Disposition | Engine instruction / note |
|---|---|---|
| `label`, `jump`, `call`, `return` | Converts | flow ops; `call`/`return` use an engine call stack |
| `scene`, `show`, `hide` (+ `at left/center/right`) | Converts | `scene` / `show` / `hide`; custom positions → nearest of L/C/R, flagged `approximated` |
| `say` statements | Converts | `say` (who, what) |
| `define c = Character("Name", color="#..")` | Converts | character table (name + color) |
| `menu:` with choices | Converts | `menu` → touch buttons on bottom screen |
| `if` / `elif` / `else` (simple conditions) | Converts | `if` op evaluated by the expression evaluator |
| `$ var = <simple expr>` , `default`, `define` of literals | Converts | `set` op; vars are int/bool/string only |
| `with dissolve` / `with fade` | Converts | transition flag on next scene/show |
| `play`/`stop`/`queue` music\|sound\|voice | Converts | `play` / `stop` on a channel; file re-encoded to OGG |
| `pause <n>` | Converts | `pause` op |
| `window show` / `window hide` | Converts | toggles dialogue box visibility |
| Text tags `{b}{i}{color}{w}{p}{size}` | Converts | inline markup in `say`; unknown tags flagged `approximated` |
| `nvl` mode | Converts (route to top screen) | flagged `approximated` if layout is custom |
| `init python:` / non-trivial `$` Python | **Flagged** `blocking` or `manual` | placeholder no-op; needs native reimplementation |
| `screen` language (custom screens) | **Flagged** `manual` | default screens provided natively; custom ones stubbed |
| ATL `transform` / animation blocks | **Converts** (common patterns) / **Flagged** `approximated` (complex) / **Flagged** `manual` (shader effects) | Common ATL patterns → `anim` preset or keyframe block (§9.1); unknown patterns flagged `approximated` with nearest safe fallback; shader/particle effects flagged `manual` |
| Custom displayables, `renpy.*` calls | **Flagged** `blocking`/`manual` | — |
| `movie` / video | **Flagged** `manual` | — |
| Live2D / spine | **Flagged** `manual` | Mesh deformation impossible on PICA200. Converter emits placeholder static sprite + detailed `manual` flag with segmentation instructions (§9.2). Multi-layer (Option A) or bone/puppet (Option B) system used as replacement after manual art pipeline step. |
| `persistent.*`, achievements | **Flagged** `manual` | — |

### 6.1 Expression evaluator (Engine)

A small, safe evaluator — **not** Python. Supports:
- Types: int, bool, string
- Operators: `+ - * /`, `== != < <= > >=`, `and or not`
- Variables defined via converted `default`/`define`/`set`
- No function calls, no attribute access, no object model

Any expression referencing a function call, object attribute, list/dict, or `renpy.*` is **not** evaluated — it is flagged at convert time and the containing branch is reported as `blocking` (because flow may depend on it).

---

## 7. The Problem Report (first-class output)

`problems.json` is emitted on every conversion run, even a clean one. It is the document a developer reads to port a game.

### 7.1 Severity levels

- **`blocking`** — The game cannot reach a correct state without human work (e.g., route flow depends on Python the evaluator can't run). Must be zero before "ported."
- **`manual`** — Converted to a placeholder/stub; needs a human to reimplement natively (custom screen, ATL animation, achievements).
- **`approximated`** — Converted, but behavior simplified (a transition downgraded, a custom sprite position snapped to L/C/R, an unknown text tag dropped). Playable as-is; review for fidelity.
- **`info`** — Noted, no action needed (e.g., a 1280×720 background downscaled to 400×240).

### 7.2 Schema

```json
{
  "game": "Hustle Cat",
  "converter_version": "0.1.0",
  "generated": "2026-06-28T22:14:00Z",
  "summary": { "total": 0, "blocking": 0, "manual": 0, "approximated": 0, "info": 0 },
  "items": [
    {
      "id": "P0001",
      "severity": "manual",
      "category": "screen",
      "source": "screens.rpy:212",
      "ren_py": "screen main_menu(): ...",
      "message": "Custom main menu screen cannot be auto-translated.",
      "suggestion": "Use the engine's native title screen, or reimplement this screen's buttons as engine menu entries."
    }
  ]
}
```

`category` ∈ `python | screen | atl | displayable | video | text-tag | audio | asset | flow | unknown`.

### 7.3 Acceptance criteria for the Problem Report

- [ ] Every flagged construct produces exactly one item with a resolvable `source` (`file:line`).
- [ ] `ren_py` contains the original snippet (truncated to a sane length) so the developer can find it.
- [ ] `summary` counts match `items`.
- [ ] A fully-convertible game produces `problems.json` with `summary.total == 0`.
- [ ] The Converter exits non-zero if any `blocking` items exist (so it can gate a build script), zero otherwise.
- [ ] A human-readable rendering (`problems.md` or console table) is produced alongside the JSON.

---

## 8. Converter Requirements

### P0 — must have
- [ ] Parse `.rpy` source for the subset in §6 into the script IR (§12).
- [ ] Emit `manifest.json`, `script.vnds`, `problems.json`.
- [ ] Re-encode images to `.t3x` atlases and audio to streamed OGG (§10).
- [ ] Produce the Problem Report per §7, gating on `blocking`.
- [ ] Deterministic output (same input → same bundle) for diffable runs.

### P1 — nice to have
- [ ] Asset atlasing/packing to minimize texture count.
- [ ] `problems.md` rendering with grouping by severity/category.
- [ ] Partial re-convert (only changed labels/assets).

### P2 — future
- [ ] A sliver of screen-language translation for the most common menu patterns.
- [ ] Heuristic auto-stubs for common `persistent`/achievement patterns.

---

## 8.1 DLC Handling

### How Ren'Py DLC works (Our Life: Beginnings & Always as reference)

Ren'Py DLC is distributed as additional `.rpa` archives dropped into the `game/` folder alongside the base game's own archives. Ren'Py merges all `.rpa` archives at runtime into one unified namespace — DLC scripts define new labels and assets that the base game's scripts reference by name. No DRM or unlock mechanism exists in the files themselves; presence of the archive is the only gate. If a DLC archive is absent, Ren'Py raises `ScriptError: could not find label` and crashes.

Our Life's Step DLCs each add five new Moment scenes, new sprites, new backgrounds, and one new CG. Some DLC Moments are also referenced in later Steps (e.g. a character recalling an event from an earlier DLC Moment), creating cross-step references that span both base game and DLC content.

### Converter behaviour with DLC

**The converter treats base game + DLC as a single merged source tree.** Before conversion, all `.rpa` archives in the `game/` directory — base game and DLC alike — are extracted into a unified working directory. The converter then processes this merged directory as if it were one game with no distinction between base and DLC content. The output bundle is a single complete self-contained package.

This is actually *simpler* than the PC runtime approach: Ren'Py's dynamic archive-merging is replaced by a static offline merge step at convert time. The 3DS engine never needs to know about DLC — it just reads `script.vnds` as one file.

**DLC present at convert time:** Moments are included in the bundle. The converter processes them identically to base game content.

**DLC absent at convert time:** The converter encounters `jump` or `call` instructions targeting labels that don't exist in the source tree. These are flagged as a dedicated Problem Report category:

```json
{
  "id": "P0088",
  "severity": "blocking",
  "category": "missing-dlc",
  "source": "script/step1.rpy:441",
  "ren_py": "jump library",
  "message": "Label 'library' not found. This is likely a DLC Moment (Step 1 DLC). Install the DLC and re-run the converter to include this content, or remove the jump if intentionally omitting this Moment.",
  "suggestion": "Add dlc_step_1.rpa to the game/ folder and re-run."
}
```

The `missing-dlc` category is distinct from `flow` errors so the developer immediately knows the cause is missing content rather than a converter bug.

**Partial DLC (some but not all DLC installed):** Supported naturally — the converter includes whatever DLC archives are present and flags only the missing ones. A player can port the base game alone and add DLC content later by re-running the converter with the additional archives present.

### Cross-step DLC references

Our Life's DLC Moments can be referenced in later Steps regardless of whether the player experienced them. In the original Ren'Py game, the base game checks for the existence of DLC Moments using `persistent` variables set when a Moment is played. On VN3DS-CHARM, since DLC content is baked into the bundle at convert time rather than dynamically loaded, this simplifies to: if the DLC was present at convert time, the cross-references are valid labels in `script.vnds`; if not, they're flagged `missing-dlc`. No runtime check needed.

### General DLC policy for all supported engines

The same merge-at-convert-time approach applies to DLC for any supported engine:

- **Ren'Py:** Extract all `.rpa` archives together before conversion.
- **KiriKiri (Phase 6b):** Extract all `.xp3` archives (including DLC patch archives) together before conversion.
- **NScripter (Phase 6a):** Merge all `.sar`/`.nsa` archives before conversion.
- **RealLive (Phase 6e):** Merge all `.seen` and asset archives before conversion.

The principle in every case: the converter consumes a complete merged source tree and produces one complete self-contained bundle. DLC is a converter input concern, not an engine runtime concern.

The engine is a fork of VNDS-LOVE running under LÖVE Potion on 3DS. The fork adds new VNDS commands (§5.1) and 3DS-specific rendering fixes. Reference implementations to study before writing engine code:
- **DDLC-LOVE** (GPL-3.0) — sprite handling, text box rendering, transitions, save state under LÖVE Potion
- **Higurashi 3DS port** (GBAtemp #492390) — chapter/save system design, image scaling, fade transitions
- **VN3DS (original)** (GBAtemp #396564) — IF/FI nesting counter pattern for `ifvar` implementation

### P0 — must have
- [ ] VNDS-LOVE fork boots in Azahar (N3DS profile) and on hardware under LÖVE Potion.
- [ ] Dual-screen render: backgrounds + sprites on top (400×240), dialogue box + name box + choices on bottom (320×240).
- [ ] Interpret standard VNDS commands: `text`, `bgload`, `setimg`, `sound`, `music`, `choice`, `jump`, `delay`, `if/fi`.
- [ ] Extended commands: `transition`, `clearimg`, `nameplate`, `setvar`, `ifvar`, `call`/`return`, `voiceover`, `stopmusic`, `stopsound`, `window`.
- [ ] Word-wrap text, typewriter reveal, advance on **A** or **screen tap**.
- [ ] Touch selection of `choice` buttons on the bottom screen.
- [ ] Streamed OGG audio (music loop + sfx + voice channels).
- [ ] Save/load of current script position and variable state.

### P1 — nice to have
- [ ] Text tags (`{b}{i}{color}{size}`), per-character name box colors.
- [ ] Dissolve/fade transitions between `bgload` calls.
- [ ] `nvlmode` (NVL text routed to top screen).
- [ ] Rollback/history (bounded depth).
- [ ] Settings screen: text speed, BGM/SFX volume.

### P2 — future
- [ ] `touchscene` command: load a Lua module for bespoke touch interaction scenes (Sucker for Love ritual segments etc.).
- [ ] Multi-VN library/launcher menu.
- [ ] CIA packaging via makerom with per-game icon/banner.
- [ ] Performance profiling pass for asset-heavy titles (Slay the Princess, Yousei).

### Fallback contingency
If LÖVE Potion performance proves insufficient on Old 3DS for a specific title (measured in Phase 0 stress test, not assumed), the Converter's output format is simple enough to retarget to a native C/citro2d engine. The converter is the valuable artifact; the engine is swappable. The Phase 0 O3DS stress test is the gate that confirms whether this contingency is needed at all.

---

## 9.1 Animation System (VN3DS-CHARM native animation, replaces ATL)

### Why this is viable

LÖVE's `love.graphics.draw` accepts position (x, y), rotation (r), scale (sx, sy), and origin offset (ox, oy) as native per-draw-call parameters that go directly to the PICA200 GPU via citro2d — they are hardware-accelerated transforms, not software operations. `love.graphics.setColor` with alpha is also confirmed working under LÖVE Potion 3.0 via citro2d's tinting mode. This means every property that matters for VN animation — position, alpha, scale, rotation — is a free GPU transform on every sprite draw call. The CPU cost per animated sprite per frame is a handful of arithmetic operations for tween interpolation.

What is **not** available: pixel/fragment shaders (PICA200 is fixed-function). Blur, chromatic aberration, per-pixel distortion, and similar effects are hardware-impossible. Everything else is viable.

### Tween engine

The animation system is built on **flux** (rxi, MIT license), a minimal Lua tween library designed for LÖVE. flux interpolates numeric properties of a Lua table over time using standard easing functions. It is tiny (~150 lines), well-tested in the LÖVE ecosystem, and has no dependencies. Each animated sprite maintains a state table:

```lua
-- sprite state table (one per on-screen sprite)
sprite = {
  image = img,
  x = 160, y = 120,    -- position on top screen
  r = 0,               -- rotation in radians
  sx = 1.0, sy = 1.0,  -- scale
  alpha = 1.0,         -- opacity (0.0–1.0)
  ox = 0, oy = 0,      -- origin offset
}

-- drawn each frame as:
love.graphics.setColor(1, 1, 1, sprite.alpha)
love.graphics.draw(sprite.image, sprite.x, sprite.y,
                   sprite.r, sprite.sx, sprite.sy,
                   sprite.ox, sprite.oy)
```

flux animates any numeric field on the state table. The engine updates all active tweens each frame via `flux.update(dt)` in `love.update`.

### Preset library

Named presets cover the ATL patterns that appear in the vast majority of real VNs. Each preset is a short Lua function that fires a flux tween on the target sprite's state table. New presets can be added without touching the command parser.

| Preset name | What it does | Typical duration |
|---|---|---|
| `enter_fade` | alpha 0→1 | 0.3s |
| `exit_fade` | alpha 1→0, then hide | 0.3s |
| `enter_left` | x from off-left + alpha 0→1 | 0.4s |
| `enter_right` | x from off-right + alpha 0→1 | 0.4s |
| `exit_left` | x to off-left + alpha 1→0 | 0.3s |
| `exit_right` | x to off-right + alpha 1→0 | 0.3s |
| `enter_bottom` | y from off-bottom + alpha 0→1 | 0.4s |
| `pulse_zoom` | sx/sy 1.0→1.08→1.0 | 0.3s |
| `shake` | rapid x oscillation (±8px, 6 cycles) | 0.4s |
| `bounce_in` | scale 0→1.1→1.0, ease bounce | 0.5s |
| `fade_out_black` | overlay alpha 0→1 (scene transition) | 0.5s |
| `fade_in_black` | overlay alpha 1→0 (scene transition) | 0.5s |
| `flip_h` | sx 1→-1 (horizontal flip) | instant |

### Keyframe form (custom animations)

For ATL patterns that don't match a preset, the converter emits a keyframe block and flags it `approximated`. The developer can tune the keyframes directly in the `script.vnds` or via the Triage Workbench animation preview (Phase 5.5):

```
anim_begin char_hero 0.6 ease_out
  keyframe 0.0  x=80   alpha=0  sx=0.8  sy=0.8
  keyframe 0.5  x=160  alpha=1  sx=1.05 sy=1.05
  keyframe 1.0  x=160  alpha=1  sx=1.0  sy=1.0
anim_end
anim_wait char_hero
text "Hello."
```

`anim_wait` pauses script execution until the named animation completes. Omitting it lets the animation run in parallel with the next command (e.g. dialogue starting while a sprite slides in).

### ATL → VN3DS-CHARM converter mapping

The converter pattern-matches common ATL blocks and emits the nearest equivalent. Unknown patterns are flagged `approximated` with the original ATL shown for reference:

| ATL pattern | Converter output |
|---|---|
| `at left` / `at right` / `at center` (static) | `setimg <file> left/right/center` (no animation) |
| `Transform: xalign 0.0, alpha 0 → xalign 0.0, alpha 1` | `anim X enter_fade 0.3` |
| `Transform: xpos -100 → xpos 160` with alpha | `anim X enter_left 0.4` |
| `MoveTransition` or `EaseIn/EaseOut` slide | `anim X enter_left/right <dur>` flagged `approximated` |
| `ZoomInTransition` or zoom ATL | `anim X pulse_zoom <dur>` flagged `approximated` |
| `Shake` or rapid position oscillation | `anim X shake <dur>` |
| `alpha 1 → alpha 0` | `anim X exit_fade <dur>` |
| ATL with `init python:` or function calls | `# FLAGGED P00XX` + `anim X enter_fade 0.3` (nearest safe fallback) |
| `renpy.pause`, `time`, multi-block chained ATL | keyframe block, flagged `approximated` |

### Hardware limits and guardrails

**CPU context:** The Old 3DS ARM11 runs at 268MHz — roughly 3× slower than New 3DS's 804MHz. The GPU (PICA200) is identical on both models, so all rendering transforms are equally cheap. The CPU constraint affects Lua execution, tween arithmetic, and spring physics calculations. For a VN these are minimal loads, but they compound with simultaneous animations and bone traversal.

- **Simultaneous tween animations:** Hard limit of **4 concurrent active tweens** targeting the engine on Old 3DS. This includes sprite enter/exit animations and any idle motion loops counted as active tweens. The idle breathing loop is implemented as a repeating low-cost sine offset in `love.update` rather than a flux tween, so it does not count against this limit. The engine logs a warning if this limit is exceeded at runtime. N3DS has no practical ceiling for VN use cases.
- **No shader effects:** Blur, glow, colour grading, and distortion effects from ATL are flagged `manual` — they are hardware-impossible on PICA200 regardless of model.
- **Rotation and scale are GPU-free:** These are PICA200 matrix operations; they cost nothing on either model. No limit.
- **Lua GC pressure:** Avoid creating new tables or closures per-frame inside `love.update` and `love.draw`. Pre-allocate sprite state tables at scene load. On O3DS the 268MHz ARM11 makes GC pauses more visible than on N3DS.

---

## 9.2 Live2D Replacement System

### What Live2D actually does (Nekopara as reference)

Nekopara's Live2D provides several distinct effects that need separate solutions:

- **Idle breathing/body sway** — continuous gentle oscillation of torso, hair, ears, and clothing running perpetually while a character is on screen.
- **Physics simulation** — secondary motion on hair, tails, cat ears, and clothing that reacts to body movement with lag and damped bounce.
- **Layered expression morphing** — eyes, eyebrows, and mouth are separate mesh layers that deform and blend independently; a character can blink while smiling while showing a head tilt simultaneously.
- **Motion presets** — named animations (happy bounce, surprised flinch, sad droop) that play over the idle and return to it.

Live2D achieves this through **real-time mesh deformation** — each layer of the original illustration is a polygon mesh that the runtime warps per-frame. The 3DS PICA200 GPU is fixed-function and has no geometry shader pipeline; it cannot run Live2D Cubism or any mesh deformation at playable framerates. The Live2D SDK itself is also proprietary and cannot be embedded. **Sprite sheet swapping is explicitly rejected** — for a title like Nekopara with dozens of expression combinations per character, pre-rendering every state as a full sprite would cause unacceptable asset bloat and blow the VRAM budget before a single scene loaded.

The replacement approach is therefore layered: a **multi-layer compositing system** (P1, implemented in Phase 3) that covers most cases with available source art, and a **bone/puppet animation system** (P2, Phase 4 stretch) that handles the full range of lively character movement without requiring mesh deformation.

---

### Option A — Multi-layer composited sprite animation (P1)

**How it works:** The character sprite is separated into independent texture layers — at minimum: body, left eye, right eye, eyebrows, mouth, hair, accessories. Each layer is a separate `.t3x` texture, sized to the full sprite canvas with transparency outside the part. The engine composites them in draw order each frame, applying per-layer transforms via `love.graphics.draw`. Since all transforms are GPU-accelerated PICA200 operations, compositing 8–10 layers per character costs nothing meaningful in performance.

**What this enables:**
- **Blinking** — scale the eye layers' sy toward 0 and back via a looping flux tween; interval randomised between 2–5 seconds for naturalism.
- **Breathing** — the entire character (all layers) drift ±3px on a slow sine wave; hair and accessories get a small additional offset on a slightly different frequency for secondary motion.
- **Expression changes** — swap the mouth, eye, and eyebrow textures independently. A character can go from neutral-eyes + closed-mouth to wide-eyes + open-mouth by swapping two layers, no full sprite change required.
- **Hair/ear/tail sway** — sinusoidal oscillation of accessory layers on their own frequency, slightly out of phase with the body.
- **Physics approximation** — for physics-driven parts (hair, tails, loose clothing), a damped spring tween on the layer's x/y offset, triggered whenever a motion preset fires and decaying back to rest position. Not true physics simulation, but convincingly similar for VN purposes.

**VRAM and RAM budget for Option A:** O3DS has ~80–90MB usable RAM total. LÖVE Potion runtime itself consumes a portion of this. Working budget for VN content: target ≤40MB RAM in use at any point during gameplay (textures + audio buffers + Lua VM + engine state). For multi-layer characters: 8–10 layers per character at sub-canvas size with alpha (ETC1A4) ≈ 80–120KB per layer ≈ 800KB–1.2MB per character. **One character on screen: well within budget. Two characters simultaneously: tight on O3DS — keep to a maximum of 2 simultaneous layered characters and aggressively free layers on character exit.** Three simultaneous layered characters: not supported on O3DS; the converter should flag scenes with 3+ Live2D characters as requiring manual memory review.

**Extended VNDS commands for multi-layer sprites:**
```
# Define a layered character (replaces single setimg for Live2D characters)
deflayer char_vanilla body      vanilla_body.t3x
deflayer char_vanilla hair      vanilla_hair.t3x
deflayer char_vanilla eye_l     vanilla_eye_l.t3x
deflayer char_vanilla eye_r     vanilla_eye_r.t3x
deflayer char_vanilla eyebrow   vanilla_eyebrow_neutral.t3x
deflayer char_vanilla mouth     vanilla_mouth_closed.t3x

# Show layered character (engine begins idle breathing + blink loop automatically)
showlayer char_vanilla center

# Swap expression layers independently
swaplayer char_vanilla mouth     vanilla_mouth_smile.t3x
swaplayer char_vanilla eyebrow   vanilla_eyebrow_raised.t3x

# Play a named motion preset (body bounce, hair follows with spring lag)
motion char_vanilla happy_bounce

# Hide layered character
hidelayer char_vanilla
```

**Source art requirement:** Layer separation cannot be done by the converter from a composed sprite — it requires the original layered PSD or equivalent source art. The converter flags any Live2D character as `manual` with a clear message: *"Character [X] uses Live2D. Segment source art into layers and define with `deflayer` commands. See §9.2 for layer naming conventions."* This is honest — it's a human art pipeline step, not something automatable from distributed game files.

**Motion preset library (mirroring §9.1 tween presets):**

| Preset | Body | Hair/accessories | Eyes | Duration |
|---|---|---|---|---|
| `idle` | ±2px Y sine, 3s period | ±4px X sine, 2.7s period, phase offset | random blink every 2–5s | looping |
| `happy_bounce` | +8px Y, return ease-out | spring follow | brief widen | 0.4s |
| `sad_droop` | −4px Y slow | slow droop | narrow slightly | 0.6s |
| `surprised` | −6px Y fast | snap up | widen + brow raise | 0.25s |
| `nod` | −3px Y, +3px, return | spring follow | — | 0.5s |
| `shake_head` | ±8px X oscillate x3 | spring follow | — | 0.5s |
| `flinch` | −10px Y snap + return | sharp spring | widen | 0.2s |
| `laugh` | rhythmic Y bounce x3 | bounce follow | — | 0.6s |

---

### Option B — Bone/puppet animation system (P2 stretch, Phase 4)

**How it works:** The character sprite is segmented into rigid rectangular pieces — roughly the same segments as option A but treated as connected bones in a hierarchy rather than independent layers. Each piece is a texture quad. The engine maintains a bone tree (root → torso → head → hair, root → upper_arm → lower_arm → hand, etc.) and applies cumulative transforms down the hierarchy each frame. A rotation of the torso bone automatically moves the head, hair, and arms with it.

This is **not** mesh deformation — each piece remains a rigid rectangle. The visual style is closer to quality Flash-era animation or a paper theatre effect: distinctly jointed, but very much alive, and with a charm of its own. For VN use (characters mostly standing, expressing, occasionally gesturing) it looks excellent.

**What this adds over Option A:**
- Arm and hand gestures — characters can reach forward, point, cross their arms via bone rotations.
- Head turns — rotating the head bone creates a natural-looking head turn if the face segment and hair are separate bones.
- Full body motion presets — a "lean forward excited" or "shrink back scared" involves moving multiple bones in coordinated ways.
- Spring physics per bone — each bone can have a spring constant and damping, so hair and clothing bones trail behind motion naturally and settle with visible overshoot. This approximates Nekopara's physics more convincingly than option A's simple sine offset.

**Bone definition format** (stored in `scenes/bones/char_name.lua`):
```lua
-- Bone definition for a character
return {
  root = {
    texture = "char_vanilla_torso.t3x",
    x = 200, y = 120,           -- anchor on top screen
    children = {
      head = {
        texture = "char_vanilla_head.t3x",
        offset = {0, -80},       -- relative to parent origin
        spring = {k=0.3, d=0.7}, -- spring constant, damping
        children = {
          hair_front = { texture="char_vanilla_hair_front.t3x",
                         offset={0,-20}, spring={k=0.2, d=0.5} },
          eye_l      = { texture="char_vanilla_eye_l.t3x",
                         offset={-18,-10} },
          eye_r      = { texture="char_vanilla_eye_r.t3x",
                         offset={18,-10} },
          mouth      = { texture="char_vanilla_mouth_neutral.t3x",
                         offset={0, 10} },
        }
      },
      arm_l = {
        texture = "char_vanilla_arm_l_upper.t3x",
        offset = {-40, -20},
        children = {
          forearm_l = { texture="char_vanilla_arm_l_lower.t3x",
                        offset={0, 40}, spring={k=0.4, d=0.6} }
        }
      },
      -- etc.
    }
  }
}
```

**VNDS command:**
```
loadpuppet char_vanilla  vanilla_bones.lua
showpuppet char_vanilla  center
puppet_motion char_vanilla  happy_bounce
swaplayer char_vanilla mouth  vanilla_mouth_smile.t3x  -- reuses swaplayer for texture swaps
hidepuppet char_vanilla
```

**Performance on Old 3DS:** Bone traversal for a 12-bone character is ~12 matrix multiplications per frame — cheap arithmetic even on the 268MHz ARM11. The spring physics adds a handful of multiply-adds per spring bone per frame. **Old 3DS budget: one fully-rigged puppet character simultaneously with comfortable headroom; two simultaneous puppet characters requires profiling and is not guaranteed.** Limit scenes to one active puppet character on O3DS unless profiling confirms two is safe. New 3DS handles two simultaneous fully-rigged puppets without issue. If a scene requires two Live2D-replacement characters on O3DS, prefer two Option A multi-layer rigs over two full Option B puppet rigs, as Option A's CPU cost per frame is lower.

---

### Converter behaviour for Live2D games

Regardless of which option is implemented, the converter's output for a Live2D game is consistent:

```
# FLAGGED P0042 [manual] [live2d]
# Character "vanilla" uses Live2D. Mesh deformation cannot run on 3DS hardware.
# ACTION REQUIRED: Segment the character's source art into layers (Option A)
# or bone pieces (Option B) and define using deflayer/loadpuppet commands.
# See spec §9.2 for layer naming conventions and motion preset library.
# Original Ren'Py show statement: show vanilla happy at center with dissolve
setimg vanilla_placeholder.t3x center   # placeholder pending manual work
```

The placeholder is a static composed sprite (exported from the game's assets at a single expression state) so the script is at least playable for testing while the manual animation work is done. The Triage Workbench (Phase 5.5) surfaces these items with a clear "segmentation required" workflow and opens the bone definition template in the user's editor when the user clicks "begin manual fix."

---

## 9.3 Combined System — Options A and B as a Unified Rig

Options A and B are not alternatives to choose between — they are complementary layers of the same rig, designed to work together. Option A handles everything **facial and expressive** (texture swaps for eyes, eyebrows, mouth, small accessories). Option B handles everything **structural and physical** (body segments that move together in a hierarchy with spring-based secondary motion). The two compose naturally because Option A's swappable texture layers sit *inside* Option B's bone hierarchy as leaf nodes, inheriting their parent bone's position and rotation automatically while remaining independently swappable.

### Combined hierarchy

A fully-rigged character using both systems looks like this:

```
bone: root  (torso — Option B, idle breathing oscillation)
├── bone: head  (Option B, follows torso with slight lag)
│   ├── layer: eye_l       ← Option A texture, swappable (blink, expression)
│   ├── layer: eye_r       ← Option A texture, swappable (blink, expression)
│   ├── layer: eyebrow     ← Option A texture, swappable (expression)
│   ├── layer: mouth       ← Option A texture, swappable (expression, lip sync)
│   ├── bone: hair_front   (Option B, spring physics — lags behind head motion)
│   ├── bone: ear_l        (Option B, spring physics — reactive to body motion)
│   └── bone: ear_r        (Option B, spring physics — reactive to body motion)
├── layer: body_base       ← Option A texture (static body illustration)
├── bone: arm_l  (Option B)
│   └── bone: forearm_l    (Option B, spring physics)
├── bone: arm_r  (Option B)
│   └── bone: forearm_r    (Option B, spring physics)
└── bone: tail             (Option B, spring physics — high spring constant,
                            visible overshoot, slow damping)
```

### How a motion plays out

When a `puppet_motion char_vanilla happy_bounce` fires:

1. The **root bone** (torso) tweens upward 8px and returns — the whole hierarchy moves.
2. The **head bone** spring-follows the torso with slight lag, overshoots slightly, and settles — natural head bob.
3. The **hair, ears, and tail bones** spring-follow the head with their own spring constants, each settling at a different rate — secondary motion that looks physically convincing without simulation.
4. Simultaneously, `swaplayer char_vanilla mouth vanilla_mouth_smile.t3x` swaps the mouth texture — the smile appears at the moment the bounce peaks.
5. The body returns to idle, and the spring bones damp out over ~0.5s.

The result covers the core Nekopara effect: lively body motion, convincing secondary physical elements, and clean independent expression control — all from GPU-accelerated rigid-body transforms and texture swaps.

### Implementation order

Option A **must be built first** (Phase 3) because:
- `swaplayer` is the mechanism that drives expression changes in both systems.
- The bone system (Option B, Phase 4) depends on `swaplayer` working correctly for leaf-node texture swaps.
- Building A first gives you working facial animation and idle breathing before the structural rig exists, so characters are already lively in Phase 3 even without full body motion.

Option B is then built on top in Phase 4, extending the existing layer system with the bone hierarchy and spring physics. No rework of Option A code is required — the bone runtime simply calls the existing `swaplayer` logic for its leaf nodes.

### Art pipeline for a combined rig

The artist segments the original character illustration (or source PSD if available) into:

- **Body base** — the static torso/clothing layer that rarely changes.
- **Facial layers** — eye_l, eye_r, eyebrow, mouth; each exported at multiple expression states (open/closed/smile/frown/wide/narrow etc.). These are the only assets that multiply by expression count, but since they're small sub-regions rather than full-canvas sprites, the VRAM cost is a fraction of full sprite sheet duplication.
- **Bone segments** — head, hair pieces, ears, tail, arm segments; each a rectangular crop from the illustration padded to power-of-two. These are single textures — no per-expression duplication needed.

Total asset count for a fully-rigged character: roughly 6–8 bone segment textures + 3–5 texture variants per facial layer (e.g. mouth: closed, open, smile, small-smile, frown) = ~25–35 textures per character. Compare to full sprite sheet duplication which would be hundreds of full-canvas textures for the same expression range. The combined system is both the highest-fidelity and the most asset-efficient approach available on the hardware.

---

## 10. Asset Pipeline & Memory Budget

**Hardware baseline:** All budgets are written against **Old 3DS** (128MB total RAM, ~80–90MB usable by homebrew, 268MHz ARM11, PICA200 GPU). New 3DS (~170MB usable, 804MHz ARM11, same GPU) runs all of the same content with headroom to spare and requires no separate budget analysis.

**Images.** Downscale to the panel that displays them (backgrounds → 400×240 top; UI → 320×240 bottom). Convert via `tex3ds` to `.t3x`. PICA200 needs power-of-two textures, so pad/atlas at convert time. Prefer ETC1 for opaque backgrounds (smallest format, GPU-native). Use ETC1A4 for anything requiring alpha (sprites, UI elements, all multi-layer/bone rig segments). RGBA8 only for UI elements where colour fidelity is critical and size is small. For multi-layer/bone rig textures, ETC1A4 is mandatory throughout since all layers require transparency.

**Audio.** Keep as OGG/Vorbis, **stream** from SD via `ndsp` rather than decompressing whole tracks into RAM. One music channel (looping) + sfx/voice channels. On O3DS, never load a full audio file into RAM — streaming is non-negotiable, not optional.

**Memory working set targets (Old 3DS):**
- LÖVE Potion runtime + Lua VM: ~25–30MB (measured baseline, not controllable)
- Background texture (single, ETC1): ~200–400KB
- Sprite/layer textures for active characters: ≤8MB total across all characters on screen
- Audio streaming buffers: ~2–4MB
- Engine state, script, variable tables: ~2–4MB
- **Total target:** ≤45MB in use during active gameplay, leaving ~35–45MB of the usable budget as headroom for GC, OS calls, and spikes
- **Hard ceiling:** Never exceed 70MB in use; beyond this, O3DS crash risk increases significantly

**Working-set rules:**
- One background texture resident at a time; free the previous before loading the next.
- Sprites and layer textures: lazy-load at scene entry, free immediately on character exit — do not keep off-screen characters in memory.
- For multi-layer characters: free all layer variants that are not the currently displayed expression state. Only the active expression textures stay resident.
- Cap rollback history depth to **3 entries** on O3DS (configurable, default 3); each entry stores variable state only, not textures.
- Audio: never resident; always streamed.
- Lua tables: pre-allocate sprite state tables at scene load; avoid per-frame allocation in `love.update`/`love.draw` to minimise GC pressure on the 268MHz CPU.

**Acceptance criteria (Old 3DS):**
- *Jisei* plays from start to credits without crash or visible stutter.
- *Hustle Cat* plays through at least one full route without crash or visible stutter, with backgrounds and at least two simultaneous static sprites visible.
- Memory in use never exceeds 70MB during normal gameplay (measured via LÖVE Potion's memory reporting).
- New 3DS runs all of the above with no regressions.

---

## 11. Target Game Catalogue

Games are ordered by port difficulty. Each entry lists engine, structural complexity, known converter hot-spots, and status. The phase each game is targeted in is noted.

---

### 11.1 Jisei: The First Case *(Phase 1 — proof target)*
**Developer:** Sakevisual | **Engine:** Ren'Py | **Length:** ~1.5 hrs | **Download:** 97 MB

**Why first:** Tiny footprint means asset budget is nearly irrelevant. Mystery/investigation structure uses clue flags and suspect state variables — exercises the expression evaluator in a clean, finite way. Fully voiced, so it proves the audio streaming pipeline early. Short enough that any manual Problem Report fixes are genuinely low-effort.

**Likely Problem Report hot-spots:**
- Investigation/clue-examination UI — may be `menu:` (converts fine) or custom `screen` (flagged `manual`; determine on first converter run).
- Title/main menu screen → `manual` (native title screen substituted).
- Persistent data for chapter unlocks → `manual` (ignorable for single playthrough).

**Definition of done:**
- [ ] Converter runs on Jisei `game/` folder; Problem Report produced.
- [ ] Zero `blocking` items after triage.
- [ ] Complete the game in Azahar (**Old 3DS profile**) from start to credits.
- [ ] Dual-screen layout, touch-to-advance, voiced lines audible, choices selectable by touch.
- [ ] Save/load mid-investigation works correctly.
- [ ] Memory in use stays below 70MB throughout (verified via LÖVE Potion memory reporting).

**Bonus:** Jisei has two sequels — *Kansei* and *Yousei* (8–9 hrs) — so a successful port is naturally extendable into a trilogy. Target these after Hustle Cat.

---

### 11.2 Hustle Cat *(engine corrected 2026-07-05 — needs re-scoping, no longer a Phase 2 target as written)*
**Developer:** Date Nighto / Pancake Games | **Engine:** ~~Ren'Py~~ **"htmlvn"** — Date Nighto's own proprietary HTML5/JavaScript VN framework, packaged as a desktop app via NW.js (Node-WebKit) | **Length:** moderate

**Correction (verified directly against the installed game files, not documentation):** this catalogue entry originally assumed Ren'Py. It is not. There is no `.rpy` source anywhere in the install — `images/htmlvn/` and the runtime's own `__HTMLVN_PRODUCTION__`/`__HTMLVN_BUILD_NUMBER__` globals (visible in `index.html`) confirm a bespoke engine, with all script/dialogue data compiled into a bundled `scripts/hustlecat.js`. The Ren'Py converter has nothing to parse here — **this is out of scope for every phase currently planned** (not Ren'Py, and not any of the Phase 6 engines either — NScripter, KiriKiri, TyranoScript, RealLive). Porting Hustle Cat would need an entirely new converter module reverse-engineering "htmlvn"'s own script format, a materially bigger undertaking than assumed. Demoted from "Phase 2 — first full port"; needs its own scoping decision before it belongs on any phase's target list again.

**Original (incorrect) rationale, kept for context:** conventional `say`/`menu`/`jump` structure with affection-gated romance routes was assumed to exercise the full P0 path without heavy asset volume or custom UI. None of this applies until "htmlvn"'s actual format is understood.

---

### 11.3 Sucker for Love: First Date *(engine corrected 2026-07-05 — needs re-scoping, no longer a Phase 3 target as written)*
**Engine:** ~~Ren'Py~~ **GameMaker: Studio** (`data.win` — GameMaker's own signature data file — confirmed present in the install; no `.rpy` source, no Ren'Py runtime folder) | **Complexity:** unknown until GameMaker's data format is investigated

**Correction (verified directly against the installed game files):** this catalogue entry also assumed Ren'Py, also wrongly — same developer as Hustle Cat, different (and also non-Ren'Py) engine. GameMaker's `data.win` bundles compiled game logic in GameMaker's own bytecode/format, entirely unrelated to Ren'Py's script model. **Out of scope for every phase currently planned**, same as Hustle Cat above — demoted from "Phase 3"; needs its own scoping decision (and likely its own converter module, decoding GameMaker's data format) before it belongs on any phase's target list again.

**Original (incorrect) rationale, kept for context:** cursor-driven ritual/interaction segments were assumed to map naturally to bottom-screen touch on the 3DS. May still be true structurally, but nothing about *how* to extract that structure from a GameMaker `data.win` has been investigated yet.

---

### 11.4 Am I Nima? *(Phase 3 — pending full release)*
**Engine:** Ren'Py (presumed) | **Status:** Full release expected October 2026

Hold until release. Verify engine and scope at that time. If it's standard Ren'Py with modest custom UI, slot after Sucker for Love.

---

### 11.5 Slay the Princess *(Phase 4)*
**Engine:** Ren'Py | **Complexity:** medium-high — branching is clean, but asset volume is heavy (full voice cast, large art set)

The label/jump branching structure converts well. The constraint is SD/RAM budget and delivery of a large asset set through the pipeline. Save for after asset atlasing and streaming are fully optimised in Phase 4.

---

### 11.6 Jisei sequels — Kansei & Yousei *(Phase 4, after 11.5)*
**Engine:** Ren'Py | **Length:** Yousei 8–9 hrs

Natural follow-on from the Phase 1 Jisei port. Kansei first (shorter), then Yousei. Mainly an asset pipeline and SD budget exercise since the structure mirrors Jisei.

---

### 11.7 Our Life: Beginnings & Always *(Phase 5 — hard)*
**Engine:** Ren'Py | **Complexity:** high — heavy custom screen language (character/customisation system, seasonal structure, persistent data), very long

The dialogue converts; the surrounding systems need significant native reimplementation. Tackle only after the custom-screen runtime stretch goal (Phase 4) is attempted.

---

### 11.8 Royal Alchemist *(Phase 5 — hard)*
**Engine:** Ren'Py | **Complexity:** high — stats-raising RPG with time management, quest system, two stats mechanics, 8 endings

Converter handles the dialogue cleanly; the game systems (stats UI, schedule screen, quest tracker, affection meters) are almost certainly custom screens requiring native reimplementation. Similar scope to Our Life. Treat as a companion project to Phase 5.

---

### 11.9 Nekopara Vol. 0 *(Phase 6b — primary E-mote/animation system stress test)*
**Developer:** NEKO WORKs / Sekai Project | **Engine:** KiriKiri Z + KAG | **Animation:** E-mote (M2 Co. Ltd.) | **Price:** Free on Steam

**Why Vol. 0 is the stress test:** Nekopara Vol. 0 is the right first target for the combined §9.2 A+B animation system — it's free, shorter than Vol. 1, and features only Chocola and Vanilla, giving a focused two-character test without the full main cast's asset load. It is still demanding enough to be a meaningful proof: both characters are on screen together throughout, both have continuous idle breathing, spring hair/ear/tail physics, and the full E-mote expression set. Passing Vol. 0 end-to-end on Old 3DS hardware proves the animation system works under real conditions at the O3DS texture budget ceiling. Vol. 1 follows naturally as a full-catalogue port once the pipeline is validated.

**Important engine/animation correction:** Nekopara is widely described as using "Live2D" but this is a common misreport. It uses **E-mote** (also written as Emote), developed by M2 Co. Ltd. — a distinct proprietary animation system with deep KiriKiri integration. E-mote and Live2D are architecturally similar (layered 2D parts, physics simulation, expression blending via parameter interpolation), so the §9.2 combined system is the correct replacement approach regardless. The distinction matters for the asset extraction pipeline.

**Asset extraction pipeline:**
- `.xp3` archives → `KrkrExtract` (or `GARbro` for some volumes)
- E-mote character models (`.psb` files in `emotewin.xp3` / `emotedx.xp3`) → `FreeMoteToolkit` (`EmtConvert` to pure `.psb`, `FreeMoteViewer` to inspect)
- KAG scripts (`.tjs` / `.scn` files in `data.xp3`) → `KrkrZSceneManager` / text editor for `.tjs`, Phase 6b KiriKiri converter for transpilation
- Background art, CGs, UI → standard image conversion to `.t3x`
- Audio → OGG re-encode for streaming

**What the KiriKiri converter handles:** The declarative KAG script — scene loads, character show/hide, dialogue, choices, BGM, jumps — converts mechanically via the Phase 6b converter. TJS2 scripting blocks are flagged `blocking`/`manual` per standard KiriKiri converter behaviour.

**What requires manual animation work (§9.2):** Every E-mote character model is a `manual` flag. The `.psb` models cannot be auto-converted to the VN3DS-CHARM bone/layer format — each character requires:
1. Export of individual body segments and facial layers from the `.psb` via `FreeMoteToolkit`
2. Manual segmentation into Option A facial layers (eyes, eyebrows, mouth, ear positions) and Option B bone segments (body, head, hair pieces, tail, ears as spring bones)
3. Authoring the bone definition file (`scenes/bones/char_name.lua`) per §9.2 spec
4. Building the motion preset library to approximate Nekopara's named E-mote motion set (idle, happy, sad, surprised, embarrassed, angry)

**Content note:** All Nekopara work in this project targets the **SFW Steam version** — the default censored release. The NSFW patch is out of scope. This means the adult CGs and associated physics are not present in the source content being extracted or ported.

**O3DS constraints:**
- Vol. 0 has Chocola and Vanilla on screen simultaneously throughout — the tight two-character case for O3DS. Each character uses aggressive layer management: only the active expression variant resident, all others freed immediately on expression change.
- Spring bone physics (tail, ears, hair, clothing) must be profiled on O3DS specifically at 268MHz. If two simultaneous puppet rigs cause CPU pressure, reduce spring bone count on the second character or switch it to Option A only for those scenes.

**Definition of done:**
- [ ] Phase 6b KiriKiri converter runs on Nekopara Vol. 0's extracted KAG scripts; Problem Report produced.
- [ ] Zero `blocking` items after triage.
- [ ] Chocola and Vanilla both rigged with combined Option A+B system.
- [ ] Idle breathing, randomised blink, spring hair/ear/tail motion, and motion presets (idle, happy, sad, surprised, embarrassed) operational on both characters.
- [ ] Both characters simultaneously on screen on **Old 3DS profile** in Azahar — both animated, memory under 70MB.
- [ ] Play through Vol. 0 end-to-end on Old 3DS hardware.
- [ ] Animation system fidelity vs. E-mote assessed and documented; findings feed back into §9.2 for Vol. 1 and future ports.

**Natural follow-on:** Nekopara Vol. 1 ports the full main cast using the rigging pipeline and motion preset library established in Vol. 0. Vol. 1 is a Phase 6b continuation target, not a separate phase — the hard work is done in Vol. 0.

---

### 11.10 CLANNAD *(Phase 6 — RealLive engine, long-term)*
**Developer:** Key / Visual Arts | **Publisher (Steam):** Sekai Project | **Engine:** RealLive (Key in-house) | **Length:** Very long — 6 routes + After Story, ~50+ hours for full completion

**Engine clarification:** CLANNAD runs on **RealLive**, Key's proprietary in-house engine — not KiriKiri. This is confirmed by the presence of `REALLIVE.sav` in the game's save directory. RealLive is distinct from both KiriKiri/KAG and Ren'Py and would require its own dedicated converter module, separate from the Phase 6b KiriKiri converter. Little Busters!, AIR, Kanon, and other Key titles on Steam also use RealLive or its successor, so building this converter unlocks the broader Key catalogue.

**Why it belongs on the list:** CLANNAD was specifically designed all-ages from the start — no adult content, no patch, no content concerns. It has been officially ported to PS Vita and Switch, confirming the content and structure work on handheld hardware. The 3DS is a natural home for it. The emotional story and its large cast of memorable characters make it one of the most requested VN ports in the community. It also has an existing Dangopedia reference system in the Steam version that would be an interesting native-screen implementation candidate.

**Complexity:** High. CLANNAD is one of the longest VNs in existence — six heroine routes in the School Life arc, plus After Story, plus numerous sub-scenarios, all required to unlock the true ending. The script volume alone is enormous. The branching is complex but declarative (no arbitrary scripting), so the converter itself is the main challenge rather than manual triage. The asset volume is also significant: HD visuals in the Steam version at 1280×960 all need downscaling to 400×240 for the top screen.

**Phase placement:** CLANNAD is a long-term target that requires:
1. A working RealLive converter (its own Phase 6 sub-module, not covered by 6a/6b/6c)
2. Proven O3DS memory management from earlier phases, given the script and asset volume
3. A native implementation of the Light Orb progression system (unlocking After Story requires collecting orbs from all routes — this is game state logic, not just dialogue flow)

It is aspirational at this stage and should be scoped only after the Phase 6b KiriKiri converter is complete and the overall pipeline is mature. Listed here to reserve its place and document the engine distinction clearly.

**Definition of done (aspirational):**
- [ ] RealLive converter module built and validated on a smaller Key title first (e.g. planetarian, which is a short kinetic novel on the same engine).
- [ ] CLANNAD converter runs; Problem Report produced; zero `blocking` items after triage.
- [ ] Light Orb progression system implemented natively.
- [ ] At least two full heroine routes playable end-to-end on Old 3DS hardware.
- [ ] After Story accessible after completing required routes.
- [ ] Memory under 70MB throughout; no crashes during long play sessions.

---

### 11.11 Just Kiss Him Already! *(candidate — unscheduled)*
**Developer:** Ekkoberry | **Engine:** Ren'Py | **Length:** ~1 hr, ~20k words | **Price:** Free (itch.io)

BL romance, standard Ren'Py structure, original art/music, no voice acting, player-customizable protagonist name. Small enough to be a good early smoke-test candidate alongside/after "The Question," similar in spirit to Jisei's role but even lighter.

---

### 11.12 Just Kiss Her Already! *(candidate — unscheduled)*
**Developer:** Ekkoberry (art by RaspberryBell) | **Engine:** Ren'Py | **Length:** ~20 min, ~4k words | **Price:** Free (itch.io)

Yuri companion piece to 11.11, same developer, even shorter. About as minimal a real Ren'Py VN as exists — a strong candidate for an extremely fast end-to-end triage/playthrough validation once the converter is stable.

---

### 11.13 Butterfly Soup *(candidate — unscheduled)*
**Developer:** Brianna Lei | **Engine:** Ren'Py | **Length:** 3–4 hrs | **Price:** Free (itch.io)

Well-known, well-regarded free VN — queer Asian-American teens playing baseball. Text-heavy, no special UI/minigames or voice acting reported, standard dialogue/choice structure. Localized into 9 languages (irrelevant to conversion, but indicates a clean, well-organized script). Good mid-length converter validation target — bigger than Jisei but structurally simpler.

---

### 11.14 Good Luck, Minutes Man! *(candidate — unscheduled)*
**Developer:** Asterhours | **Engine:** Ren'Py | **Length:** 1–2 hrs | **Price:** Free (itch.io)

Dream SMP fan visual novel, 5 endings + 1 secret ending. Standard Ren'Py branching; multiple endings suggest a moderate `if`/variable-state load, a reasonable exercise for the Phase 2 expression evaluator once picked up.

---

### 11.15 The Five Steps To Ensuring Momo Graduates Successfully!!! *(candidate — unscheduled)*
**Developer:** milkkylemon | **Engine:** Ren'Py | **Length:** Short (NaNoRenO 2022 entry) | **Price:** Free (itch.io)

Yuri/magical-girl short VN, 2 endings, original soundtrack. Small scope, standard structure — another fast validation candidate.

---

### 11.16 RE: Alistair++ *(candidate — unscheduled)*
**Developer:** Sakevisual — **same publisher as Jisei (11.1)** | **Engine:** Ren'Py | **Price:** Free (itch.io)

Otome dating-sim: "make new friends, balance schoolwork and fun, go shopping, search for the culprit" — this phrasing suggests schedule/stat-tracking mechanics similar in spirit to Hustle Cat (11.2) or Royal Alchemist (11.8), likely more custom-UI-dependent than a typical linear-choice VN; verify on first converter run before assuming Jisei-level effort. The developer's own itch.io page notes the original release uses "custom code" incompatible with newer Ren'Py versions, which may also affect what the decompiled/extracted source actually looks like — worth an early scoping pass rather than assuming it's a quick follow-on from Jisei just because it's the same studio.

---

### 11.17 Gender Bender DNA Twister Extreme *(candidate — unscheduled, likely Phase 4+ scope)*
**Developer:** Transcendent Studios | **Engine:** Ren'Py | **Length:** ~40 hrs, 13 playable characters/routes | **Price:** Paid (Steam, commercial — requires an owned copy, same as Jisei/Hustle Cat)

Comedic gender-bending ensemble story, 13 chapters each with its own protagonist and unique NPCs/love interests/endings. Substantially larger in scope than anything else in this catalogue except CLANNAD — closer to Our Life/Royal Alchemist territory in raw content volume, though (unlike those) nothing in available material suggests heavy custom-screen game systems, so it may convert more like "a much longer Jisei" than "a systems-heavy port." Verify on first converter run. Given the size, likely belongs alongside the Phase 4/5 asset-heavy titles rather than an early phase, primarily as an SD-budget and long-script-volume exercise.

---

### 11.18 Mice Tea *(candidate — unscheduled)*
**Developer:** Cinnamon Switch | **Engine:** Ren'Py | **Length:** moderate — four romanceable characters, each with multiple transformation branches and endings | **Price:** Paid (Steam/itch.io, owned copy required, same as Jisei/Hustle Cat)

Transformation-themed romance VN, structurally similar in shape to Hustle Cat/Sucker for Love (say/menu/jump with affection-style branching) rather than to the heavier custom-screen titles — four routes, each with its own set of transformation variants and multiple endings, plus 100+ illustrated CGs and an original soundtrack (streamed audio, no special handling expected beyond the existing pipeline). Likely converts cleanly through the existing P0/P1 subset; verify on first converter run whether the transformation-state tracking uses plain variables (converts) or custom screens (flagged). Adult content, same handling precedent as the NEKOPARA catalogue entries.

---

`script.vnds` is a plain-text extended VNDS file. Labels are marked with `@label`. One command per line. The Converter emits this directly; the Engine reads it top-to-bottom, branching on `jump`/`call`/`ifvar`.

```
# manifest.json carries character definitions (name, color) and entry label
# script.vnds carries the command stream

@start
bgload bg_cafe.png
transition dissolve 0.5
music theme.ogg
setimg avery_smile.png center
nameplate Avery
text Welcome to A Cat Cafe!
setvar affection 0
choice Hi there.|...
jump polite|shy

@polite
setvar affection affection+1
jump day1

@shy
jump day1

@day1
# ... continues
```

Notes:
- `choice` options are pipe-delimited; the engine maps them to touch buttons on the bottom screen. Each option corresponds to a `jump` target on the next line (also pipe-delimited).
- `ifvar` for in-line conditional branching: `ifvar affection >= 3 jump route_good`
- `call`/`return` maintain a call stack in the engine for shared subroutine labels.
- Flagged constructs emit a `# FLAGGED P0001` comment line followed by a no-op so the script stays parseable; the detail lives in `problems.json`.

---

## 13. Phase Plan & Roadmap

Each phase ends with a working, playable build and a clear deliverable. Hardware validation happens at the end of each phase; all iteration happens in Azahar.

---

### Phase 0 — Engine Fork Spike
**Goal:** Fork VNDS-LOVE, get it running under LÖVE Potion on Azahar, and prove dual-screen + touch work before writing any converter code.

- Fork VNDS-LOVE repo; strip to bare bones.
- Wire LÖVE Potion build (reference DDLC-LOVE's `Makefile` and `LovePotion.elf` setup).
- Hardcode a 3-line VNDS script: `bgload`, `text` x3, `choice`.
- Static image on top screen, text box and choice buttons on bottom screen.
- Advance on **A button** and **screen tap**; choice selectable by touch.
- No converter. No asset pipeline. Hardcoded everything.

**Reference:** Study DDLC-LOVE (GPL-3.0) for dual-screen layout, sprite rendering, and touch input under LÖVE Potion. Study the original VN3DS (GBAtemp #396564) for the LPP/LÖVE Potion VNDS command loop structure. Once the fork boots, load an existing VNDS community script (e.g. Tsukihime, Saya no Uta — freely available) as free smoke-test content before writing any converter code.

**Exit criteria:** `.3dsx` boots in Azahar (**Old 3DS profile**), shows image top + text/choice bottom, tap advances through 3 lines, choice touch-selectable, exits cleanly. **Additionally:** run a stress test — load a 400×240 ETC1 background, two ETC1A4 sprites, and stream an OGG music file simultaneously and confirm no crash or stutter. This is the O3DS baseline validation that gates Phase 1.

---

### Phase 1 — Walking Skeleton + Jisei Proof Port
**Goal:** Converter + Engine wired end-to-end; first real VN playable.

**Converter (P1):**
- Parse `.rpy` for `label/jump/call/return`, `scene/show/hide`, `say`, `Character()`, `menu:`.
- Emit `script.vnds` (extended VNDS format) + `manifest.json`.
- Emit `problems.json` (Problem Report) for everything not in the supported subset.
- Asset pipeline: image → `.t3x`, audio → `.ogg`.

**Engine (P1):**
- Interpret `script.vnds` flow ops, `scene/show/hide`, `say`, `menu`.
- Word-wrap text, typewriter reveal, advance on A/tap.
- Touch choice selection on bottom screen.
- Streamed OGG music via `ndsp`.

**Validation sequence:**
1. Run converter on Ren'Py's bundled **"The Question"** (ships with source, tiny). Expect zero `blocking` items.
2. Run converter on **Jisei**. Triage Problem Report to zero `blocking` items.
3. Play Jisei from start to credits in Azahar.

**Exit criteria:** §11.1 definition of done satisfied for Jisei.

---

### Phase 2 — Logic, State, Audio + Hustle Cat Port
**Goal:** Full game logic support; first romance VN playable.

**Converter additions:**
- `default`, `define` literals, `$ var = <expr>`, `if/elif/else`.
- `with dissolve/fade`, `play/stop/queue music|sound|voice`, `pause`.
- `window show/hide`, basic text tags `{b}{i}{color}{w}{p}{size}`.

**Engine additions:**
- Expression evaluator (§6.1): int/bool/string, arithmetic, comparisons, `and/or/not`.
- `set`/`if` ops, variable state.
- `play`/`stop` on music + sfx + voice channels.
- Save/load: current label, instruction index, variable state → serialized to SD.
- `pause` op, `window` toggle.

**Validation:**
- Run converter on **Hustle Cat**. Triage Problem Report to zero `blocking` items.
- Play at least one full route to an ending in Azahar.

**Exit criteria:** §11.2 definition of done satisfied for Hustle Cat.

---

### Phase 3 — Fidelity + Animation System + Sucker for Love / Am I Nima?
**Goal:** Polish the player experience; implement the native animation system; tackle the first game with bespoke interaction segments.

**Converter additions:**
- ATL pattern-matching: map common ATL blocks to `anim` presets and keyframe blocks per §9.1 conversion table.
- Unknown ATL patterns flagged `approximated` with nearest safe fallback emitted; shader/particle ATL flagged `manual`.

**Engine additions:**
- **Animation system (§9.1):** integrate flux tween library; implement `anim`, `anim_begin`/`anim_end`, `anim_wait` commands; full preset library (enter_fade, exit_fade, enter_left, enter_right, exit_left, exit_right, enter_bottom, pulse_zoom, shake, bounce_in, fade_out_black, fade_in_black, flip_h).
- **Multi-layer sprite system (§9.2 Option A):** `deflayer`, `showlayer`, `swaplayer`, `hidelayer`, `motion` commands; idle breathing loop, randomised blink, expression layer swapping, spring-offset physics approximation for hair/accessories; motion preset library.
- Dissolve/fade transitions between `bgload` scene changes.
- Colored name boxes per character definition.
- Bounded rollback/history (configurable depth).
- Settings screen: text speed, BGM volume, SFX volume.
- Bottom-screen choice button styling (highlight, touch feedback).
- `nvlmode` routed to top screen.

**Sucker for Love:**
- Run converter; triage Problem Report.
- Hand-author ritual/interaction segments as native bottom-screen touch scenes (one per flagged `manual` interaction).
- Play at least one route end-to-end.

**Am I Nima?** (if released by Oct 2026):
- Verify engine; run converter; triage; port.

**Exit criteria:** Sucker for Love playable end-to-end with all interaction segments reimplemented as touch scenes, and sprite enter/exit animations visibly running. (Am I Nima? is a stretch goal for this phase.)

---

### Phase 4 — Packaging, Optimisation + Bone/Puppet System + Slay the Princess / Jisei Sequels
**Goal:** Production-quality builds; handle asset-heavy titles; implement the full Live2D replacement system.

**Toolchain additions:**
- CIA packaging via `makerom` with per-game icon, banner, and title.
- Atlas optimisation: bin-packing sprites into fewer `.t3x` atlases.
- Multi-VN library/launcher menu on the engine's title screen.
- Partial re-convert (only changed labels/assets re-processed).

**Engine additions (stretch):**
- **Bone/puppet animation system (§9.2 Option B):** bone hierarchy format (`scenes/bones/`), `loadpuppet`/`showpuppet`/`hidepuppet`/`puppet_motion` commands, hierarchical transform traversal, per-bone spring physics (damped spring, configurable k and damping per bone). Reuses `swaplayer` for texture swaps within puppet rigs.
- Performance validation: two simultaneous fully-rigged puppet characters on N3DS without frame drop.

**Ports:**
- **Slay the Princess** — converter + triage; main constraint is asset pipeline throughput and SD budget. Verify it fits N3DS memory working set.
- **Kansei** (Jisei sequel) — straightforward follow-on; same structure as Jisei.
- **Yousei** (Jisei sequel, 8–9 hrs) — longer; mainly an asset volume and save-state exercise.

**Exit criteria:** At least two of the three ports playable end-to-end on **Old 3DS hardware** (not just Azahar), memory under 70MB throughout. CIA builds installable from SD. Bone/puppet system operational in at least one test character on O3DS.

---

### Phase 5 — Complex Ports + Custom Screen Runtime (stretch)
**Goal:** Tackle games with native game systems that need reimplementation.

**Engine stretch additions:**
- Minimal custom-screen runtime: enough to handle the most common menu/stats patterns without full native reimplementation per game.
- `persistent.*` stub layer for gallery/unlock systems.

**Ports:**
- **Our Life: Beginnings & Always** — dialogue converts; customisation/seasonal system needs native screens.
- **Royal Alchemist** — dialogue converts; stats-raising, quest, and schedule systems need native reimplementation (effectively building a small RPG layer on top of the VN engine).

**Exit criteria:** At least one full route of Our Life or Royal Alchemist playable, with core game systems functional (not necessarily complete parity with PC version).

---

### Phase 5.5 — Triage UI (converter front-end)
**Goal:** Replace the "read `problems.json` in a text editor and hunt through source files" workflow with a comfortable, purpose-built desktop UI that guides any user — not just the developer who built the converter — through resolving every flagged item.

**Motivation:** As of Phase 5, triaging the Problem Report requires: opening `problems.json`, finding the source file and line, understanding what the flagged construct does, deciding on a fix strategy, editing either the source `.rpy` or the output `script.vnds` directly, re-running the converter, and repeating. That loop is workable for a developer but is a significant barrier for anyone else. Phase 5.5 wraps that entire loop in a single application.

---

**Core UI concept — the Triage Workbench:**

A desktop app (cross-platform; Python + a lightweight UI framework such as tkinter, PySimpleGUI, or a small web UI served locally) that opens a VN3DS-CHARM project folder and presents:

- **Problem list panel** (left): all `problems.json` items sorted by severity (`blocking` → `manual` → `approximated` → `info`). Each item shows its ID, severity badge, category icon, and a one-line summary. Clicking an item focuses it.
- **Source context panel** (centre-top): the original `.rpy` (or other engine source) snippet from the flagged item, syntax-highlighted, with the offending construct highlighted in red. Read-only — the source is shown for context, not edited here.
- **Fix panel** (centre-bottom): the suggested fix from `problems.json`, with an editable text area pre-populated with a stub or suggested replacement in VNDS extended format. The user edits here and hits **Apply Fix** — which writes the override into a `fixes/` sidecar directory and marks the item resolved.
- **Preview pane** (right, optional): a lightweight script-stream preview showing what the converted output looks like around the fixed section, updated live as the user edits.
- **Run Converter button**: re-runs the converter with all applied fixes baked in, refreshes the problem list. Blocking count shown prominently — the goal state is `0 blocking`.
- **Export bundle button**: when `blocking == 0`, packages the bundle for Azahar/hardware drop-in.

---

**Fix strategies the UI supports:**

| Flag category | UI-assisted fix |
|---|---|
| `python` / `blocking` | Editable stub: user writes equivalent VNDS extended commands or marks as `skip` (no-op placeholder) |
| `screen` / `manual` | Choice: use engine native screen (title, save/load, choices) OR open stub Lua template in external editor |
| `atl` / `approximated` | Show the ATL block; show which preset was auto-applied; offer swap from preset dropdown with **live animation preview**; or let user write a custom keyframe block |
| `text-tag` / `approximated` | Show the unknown tag inline; offer "strip tag" or "replace with supported tag" from a dropdown |
| `audio` / `info` | Show the original filename and re-encoded output filename; confirm or override |
| `asset` / `info` | Show source resolution → target resolution; accept or flag for manual art resize |

---

**Fix persistence (the `fixes/` sidecar):**

Fixes are stored as a `fixes/overrides.json` sidecar in the project folder, keyed by Problem Report item ID. The converter reads `fixes/overrides.json` on every run and applies overrides before emitting the output. This means:
- The original source files are never modified.
- Fixes survive a converter re-run without needing to be re-applied.
- The fixes file is human-readable and diffable — a developer can inspect or hand-edit it if needed.
- Each entry records: `problem_id`, `strategy` (skip / replace / accept-approximation / native-screen), and `replacement` (the VNDS extended snippet, if applicable).

---

**P0 — must have:**
- [ ] Open a project folder; read and display `problems.json`.
- [ ] Source context panel: show flagged snippet from source file at the correct line.
- [ ] Fix panel: editable text area with pre-populated stub; Apply Fix writes to `fixes/overrides.json`.
- [ ] "Accept approximation" one-click for `approximated` items.
- [ ] "Mark skip" one-click for `blocking` items the user wants to no-op.
- [ ] Re-run converter button; problem list refreshes; blocking count updates.
- [ ] Blocking count displayed prominently; zero-blocking state visually celebrated (green, clear indicator).
- [ ] Export bundle button (active only when blocking == 0).

**P1 — nice to have:**
- [ ] Severity filter and category filter on the problem list.
- [ ] "All approximations" bulk-accept button for items the user is happy to ignore.
- [ ] Live VNDS script preview panel updating as fixes are applied.
- [ ] Per-item notes field (user can annotate why they made a particular choice).
- [ ] Fix history / undo per item.
- [ ] Progress bar: `N of M items resolved`.

**P2 — future:**
- [ ] Stub Lua template launcher: for `screen` / `manual` items, open a pre-scaffolded Lua file in the user's editor of choice for native screen implementation.
- [ ] Side-by-side "before/after" playback in a minimal desktop VNDS player for the section around a fix.
- [ ] Multi-game project switcher (library view of all VN3DS-CHARM projects in a folder).

---

**Exit criteria:**
- [ ] A person with no prior knowledge of `problems.json` or `.rpy` can open the Triage Workbench, work through a Problem Report for a previously-converted game (e.g. Hustle Cat), reach `0 blocking` items, and export a playable bundle — without opening a terminal or editing any file manually.
- [ ] Fix overrides survive a full converter re-run without being lost.
- [ ] Tested on at least one Ren'Py port (Hustle Cat) and one non-Ren'Py port (Phase 6a, NScripter title) to confirm the UI is engine-agnostic.

---

### Phase 6 — Multi-Engine Converter (post-Ren'Py, long-term)
**Goal:** Extend the converter toolchain to support additional popular VN engines, targeting the same VN3DS-CHARM engine. Ren'Py conversion remains primary and must be complete before any Phase 6 work begins. Phase 6 converters are independent modules — each is its own sub-project — and any one of them can be started without the others.

**Core principle:** The engine doesn't change. Every Phase 6 converter is just a new input parser that emits the same extended VNDS `script.vnds` + `manifest.json` + `problems.json` that the Ren'Py converter already produces. The Problem Report as a first-class output applies equally here — flag what can't be converted, don't silently miscompile.

---

#### 6a — NScripter / ONScripter
**Difficulty: Low — best first Phase 6 target**
**VNDB catalogue:** ~thousands of titles (Tsukihime original, Narcissu, Higurashi original scripts, Cross Channel, many classic Japanese VNs)

NScripter's script format is simple and well-documented — it was designed to be easy to author by hand. ONScripter is a mature open-source reimplementation (SDL-based, runs on DS/PSP/Android) whose source is the de facto format spec. The core command set (`lsp`/`csp`/`bg`/`ld`, text display, `goto`/`gosub`, `if`, `mov`, `play`/`playstop`, `click`, `select`) maps cleanly to VNDS extended commands. Scripts are plain text `.txt` files, no proprietary archive format to crack.

**Key advantage:** Many NScripter titles have already been converted to VNDS for the DS community (Tsukihime, Fate/Stay Night, Saya no Uta, Umineko, Higurashi, Cross Channel are all in the wild as VNDS). This means a working NScripter→VNDS-LOVE converter immediately unlocks that library with better quality than the old DS-era conversions (higher resolution, proper dual-screen layout, streaming audio).

**Main challenges:** NScripter's `lsp`/`csp` sprite layer system (multiple numbered layers) vs. VNDS-LOVE's positional model. Proprietary `.nsa`/`.sar` archive extraction needed for most distributed games (tools exist: `nsadec`, `sarconv`). Some titles use custom engine extensions.

**Suggested test title:** Tsukihime (NScripter original, VNDS scripts already exist as reference for comparison).

---

#### 6b — KiriKiri / KiriKiri Z (KAG script)
**Difficulty: High — most complex, highest catalogue value**
**VNDB catalogue:** ~6,800 titles (Fate/stay night, Fate/hollow ataraxia, Nekopara series, Little Busters!, Clannad, many Key titles, many TYPE-MOON titles)

KiriKiri's scripting language KAG (KiriKiri Adventure Game) is tag-based (similar syntax to TyranoScript, which is derived from it): `[image layer=base storage="bg.png"]`, `[chara_show name="hero"]`, etc. KiriKiri Z (the maintained fork) is open source. The declarative VN subset of KAG — scene loads, character display, text, choices, BGM, jumps — converts mechanically. The hard part is KiriKiri's embedded scripting language **TJS2** (TypeScript-like, Turing-complete), which is the equivalent of Ren'Py's arbitrary Python problem — anything in TJS2 blocks gets flagged, not converted.

Assets are stored in `.xp3` archives; extraction tools exist (`KrkrExtract`, `GARbro`). E-mote character models (used in Nekopara) are in `.psb` format inside `emotewin.xp3` / `emotedx.xp3` and require `FreeMoteToolkit` for extraction and inspection.

**Primary test target: Nekopara Vol. 1 (§11.10)** — chosen specifically because it is the maximum stress test for the §9.2 combined A+B animation system. Successfully porting Nekopara proves both the KiriKiri converter and the animation system under the most demanding real-world conditions in the catalogue.

**Main challenges:** TJS2 scripting (flag it, same as Ren'Py's `init python:`); complex layered sprite/effect system; `.xp3` asset extraction; E-mote model segmentation (all characters are `manual` animation flags); O3DS memory budget under two simultaneous animated characters.

**Suggested approach:** Start with a smaller KiriKiri Z doujin title with minimal TJS2 usage to validate the converter, then move to Nekopara Vol. 0 (free, shorter) as an animation system pre-test, then Nekopara Vol. 1 as the full stress test.

---

#### 6c — TyranoScript / TyranoBuilder
**Difficulty: Medium — well-documented, modern, web-based**
**VNDB catalogue:** ~4,700 titles (large Japanese indie scene; growing English indie scene)

TyranoScript uses `.ks` files (same extension as KAG, and KAG-derived syntax), is open source, and has an English tag reference. It's a web-first engine (HTML5/JavaScript/Electron), so all assets are plain files — no proprietary archive to crack. The tag-based declarative subset (`[bg]`, `[chara_show]`, `[text]`, `[link]`, `[jump]`, `[if]`) converts directly. JavaScript blocks (`[iscript]...[endscript]`) are flagged the same way as Ren'Py's arbitrary Python. Compared to KiriKiri, the scripting escape hatch is less commonly used in typical VNs.

**Key advantage:** Games are distributed as plain directories (or Electron packages), so asset access is trivial compared to `.xp3` or `.nsa` archives. TyranoBuilder projects in particular have a very predictable folder structure.

**Main challenges:** JavaScript blocks (`[iscript]`); HTML embed blocks (`[html]`); Live2D integration (flag it). Some games use heavily customised JavaScript plugins.

**Suggested test title:** Any freely available TyranoScript game on itch.io with minimal JavaScript usage.

---

#### 6d — NVL-Maker / other KAG derivatives
**Difficulty: Medium (if KAG converter exists) — low priority**

NVL-Maker uses KAG as its underlying format. If the KiriKiri/KAG converter (6b) is complete, NVL-Maker games are effectively already covered with minor adjustments. Treat as a sub-task of 6b, not a standalone phase.

---

#### 6e — RealLive (Key / Visual Arts)
**Difficulty: Medium-High | Primary target: CLANNAD (§11.10)**
**Catalogue:** Key's entire back catalogue — CLANNAD, Little Busters!, AIR, Kanon, planetarian, Harmonia, Angel Beats!, Summer Pockets, Rewrite, and more

RealLive is Key's proprietary in-house engine used across nearly all their major titles. It is distinct from both KiriKiri and Ren'Py and requires its own dedicated converter module. The script format uses `.g` or `.seen` compiled scenario files; extraction tools and decompilers exist in the community (the `rlvm` open-source RealLive reimplementation for Linux/Mac is the most comprehensive prior art and is the best reference for the script format). The declarative VN subset — scene loads, character display, dialogue, choices, BGM, jumps — converts mechanically. RealLive also has its own expression/scripting system that gets flagged the same way as TJS2 or Ren'Py's Python.

**Suggested approach:** Start with **planetarian** — a short (~8 hour) kinetic novel with no choices, minimal scripting, and a tiny cast. It's the lowest-risk RealLive title, available on Steam with English text, and validates the converter format before tackling CLANNAD's enormous script volume.

**Key prior art:** `rlvm` (open-source RealLive VM, GPL, C++) — the most complete existing reimplementation, covering the script bytecode format, opcode set, and memory model. Study this before writing the converter; it's a far better reference than reverse-engineering from scratch.

---

#### Phase 6 priority order
1. **6a (NScripter/ONScripter)** — simplest format, existing VNDS library as validation baseline.
2. **6c (TyranoScript)** — plain files, good docs, large modern catalogue.
3. **6b (KiriKiri/KAG)** — hardest, highest catalogue value; includes Nekopara animation stress test.
4. **6e (RealLive)** — Key catalogue including CLANNAD; tackle after 6b establishes the multi-engine pattern.
5. **6d (NVL-Maker)** — free if 6b is done.

**Exit criteria for Phase 6:** At least one full VN from each completed converter plays end-to-end in VN3DS-CHARM on **Old 3DS hardware**, memory under 70MB, with a Problem Report that correctly identifies all unconvertible constructs.

---

### Roadmap summary

| Phase | Key deliverable | Target game(s) |
|---|---|---|
| 0 | VNDS-LOVE fork spike + O3DS stress test | — (existing VNDS scripts as smoke test) |
| 1 | Walking skeleton + proof port | Jisei |
| 2 | Logic + state + audio | Hustle Cat |
| 3 | Fidelity + ATL animation + multi-layer sprites | Sucker for Love, Am I Nima? |
| 4 | Packaging + bone/puppet system + asset-heavy titles | Slay the Princess, Kansei, Yousei |
| 5 | Complex ports + screen runtime | Our Life, Royal Alchemist |
| 5.5 | Triage Workbench UI | Hustle Cat re-test (zero-terminal goal) |
| 6a | NScripter/ONScripter converter | Tsukihime + existing VNDS library |
| 6b | KiriKiri/KAG converter + E-mote animation stress test | Nekopara Vol. 0 → Vol. 1, Fate/stay night |
| 6c | TyranoScript converter | TyranoBuilder indie titles |
| 6d | NVL-Maker (sub-task of 6b) | — |
| 6e | RealLive converter | planetarian → CLANNAD + Key catalogue |

---

## 14. Testing Approach

- Primary loop is **Azahar** (**Old 3DS profile**) — convert, load bundle, run. No SD reflash per iteration. Using O3DS profile from the start means N3DS regressions are caught early, not at hardware validation.
- **Phase 0 O3DS stress test:** Before any converter work — load a 400×240 ETC1 background, two ETC1A4 sprites, and stream OGG audio simultaneously on the O3DS Azahar profile. Measure memory via LÖVE Potion's reporting. This is the gate that confirms the platform baseline and whether the fallback contingency (native C engine) is needed.
- **VNDS corpus (Phase 6g, ADR-004):** Existing VNDS community scripts (Tsukihime, Saya no Uta, Kanon — standard VNDS format, freely available) are converted through the VNDS front end and must play correctly after conversion. During Phase 0 they were loaded directly as the engine's smoke test; the engine no longer reads VNDS directly.
- **Converter regression corpus (Phase 1+):** "The Question" (Ren'Py sample, ships with source, full convert expected zero `blocking` items) plus hand-written `.rpy` snippets that each exercise one flagged category.
- **Hardware validation** at every phase boundary on an actual Old 3DS unit, not just Azahar.

---

## 15. Open Questions

- **(eng)** Save format: follow DDLC-LOVE's pattern (plain Lua table serialized to SD) for consistency with the LÖVE Potion ecosystem; revisit if SD I/O becomes a bottleneck in Phase 4.
- **(eng)** Font: bundle a single VN-appropriate font, or convert the game's own font? Game fonts vary in license; default to a bundled font, flag in Problem Report if the game's typography matters.
- **(eng)** Rollback depth is specified as 3 entries; measure actual RAM cost per entry in Phase 3 to confirm it's safe on O3DS and whether it can be raised.
- **(eng)** O3DS LÖVE Potion baseline RAM consumption — the ~25–30MB estimate needs validation against the current LovePotion release in the Phase 0 stress test.
- **(scope)** Jisei investigation UI — does it use `menu:` (converts) or custom `screen` language (flagged)? Answer comes from first converter run in Phase 1.
- **(scope)** How much of Hustle Cat's persistent/unlock system matters for a single-route playthrough? Determined by reading its Phase 2 Problem Report.
- **(scope)** Am I Nima? — engine and complexity unknown until full release (Oct 2026). Slot into Phase 3 or later based on what ships.
- **(legal/personal)** Source acquisition for each game's `.rpy` — confirm owned copy + extraction method before each phase's converter run. Jisei first.
- **(phase 5)** Is a custom-screen runtime worth building, or is per-game native reimplementation faster? Evaluate after Phase 4 experience with Slay the Princess.
- **(phase 6)** O3DS budget for Phase 6 target titles (Tsukihime, etc.) — NScripter/VNDS titles were originally designed for DS-class hardware, so O3DS headroom should be generous, but confirm during Phase 6a development.

---

## 16. Out-of-Scope Reference (so it isn't re-litigated)

### Prior art — study, don't rebuild
- **DDLC-LOVE** (LukeZGD, GPL-3.0, `github.com/LukeZGD/DDLC-LOVE`) — reference for dual-screen layout, LÖVE Potion sprite/audio, save state, CIA build. Engine fork starts from VNDS-LOVE, not DDLC-LOVE, but this is the most useful 3DS-specific reference.
- **Higurashi: When They Cry 3DS port** (MyLegGuy, GBAtemp #492390) — reference for converter+engine architecture, C# script/image converter design, chapter navigation, fade transitions, PS3-quality asset handling on 3DS. Abandoned but source on GitHub.
- **VN3DS** (GBAtemp #396564) — earlier LPP VNDS interpreter; reference for IF/FI nesting counter pattern. Source of project name conflict; VN3DS-CHARM is the distinct successor name.
- **VNDS community scripts** (Tsukihime, Saya no Uta, Kanon, Umineko, Fate/Stay Night, etc.) — standard VNDS format, freely available; use as Phase 0 engine smoke-test content, no converter needed.

### Out-of-scope game targets
- *Mad Father*, *Misao*, *Ib*, *The Witch's House*, and all other RPG Maker / WOLF RPG Editor titles — removed from the project entirely. Different runtimes, different tools, different project.
- Any title running on Unity, Godot, or web-based engines (RPG Maker MV/MZ, etc.) — impractical on 3DS hardware regardless of content.
