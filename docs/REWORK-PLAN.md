# Rework Plan v2 — A Native 3DS Visual Novel Engine and Converter

> Status: v2, 2026-11-13. Replaces v1 of this document (same file). v1
> assumed a LÖVE Potion runtime; the engine is now native C, so every feature
> has been re-planned around what the hardware can actually do. Project name
> is pending a rebrand (§16); "the engine" and "the converter" are used
> throughout.

## 0. Decision log

Settled:

| # | Decision | Where |
|---|---|---|
| D1 | Rework approved, with plan re-reviews after R1 (harvester across the corpus) and R3 (hardware measurements) | §15 |
| D2 | Original VNDS scripts are not read by the engine; VNDS becomes a converter source | ADR-004 |
| D3 | **Native C engine** (citro3d/ctrulib/ndsp) with a desktop backend for testing. LÖVE Potion and MoonScript are dropped | ADR-005 (to write), §3 |
| D4 | All of a game's languages go into one bundle, switchable in settings | §6.10 |
| D5 | Framing: nothing PC-visible is ever lost, one uniform camera, fit by default, tighter only when provably lossless, crops only by explicit opt-in | §9 |
| D6 | Dual screen: the top screen is the stage, the bottom screen is the reader and controls | §10 |
| D7 | Top-screen 800×240 wide mode used wherever it improves the picture | §9.3 |
| D8 | Repo commits as PrinceDrowsy; unpushed history re-authored, AI trailers removed; plain `origin` URL | done |
| D9 | **MicroPython** is the on-device logic VM; every engine's logic is translated into Python | §6 |
| D10 | Tiered video pipeline: ETC1A4 loops in RAM, Old 3DS MPEG-2/Theora + Y2R, New 3DS H.264 via MVD, audio-clocked, original frame rate | §8.7 |
| D11 | Music codec (DSP-ADPCM vs Vorbis) chosen from R3 measurements, biased toward ADPCM unless the difference is audible; voice and SFX use ADPCM | §8.6 |
| D12 | Speech bubbles stay on the top screen where the author placed them, legibility-checked | §8.2 |
| D13 | Info HUD widgets stay on the top screen at their PC position | §10 |
| D14 | Per-game CIA packaging with its own HOME icon, 3D banner, save space and memory mode; library `.3dsx` for development | §12 |
| D15 | Puppet oracles (a game's own Live2D core / E-mote driver) are acceptable for personal use, never redistributed | §8.8 |
| D16 | PC save import is a stretch goal for R8 | §8.9 |
| D17 | Rebrand: project **VN3DS-CHARM**, converter **Witch**, engine **Enchantment**, bundle files **`.charm`** | ADR-006, §16 |

Open: nothing. The R1 and R3 re-reviews (D1) may reopen decisions with
measured data.

## 1. Goal and principles

Point the converter at an installed visual novel and get a 3DS port that plays
like the PC game: the same story flow and logic, the same sprites in the same
places, the same transitions, animation, timing, music and voice, the same
menus. Hand-fixing a port is the exception for genuinely custom systems.

1. **Fidelity first.** Match what the original engine does, read from its
   source. Where the 3DS can't do something as-is, precompute it on the PC
   rather than simplify it.
2. **Old 3DS performance is the hard limit; New 3DS gets the upside.** Every
   feature must run well on an Old 3DS. Where a New 3DS can do better (wide
   video, higher frame rates, more memory), it does.
3. **Run the game's own logic, reproduce its engine.** Each game's scripts and
   Python run on the 3DS as close to verbatim as possible (§6). The engine
   reimplements the *original engine's* behavior in C, rule for rule.
4. **The original engine is the oracle.** On the PC, the game's own engine
   (Ren'Py's runtime, KiriKiri's E-mote driver, a game's Live2D core) is used
   to read the game, to evaluate things too heavy for the 3DS, and to produce
   reference frames that our output is checked against.
5. **One engine-neutral core.** The engine models what visual novels share.
   Each source engine gets a converter front end. Nothing game-specific lives
   in engine or converter code; per-game choices are data in a profile.

## 2. Evidence that shaped this plan

- **The 2026-11-13 audit** (memory `architecture_audit_2026_11`; lint script
  `D:\ClaudeScratch\vn3ds-audit\lint_bundle.py`):
  - The old hand-written parser drops named menus: 203 jumps to missing labels
    in Cooking Companions, each a crash.
  - The engine silently skipped all 219 transitions in Mice Tea.
  - A flat asset namespace collapsed 46 different `Eyes Neutral.png` files
    into one.
  - Lua semantics broke Python conditions.
  - Mixed coordinate systems were behind the July hardware bugs.
  - Loading the whole script up front cost ~40 MB for Mice Tea.
- **The harvester spike:** the game's own Ren'Py, run headless through
  `register_command`, read every statement, image, transform, style and
  Character in Mice Tea (8.3) in 4.6 s. The same worked for Cooking
  Companions (7.4, Python 2, `.rpa`), Life After Magic (8.0) and DateWarp
  (6.17, which unrpyc can't decompile). It also resolved Mice Tea's custom
  CharacterImage sprites into plain layer lists.
- **LÖVE Potion 3.0.2 source review:**
  - It has canvases and stereo, plus wide mode in C that isn't exposed to Lua.
  - Its only texture formats are RGBA8, RGB8, RGB565 and LA8.
  - It has no video module.
  - It could close the gaps, but a native engine gets everything directly
    (D3).
- **Library survey:**
  - 15 Ren'Py games.
  - NEKOPARA 0/1/2/4/Extra on KiriKiri and Vol. 3 on CatSystem2, all
    shipping `emotedriver.dll`.
  - CLANNAD on RealLive/Siglus.
  - Custom engines: Amorous (C#/FNA), Hustle Cat (NW.js), Unity games,
    Sucker for Love (GameMaker).
  - Am I Nima? releases 2026-11-27.

## 3. What the hardware gives a native engine

| Hardware | Facts | How the engine uses it |
|---|---|---|
| CPU | O3DS: ARM11 MPCore 268 MHz, app core plus a time-limited share of the system core (`APT_SetAppCpuTimeLimit`). N3DS: 804 MHz, extra cores, 2 MB L2 | Main thread: VM, layout, animation. Worker threads: asset streaming, video decoding, audio decoding, texture decompression. On N3DS: high-speed mode plus a full extra core |
| Memory (FCRAM) | App memory set in the CIA ExHeader. O3DS: 64 MB default, 72/80/96 MB modes (80/96 disable the browser and Miiverse while running). N3DS: 124 MB, or 178 MB (HOME Menu doesn't run) | Budgets in §11. A CIA requests the largest mode that keeps HOME Menu and sleep working, verified in R3 |
| VRAM | 6 MB | Framebuffers, the hottest render targets |
| GPU (PICA200) | Programmable vertex and geometry shaders. Fixed-function fragment stage with 6 texture-combiner (TEV) stages (incl. DOT3, MULTIPLY_ADD, INTERPOLATE), 3 texture units plus a procedural-texture unit, alpha test, 8-bit stencil, full blend equations and logic ops, render-to-texture | Everything in §7: compositing, transitions, color matrices, masks, puppets, 3D stage |
| Texture formats | RGBA8, RGB8, RGBA5551, RGB565, RGBA4, LA8, HILO8, L8, A8, LA4, L4, A4, ETC1, ETC1A4; 1024×1024 max | Per-asset choice by measured quality (§11) |
| Display | Top 400×240 (800×240 wide when 3D is off), stereoscopic 3D; bottom 320×240 resistive touch | §9, §10 |
| Video hardware | Y2R (YUV→RGB, tiled output) on all models; MVD H.264 decoder on N3DS | §8.7 |
| GX engines | DisplayTransfer (linear↔tiled, format conversion, 2× downscale), TextureCopy, MemoryFill | Video frames, screenshot capture for save thumbnails, fast clears |
| DSP (ndsp) | 24 channels, PCM8/PCM16 and DSP-ADPCM decoded in hardware, per-channel volume/pan/mix, interpolation, IIR (monopole/biquad) filters | §8.6 |
| Input | Buttons, circle pad, touch; N3DS C-stick and ZL/ZR; gyro, accelerometer, mic, cameras, 3D slider | §10.6 |
| System | Software keyboard, shared system font (incl. CJK), sleep/hinge events, HOME Menu icon and 3D banner (CIA) | Text entry, glyph fallback, pause and resume, per-game HOME icons (§12) |

The engine never assumes LÖVE-style limits: **no "impossible because no
shaders"**. The fixed-function stage plus render targets covers almost every
2D effect visual novels use (§7.3).

## 4. Architecture

```
 PC (converter, Python)                               3DS (native engine, C)
 ┌────────────────────────────────────────┐           ┌──────────────────────────────────┐
 │ Front ends + oracles                   │           │ Platform: citro3d · ndsp · ctrulib│
 │  Ren'Py harvester (game's own Ren'Py)  │           │ VM: node graph, call stack        │
 │  KiriKiri/KAG, CatSystem2, RealLive,   │           │ Logic: MicroPython + renpy shim   │
 │  NScripter, Tyrano, VNDS, ...          │           │   (§6)                            │
 │  Puppet oracles (Live2D core, E-mote)  │  bundle   │ Scene: layers, tags, attributes,  │
 │            ▼                           │ ───────▶  │   transforms, ATL VM, 3D stage    │
 │ Neutral model (node graph, Python,     │           │ Renderer: batches, RT cache, TEV  │
 │  displayables, ATL, screens, styles,   │           │   effects, transitions, puppets   │
 │  puppets, video, audio)                │           │ Text: glyph atlases, layout, tags │
 │ Asset pipeline (quality-gated formats) │           │ Screens runtime, dual-screen UI   │
 │ Framing + dual-screen classification   │           │ Audio (ndsp), video (Y2R/MVD)     │
 │ Verifier (lint, reachability, oracle   │           │ Saves, rollback, history, prefs   │
 │  comparison, autoplay)                 │           │                                    │
 └────────────────────────────────────────┘           └──────────────────────────────────┘
                                                        same core ⇄ desktop backend
                                                        (SDL2 + OpenGL) for testing
```

- **Engine language: C (C17)**, built with devkitARM. The core (VM, scene,
  ATL, layout, text, screens, saves) is portable C with no 3DS calls. A thin
  platform layer has two implementations:
  - 3DS: citro3d, ndsp, ctrulib, Y2R, MVD.
  - Desktop: SDL2 + OpenGL, used for headless autoplay and frame comparison
    (§13).
- **The bundle** is the only contract: node graph, compiled logic, a
  displayable/ATL/screen/style database, and assets, in a binary format read
  with zero parsing on the 3DS: memory-mapped tables plus string pools, loaded
  per chunk on demand. Schema in ADR-006 (to write).

## 5. Ren'Py front end: the harvester

Unchanged from v1 in substance:
- A version-neutral `.rpy` registers `vn3ds_harvest`.
- It runs inside a **scratch copy** of the game: Python directly for Ren'Py
  7/8, the game's own `.exe` for 6.x.
- `--savedir` points at scratch and `TMP`/`TEMP` stay on D:.

It emits:
1. **Node graph** from `renpy.game.script.namemap`, with Ren'Py's own node
   names as stable ids (saves survive reconversion). Every node type,
   including named menus, `call … from`, `With(paired)`, `ShowLayer`/`Camera`,
   Translate blocks for every language, and `UserStatement`s with their
   parsed data.
2. **Python, as source plus the compile flags Ren'Py used**, read from the
   game's own `renpy/python.py`. Python 2 games are normalized to Python 3 at
   the AST level using exactly those `__future__` flags (division,
   unicode_literals, print_function, …), so semantics stay identical (§6).
3. **Initialized state.** Every `define` value and `default` initializer. All
   `init python` code is shipped as code too, not only its results, because
   the 3DS runs it (§6).
4. **Images**: displayable trees (§7.2), attribute tables, LayeredImage
   definitions.
5. **Transforms** (ATL trees), **Characters**, **resolved styles + `gui.*`**,
   **config** (layers, tag layers, default transform, window settings, …).
6. **Screens** as SL2 ASTs.
7. **Audio channels and files; Live2D models** used via
   `renpy.gl2.live2d.Live2D`.
8. **Fonts** used per style, for glyph atlas generation (§8.4).

## 6. Game logic: run the game's own Python on the 3DS

This is the biggest change from v1. v1 compiled Python to Lua and emulated
Python's semantics in a Lua runtime, which is the riskiest and least faithful
part of that plan: every semantic edge case would be our bug.

**Decided (D9): embed MicroPython** (MIT, C, designed for small devices; it
has been ported to the 3DS before, e.g. LiquidFenrir's `3dspython`).

- **Exact Python semantics, for free:** arbitrary-precision ints, None,
  truthiness, `==` across int/float/bool, `/` vs `//`, string methods and
  formatting, f-strings, list/dict/set/tuple, slicing, comprehensions, classes
  with inheritance, closures, generators, exceptions.
- **The game's code runs nearly verbatim:**
  - stat systems, inventories, calendars, dating-sim meters
  - custom text tags (Mice Tea's kinetic tags)
  - custom image systems (CharacterImage, ChangePortrait), which run on the
    device through the displayable API shim, with no per-game reimplementation
  - screen Python, `renpy.random` logic, minigame logic
- **Converted at build time:**
  - Python 2 → 3 normalization with Ren'Py's own flags.
  - `mpy-cross` precompiles everything to MicroPython bytecode (`.mpy`), so
    nothing is parsed on the 3DS, and load is fast and small.
- **The `renpy` API shim:**
  - A Python package (`renpy`, `store`, `persistent`, `config`, `gui`,
    `style`, `_window_*`, …) backed by C bindings into the engine.
  - It implements Ren'Py's public API that games call:
    - `renpy.show/hide/scene/with_statement/pause/say/jump/call/return_statement`
    - `call_screen/show_screen/hide_screen`, `music.*/sound.*`
    - `notify`, `random`, `showing`, `get_attributes`, `restart_interaction`,
      `input`, `notify`, `get_screen`, `seen_label/seen_image`, …
    - Displayable constructors: `Image`, `Solid`, `Frame`, `Fixed`,
      `Composite`/`LiveComposite`, `Transform`, `ConditionSwitch`,
      `DynamicDisplayable`, `LayeredImage`, `Text`, `im.*`, `Movie`, …
  - Where Ren'Py's own implementation is pure Python (substitutions, parts of
    `layeredimage`, action classes in `00action_*.rpy`), the shim reuses it
    (Ren'Py is MIT; attribution kept).
- **Gaps:**
  - MicroPython lacks parts of CPython's stdlib (`datetime`, full `re`,
    `pickle`, some `collections`). The shim adds pure-Python stand-ins for
    the ones games use, found by the corpus scan in R2.
  - Anything still missing is reported with its exact call site and reach
    count.
- **Store, saves and rollback:**
  - Store variables live in MicroPython.
  - Saves serialize the store with our own deterministic serializer.
  - Rollback keeps per-checkpoint diffs in a bounded ring.
- **Other engines use the same VM:**
  - KiriKiri's TJS2, TyranoScript's JS and RealLive/CatSystem2 script logic
    are translated into Python by their front ends.
  - So there is one logic VM for every engine, not one per engine.
- **Performance:** visual novel logic is light. The heavy work (rendering,
  ATL, text, audio, video) is all C. MicroPython's heap is a fixed region
  (sized per game from the corpus scan, typically 4–12 MB). Garbage
  collection runs between interactions, never mid-animation.

Alternatives considered and rejected:
- **Lua 5.4 plus a Python→Lua compiler:** the v1 approach, with much more
  converter work and lower fidelity.
- **Python compiled to C:** per-game binaries, and the 3DS toolchain needed on
  every converting PC.
- **A custom VM:** the most work, for no gain over MicroPython.

R2 starts with a spike: MicroPython on hardware, running a conformance suite
built from the corpus's own Python, compared against CPython with each game's
flags.

## 7. Display: scene, effects, transitions

### 7.1 The scene model

All of v1 §6.1–6.3 holds, implemented in C, read from Ren'Py 8.3's source:
- **Game coordinates.** The engine works in the game's own resolution, and
  each screen has one camera.
- **Placement:** `x = pos(room) + offset − anchor(child)`. Int and `absolute`
  values are pixels, floats are fractions, and `position()` combines both.
- **Default transform:** bottom-center. `left`/`right` align the sprite's
  edge with the screen edge.
- **Layers** from `config.layers`, plus tag layers and `onlayer`.
- **Show on an existing tag:**
  - replaces the image in place and keeps its zorder
  - carries the transform state over, or keeps the running transform
  - remembers the tag's `at` list
  - fires `on hide`/`on replace` ATL events, which can keep the old image
    alive until they finish
- **Image attributes:** `apply_attributes`/`choose_image` reimplemented
  exactly, including `-attr`, say attributes, `@` temporary attributes and
  the longest-prefix lookup.

### 7.2 Displayables and the composite cache

- Native displayables:
  - `Image`, `Solid`, `Frame` (9-slice, tiled or stretched), `Fixed`/
    `Composite`/`MultiBox`, `Transform`, `Crop`, `AlphaMask`, `Flatten`,
    `Null`, `Text`
  - `ConditionSwitch`/`ShowingSwitch`/`DynamicDisplayable`, with conditions
    and functions in MicroPython
  - `LayeredImage`, with its full attribute algorithm
  - Movie (§8.7), Puppet (§8.8), particles (§7.5)
- **Composite cache:** a multi-layer sprite (layered images, CharacterImage
  output, composites) is drawn once into a render target when its attributes
  change, then drawn as one texture until it changes again. One texture per
  visible character keeps Old 3DS draw cost low.
  - This replaces v1's convert-time enumeration of attribute combinations,
    which could explode for large casts.
  - Flattening only happens at runtime, for what is actually on screen.
  - Layers with their own animation stay unflattened above or below the cached
    base.
- `im.*` image operations (`im.Composite`, `im.Crop`, `im.Scale`,
  `im.MatrixColor`, `im.Grayscale`, `im.Sepia`, …) evaluate at runtime
  through the same render targets and color effects (§7.3), cached like
  composites. Convert-time baking stays available as a fallback, decided per
  image by cost.

### 7.3 Color, masks and other effects on the PICA200

| Ren'Py feature | Native route | Fidelity |
|---|---|---|
| `alpha`, `additive`, blend modes | Blend equations | Exact |
| `matrixcolor` tint / brightness / contrast / opacity / invert | One or two TEV stages (MODULATE, ADD, MULTIPLY_ADD, one-minus) | Exact up to 8-bit precision |
| `matrixcolor` saturation / grayscale / sepia | DOT3 luminance stage + INTERPOLATE back toward the original | Exact up to 8-bit precision |
| `matrixcolor` hue rotation, arbitrary 4×4 matrices | Three DOT3 passes into separate channels via render targets, or baked when the image is static | Exact (multi-pass) or baked |
| `AlphaMask`, `im.AlphaMask`, Live2D clipping masks | Second texture unit as alpha, or 8-bit stencil | Exact |
| `blur` | Downsample chain through render targets (GX 2× box filter), then bilinear upsample | Close; compared against the oracle per blur radius used |
| `Pixellate` | Render small, upscale with nearest | Exact |
| Procedural noise, grain | Procedural-texture unit | Exact for Ren'Py's simple noise; custom ones compared |
| Custom GLSL shaders (`renpy.register_shader`) | Ren'Py's built-in shader parts are mapped to TEV programs. Custom ones are pattern-matched where possible, otherwise rendered by the oracle and baked when static, or reported | Case by case |

### 7.4 ATL, transitions, 3D stage

- **ATL VM in C:**
  - Block, Interpolation (all warpers, splines, `knot`, `circles`), Repeat,
    Parallel, Choice (seeded, so saves stay deterministic), Time, Pause, On
    (show/hide/replace/update/hover/idle…), Event, Child/Contains, and
    Function (the callback runs in MicroPython).
  - All ~60 transform properties. Tier-3 properties from v1 are now native
    (§7.3).
- **Transitions:**
  - The snapshot model: `with None` records the old scene, `with T` animates
    old → new as its own interaction, with an implicit `with None` after
    interactions, and per-layer dicts.
  - Both scenes render into render targets and the transition combines them:
    Dissolve, Fade, `ImageDissolve`/`AlphaDissolve` (mask ramp via
    MULTIPLY_ADD and clamp), CropMove, PushMove, MoveTransition families
    (per-tag tweens), Pixellate, zoom, punches, ComposeTransition,
    MultipleTransition.
  - The exact built-in timings from `00definitions.rpy`.
- **3D stage** (`zpos`, `perspective`, `matrixtransform`, camera, `zzoom`):
  real perspective in the vertex shader. The PICA200 is a 3D GPU, so Ren'Py's
  3D stage maps directly.
  - **Games that use the 3D stage get genuine stereoscopic depth from their
    own `zpos` values.**
  - Other games can opt into layer-depth parallax (§10.7).

### 7.5 Particles

`SnowBlossom`, `Particles`, and `renpy.display.particle` factories are
reimplemented in C from Ren'Py's source, with the same algorithm and seeded
randomness. Thousands of sprites render as one batched draw.

## 8. Feature-by-feature routes

### 8.1 Script and flow

The node graph executes natively:
- labels with parameters, `call`/`return` with `_return`, `jump expression`
- menus with conditions, `set`, captions and item arguments
- `while`/`if`/`pass`
- user statements: Ren'Py's built-ins are native, game-registered ones run
  their execute functions in MicroPython

Script chunks load per source file or label range and unload when cold.

### 8.2 Say, window, NVL, bubbles

- `Character` in full:
  - prefixes and suffixes, `ctc` with its positions, `dynamic`, `condition`
  - `kind` inheritance, side images, voice tags, `callback`
  - `extend`, `multiple`, `nointeract`
- **Window:** `window show/hide/auto` with Ren'Py's exact auto show/hide lists.
- **NVL mode:** paginated on the bottom screen (§10).
- **Speech bubbles** (Ren'Py 8.1+): positioned next to characters, composed
  into the art by the author, so they stay on the top screen where placed
  (D12). The converter checks their text is legible at 3DS size, and history
  still collects their lines on the bottom screen.

### 8.3 Choices and interaction

- Menus, `call screen`, and timed choices (ATL timers or `renpy.pause`
  windows).
- `renpy.input` uses the system keyboard.
- Drag and drop (`Drag`/`DragGroup`) works directly by touch on the bottom
  screen.
- Viewports scroll with touch drag and have kinetic scrolling.
- Bars and sliders are dragged with touch.

### 8.4 Text

- **Glyph atlases baked on the PC** with FreeType, using the game's own fonts,
  sizes, hinting, outlines, shadows and kerning, as Ren'Py renders them.
  - Coverage: every character in the script, in every language, plus
    everything the system keyboard can produce for name entry.
  - Missing glyphs fall back to the 3DS shared system font (with CJK).
  - Each atlas is sized for the actual on-screen size (bottom screen at 1:1;
    top-screen text at its camera scale, and at 800×240 in wide mode), so
    text is always crisp.
- **Layout matches Ren'Py:**
  - Unicode line breaking with Ren'Py's `language` rules (`unicode`,
    `japanese-strict`/`normal`/`loose`, `korean-with-spaces`, `western`).
  - Justification, `text_align`, `min_width`, `line_spacing`, `ruby` (furigana)
    and vertical text.
- **Tags:** every built-in text tag, plus game-defined custom tags running in
  MicroPython. Kinetic tags animate glyphs individually.
  - `{w}`, `{p}`, `{nw}`, `{fast}`, `{cps}`.
  - Typewriter speed uses Ren'Py's exact `cps` math.
- Rendered lines are cached into render targets, so text costs nothing after
  it's laid out.

### 8.5 Screens and UI

- An SL2 runtime in C, with styles pre-resolved by the oracle:
  - Layout follows Ren'Py's algorithms: box spacing and fills, `xfill`/
    `yfill`, size groups, grids, sides, frames, viewports.
  - All screen statements from v1 §8. Screen Python and actions run in
    MicroPython, so custom actions work too.
- The game's own menus are used where they convert. The dual-screen split is
  in §10.
- Focus navigation follows Ren'Py's own keyboard/gamepad focus model.

### 8.6 Audio

- Ren'Py's channel model in full:
  - registration (mixer, default loop, tight)
  - `play`/`queue`/`stop` with fades, `if_changed`
  - partial-play specs (`<from>`, `<to>`, `<loop>`, `<silence>`)
  - mixers, voice behavior (stops at the next line unless sustained),
    `set_volume` with delays, pan
- **DSP-ADPCM by default** for SFX and voice: the DSP decodes it in hardware
  with zero CPU, playback starts instantly, and loop points are sample-exact.
- **Music:** DSP-ADPCM or Vorbis streamed on a worker thread. R3 measures
  CPU, storage and listening quality to set the default, biased toward ADPCM
  unless the difference is audible (D11).
- Ren'Py 8.1 audio filters (low/high-pass, reverb-ish) map to the DSP's
  per-channel IIR filters where they correspond, and are reported where they
  don't.
- **Lip sync:** voice amplitude envelopes are computed at convert time and
  drive Live2D mouth parameters (§8.8) and Ren'Py's voice-driven attribute
  callbacks.

### 8.7 Video

The tiered pipeline, now native:
- **Loops and overlays** (rain, smoke, snow, dust): **ETC1A4 frame sequences
  in RAM** at 1 byte per pixel, with exact timing and seamless loops.
  Transparency is kept: Ren'Py's `Movie(mask=…)`/`side_mask` alpha become
  ETC1A4 alpha.
- **Cinematics and animated menu backgrounds:** streamed video.
  - Old 3DS: MPEG-2 or Theora at 400×240, chosen by R3 benchmarks. Decoding
    runs ahead on a worker thread, and **Y2R converts frames in hardware
    straight into GPU-tiled textures**.
  - New 3DS: H.264 at 800×240 (wide) through **MVD**, with GX
    DisplayTransfer doing the tiling. CPU stays near idle.
  - **Alpha video:** streamed side-by-side masks, combined on a second
    texture unit.
- **Timing:**
  - The original frame rate is kept: always on New 3DS, and on Old 3DS for
    sources up to 30 fps. Higher-rate sources are flagged for Old 3DS.
  - Presentation is clocked to the DSP's sample position, so there's no
    drift.
  - Cut points, durations and framing match the source.
- **Video inside scenes:** decoded frames are ordinary scene textures, so a
  `Movie` displayable can sit under sprites and take part in transitions, as
  in Ren'Py.
- **Verification:** the target is zero dropped frames on the corpus videos,
  measured on hardware.

### 8.8 Animated puppet sprites (Live2D, E-mote, Spine, Inochi2D)

Puppet sprites are meshes deformed by named parameters (head angle, eye
open, breathing, mouth), driven by motion curves, expressions, physics and
lip sync. The PICA200 draws textured triangle meshes natively. What has to be
solved is evaluating the deformation, which proprietary runtimes do.

**Target: one engine-native Puppet displayable,** fed by per-format
extractors:

- **Geometry: a measured surrogate of the original runtime.**
  - On the PC, the extractor drives the *original* runtime as an oracle:
    the Cubism Core library a Live2D game ships, or the E-mote driver
    (`emotedriver.dll`) the NEKOPARA games ship.
  - It samples every drawable's vertices, opacity and draw order across
    parameter space.
  - It fits a compact model per drawable: the base mesh, one-parameter
    response curves, and pairwise terms only where two parameters actually
    interact (a truncated functional decomposition). Higher orders are added
    only where the error demands it.
  - Draw order and opacity get their own surrogates.
  - **Accuracy is measured, not assumed:** the surrogate is compared with the
    oracle on random parameter vectors and on every motion the game uses.
    The acceptance bar is max vertex error under 0.5 px at 3DS scale. Models
    that miss it get denser sampling or more interaction terms automatically.
- **Runtime:** per-drawable blending of those terms.
  - It can run in the **PICA200 vertex shader**: deltas as vertex attributes,
    weights as uniforms, about 10 terms per pass. That keeps O3DS CPU free.
  - A CPU path covers models that exceed attribute limits.
- **Everything around the geometry is reimplemented exactly from open
  formats:**
  - Live2D: `motion3.json` (linear/bezier/stepped curves, fades, loops),
    `exp3.json` (add/multiply/overwrite), `physics3.json` (the pendulum
    algorithm, documented in Live2D's open Framework), `pose3.json`, eye
    blink, breathing, lip sync.
  - Rendering: Cubism blend modes, clipping masks via stencil, and
    multiply/screen colors via TEV stages.
  - Ren'Py's own Live2D layer (`renpy/gl2/live2d.py`: attributes mapped to
    motions and expressions, fades, `loop`, `nonexclusive`, `seamless`,
    `update_function`) is reproduced rule for rule.
- **E-mote (NEKOPARA):** the same surrogate approach, with the E-mote driver
  as oracle.
  - Getting geometry out of it needs a research spike: either capture its
    draw calls under Direct3D, or use FreeMote's documentation of the PSB
    format plus our own evaluator, validated against the driver.
  - Its timelines and variables become Puppet motions and parameters.
- **Spine** (some Unity VNs) and **Inochi2D** (an open format): both have
  documented formats, so skeletal deformation (bones, weighted meshes, IK,
  constraints) can be implemented natively from the spec. Bone skinning runs
  in the vertex shader.
- **Textures:** a model's 2048–4096 px atlases are rebuilt at the model's real
  on-screen size (about 240 px tall, or 480 px of horizontal detail in wide
  mode), quality-gated (§11).
- **Usage rule (D15):** the oracles are the runtimes that ship inside games
  the owner bought, run only on the owner's PC for extraction. Neither the
  runtimes nor extracted models are ever redistributed.
- **Scope:** puppets from the original game only. The engine never invents
  animation for static sprites.

### 8.9 Saves, rollback, history, skip/auto, persistent

As v1 §6.9:
- Saves hold node id, call stack, store, scene lists with transform state,
  audio, window and screens.
- Rollback is a bounded diff ring.
- Seen-node tracking drives skip.
- Auto mode uses Ren'Py's formula.
- Saves get a 400×240 top-screen thumbnail through GX capture.

**Stretch: bring PC saves across.** The harvester can load a PC save with the
game's own Ren'Py (Ren'Py saves are pickles of its internals, which only real
Ren'Py can read) and write it out in our save format. A player could then
continue their PC playthrough on the 3DS, with persistent unlocks (galleries,
endings) carried over. Export back to PC is harder and out of scope for now.

### 8.10 Translations

- Every language in the bundle (D4), switchable in settings, following Ren'Py's
  translation semantics: `translate` blocks, string translations, language
  callbacks, and per-language fonts and styles.
- Glyph atlases include each language's characters.

### 8.11 Meta and unusual features

Some games read the OS username, write files, or fake crashes (DDLC-style
meta horror). These run through MicroPython with shims that behave
sensibly on 3DS (the username comes from the 3DS profile name), or they are
reported case by case. Achievements become an in-game list plus a toast.
Ren'Py's self-voicing has no 3DS text-to-speech and is reported.

## 9. Framing (top screen)

Settled rules (D5), unchanged from v1 §9.1:
1. Nothing PC-visible is lost; no sprite is cut off unless the PC cuts it off
   the same way.
2. One uniform camera: no per-sprite moves, no zoom that changes between lines.
3. Sprites as large and sharp as possible, through quality, never cropping.

### 9.1 Defaults

- **Fit** is the default: the whole frame, scaled uniformly, centered. Mice
  Tea comes out at 400×225 (7.5 px bars). Jisei at 320×240 (40 px
  pillarbox). Life After Magic's 4× pixel art (native 240×180) scales to
  320×240.
- **A tighter frame only where the converter proves nothing is lost:** margins
  holding only UI that moves to the bottom screen, or purely decorative frame
  art. The textbox area never qualifies, because it shows whenever the window
  hides.
- **Cover-style crops** only by explicit profile opt-in, with every clipped
  show listed.

### 9.2 Content check, preview, profiles

- **Content check:** every show and every ATL path is checked against the
  frame. A rule-1 violation fails the build unless the profile accepts it
  explicitly.
- **Preview sheet:** oracle-rendered PC frames side by side with our 3DS
  framing at true size.
- **Profiles** (`profiles/<game>.toml`) are the only place per-game choices
  live.

### 9.3 Sharpness

- **Draw at 1:1.** Assets are resampled once on the PC to their exact
  on-screen size, with area averaging or Lanczos per asset type.
- **Pixel art:** detected automatically (exact k×k upscales, e.g. Life After
  Magic at 4×). Integer scales use nearest-neighbor; non-integer scales use
  pre-baked sharp bilinear.
- **Wide mode (D7):**
  - 800×240 is on by default wherever the art has more than 400 px of
    horizontal detail. Assets are resampled for it, and its memory cost is in
    the budget.
  - It's detected at runtime, with a half-width fallback on models without
    it.
  - It takes priority over stereo, which applies only while the player has
    stereo enabled and the slider raised.
- **Size report:** each character's on-screen height and estimated face size
  in 3DS pixels.

## 10. Dual-screen design

Settled (D6) and unchanged from v1 §9.5: **the top screen is the stage, the
bottom screen is the reader and the controls.** On the 3DS the art is never
covered by text or buttons.

1. **What goes where.**
   - The converter classifies everything automatically, reports it, and
     shows it on the preview sheet. The profile can override any item.
   - Top: scene layers, `show text` and `centered` cards, art-like overlays
     and information HUD.
   - Bottom: say, choices, NVL, modal and interactive screens, notifications.
2. **Bottom-screen layouts:**
   - Dialogue is laid out natively for 320×240, skinned with the game's own
     `gui/` art and fonts, with side images beside the text.
   - Choices are large touch buttons, and the scene stays visible above them.
   - NVL is paginated.
   - A quick bar sits along the bottom edge.
   - When the window is hidden, the bottom screen shows a quiet idle state.
3. **Split menus:**
   - main menu art on top, buttons below
   - save/load: the selected slot's thumbnail large on top
   - history: scroll on the bottom with voice replay, the scene stays up
   - gallery: thumbnails below, the CG on top, with an optional
     high-resolution pan-and-zoom viewer
   - music room and stat screens split the same way
4. **Point-and-click mirror:** imagemaps and investigation scenes stay full
   quality on top, with a touch map of the same scene below. A d-pad cursor
   follows Ren'Py's focus order.
5. **Sync:**
   - Whole-screen fades and flashes cover both screens.
   - Scene-only effects and shakes stay on top.
   - Typewriter, auto and skip indicators sit on the bottom.
6. **Input:** A advance, B back/menu, X history, Y hide window, L skip, R
   auto, Start for the game menu, d-pad focus, touch everywhere on the bottom
   screen. On N3DS, C-stick scrolls history and viewports.
7. **Stereoscopic 3D:**
   - Games with Ren'Py's 3D stage get true depth from `zpos`.
   - Other games can opt into layer-order parallax. It's off by default and
     measured on Old 3DS first.

## 11. Assets and memory

- **Namespaced paths:** the source tree is kept, so name collisions can't
  happen. The manifest maps every image name to its file.
- **Quality-gated texture formats:**
  - For each asset at its final size, the converter encodes the candidates
    (ETC1/ETC1A4, RGB565/RGBA4/RGBA5551, RGBA8) and measures each against
    the source with a perceptual metric (SSIM, plus edge and banding checks).
  - It picks the smallest format above the quality bar. Pixel art and text are
    never compressed.
  - The bar is set once on real hardware in R3.
- **Large images:** anything over 1024 px is tiled (long pans, wide-mode
  backgrounds).
- **Streaming and caching:**
  - Asset streaming and decompression run on a worker thread, with prefetch
    along the next few nodes (Ren'Py's prediction idea).
  - The texture cache is an explicit-budget LRU. Composite caches (§7.2) count
    against it.
  - No directory listing at runtime: the manifest is an index.
- **Budgets (initial, refined in R3):**

| Pool | O3DS (CIA, mode verified in R3) | N3DS (124 MB) |
|---|---|---|
| Engine code + static data | ~4 MB | ~4 MB |
| MicroPython heap | 4–12 MB per game | 8–24 MB |
| Script chunks + databases | 2–6 MB | 2–8 MB |
| Textures + composite caches | remainder, ≥ 30 MB | ≥ 70 MB |
| Audio buffers / video ring buffers | 2–6 MB | 4–12 MB |
| Glyph atlases + text caches | 1–3 MB | 2–4 MB |

## 12. Packaging and the 3DS experience

- **Per-game CIA (D14):** the converter wraps the engine plus the game's
  bundle into its own installable title:
  - its own HOME Menu icon (from the game's window icon) and 3D banner (from
    its main-menu art, with a short clip of its title music as the banner
    jingle)
  - its own title name and save space
  - its own memory mode from the ExHeader (§3)

  Large games keep heavy assets (video, voice) in an SD folder the CIA reads,
  which keeps installs quick.
- **Development build:** a library `.3dsx` that lists bundles on SD, as today.
- **Sleep/hinge:** closing the lid pauses audio, video and timers, and
  resumes exactly where it left off. HOME button suspends cleanly.

## 13. Verification

1. **Bundle verifier** (fails the build):
   - Every jump/call target exists, and every node type and opcode is known
     to the engine (one shared schema, generated, tested on both sides).
   - Every asset exists.
   - Every reachable node is supported, and every Python module imports under
     MicroPython.
2. **Problem Report v2:** severity by player impact (crash/stuck, missing
   content, visual mismatch, cosmetic, harmless), only for **reachable**
   nodes, with reach counts.
3. **Headless desktop runner:** the same engine core on the desktop backend,
   auto-playing and exploring every menu branch (bounded). It asserts no
   errors, no missing assets, no stuck interactions, and that budgets hold.
4. **Oracle comparison:**
   - Real Ren'Py and our engine are driven down the same path and frames
     compared at each say node, framed identically, giving per-scene scores.
   - Puppets: surrogate vs. oracle vertex error.
   - Video: frame timing vs. source.
5. **Azahar** (Old 3DS profile) for performance and memory, **hardware** last.

## 14. Front ends and engine coverage

| Engine | Library | Logic → MicroPython | Notes |
|---|---|---|---|
| Ren'Py 6.17–8.3 | 15 games | Native Python | Harvester (§5) |
| VNDS (ADR-004) | community scripts | Tiny translator | Validates the neutral model on a second source |
| KiriKiri/KAG (+TJS2) | NEKOPARA 0/1/2/4/Extra | TJS2 → Python | XP3 archives, KAG layers and messages, rule-image transitions (= ImageDissolve), E-mote puppets via the driver oracle |
| CatSystem2 | NEKOPARA Vol. 3 | CST scripts → Python | Archive and script format research |
| RealLive/Siglus | CLANNAD | Bytecode → Python | rlvm as the semantic reference; graphics objects map to tagged displayables |
| NScripter/ONScripter, TyranoScript, Naninovel | (future) | → Python | Documented script formats |
| Custom engines | Amorous, Hustle Cat, Dream Daddy, HuniePop 1/2, Sucker for Love | Per game | No standard format. Each is its own reverse-engineering project, never out of the box |
| Am I Nima? | releases 2026-11-27 | TBD | Fingerprint the engine on release |

The neutral model covers:
- Ren'Py's display model, which is the richest
- KiriKiri's numbered layers and multiple message windows
- RealLive's object model
- vertical text and ruby
- puppets, video, particles and the 3D stage

## 15. Phases

Each phase ends with its exit criteria met on the validation targets (Jisei,
Mice Tea, Life After Magic, Scarlet Hollow). The old pipeline keeps working
until R6 reaches parity.

- **R0 — Verification first.**
  - Bundle verifier and schema; Problem Report v2; a desktop autoplay harness
    for today's bundles.
  - Exit: it reproduces the audit's crashes.
- **R1 — Harvester.**
  - Full harvest (§5) across all 15 Ren'Py games; the oracle frame-capture
    helper.
  - Exit: all 15 harvest cleanly, and node counts match Ren'Py's own.
  - *Plan re-review (D1).*
- **R2 — Logic VM spike, then build.**
  - MicroPython on hardware; py2→py3 normalization; the `renpy` shim; a
    conformance suite from the corpus vs. CPython.
  - Exit: ≥ 98% of reachable Python in the corpus runs unmodified, with the
    rest listed by call site.
- **R3 — Engine core + hardware truth.**
  - Platform layers (3DS + desktop); VM; scene model; renderer with TEV
    effects; render targets; transitions; ATL VM; text; audio; saves.
  - Hardware measurements: SD throughput, memory modes, decode benchmarks
    (MPEG-2/Theora/MVD), texture-format quality bar, wide mode and stereo on
    O3DS/N3DS/2DS.
  - Exit: Jisei plays start to finish on hardware from a native bundle, and
    saves survive reconversion.
  - *Plan re-review (D1).*
- **R4 — Displayables, assets, framing.**
  - Composite cache, LayeredImage, `im.*` at runtime, particles, 3D stage,
    quality-gated assets, pixel-art pipeline, framing with its content check
    and preview, wide mode.
  - Exit: Mice Tea and Life After Magic play end to end; content check clean;
    budgets met on Old 3DS.
- **R5 — Screens and dual screen.**
  - SL2 runtime, focus, dual-screen classification and layouts, split menus,
    point-and-click mirror, system keyboard, translations.
  - Exit: every validation target's own menus work; Jisei's investigations
    work through the mirror; Scarlet Hollow's custom screens work.
- **R6 — Video and audio polish.**
  - Tiered video pipeline; DSP-ADPCM/Vorbis defaults from R3 data; lip-sync
    envelopes.
  - Exit: Scarlet Hollow's cinematics, menu video and effect loops play with
    zero dropped frames on Old 3DS and New 3DS.
- **R7 — Puppets.**
  - Puppet displayable, surrogate fitting with measured error, Live2D open
    formats, Ren'Py Live2D semantics; E-mote research spike.
  - Exit: a Live2D test model, plus one NEKOPARA character once the KiriKiri
    front end exists, animate within the error bar at full frame rate on Old
    3DS.
- **R8 — Fidelity loop and packaging.**
  - Oracle comparison across the corpus; per-game CIA builds with HOME icon
    and banner; PC save import (stretch).
  - Exit: all 15 Ren'Py games with zero crash/stuck/missing-content items on
    reachable paths, or each one explained.
- **R9 — Retire the old pipeline.**
  - Remove the MoonScript engine, the old parser and emitter, and their tests.
  - Rewrite `VN3DS-spec.md`, `ARCHITECTURE.md` and the stack docs around this
    plan.

Then the front ends in §14 order: VNDS, KiriKiri (with E-mote), RealLive,
CatSystem2.

**Release milestone: Universal-DB listing.** Once Enchantment plays converted
games end to end (R4 at the earliest), publish a GitHub release and submit
the repo through Universal-DB's app request form.
- **What gets listed:** the library build of Enchantment (`.3dsx`/`.cia`,
  which plays `.charm` bundles from the SD card), with Witch linked as the PC
  tool that makes them.
- **Release assets:** the form expects direct `.3dsx`/`.cia` files attached to
  the release; archives need the `archive` tag added by hand.
- **Never in a release:** `.charm` bundles or per-game CIAs, which contain the
  original games' content.
- **Before submitting:** check Universal-DB's guidelines against how Witch is
  described (converting games the player owns), and write the listing's
  description and screenshots from a public-domain or self-made test novel.

## 16. Rebrand

Decided (D17, ADR-006), on a love-magic theme:
- **VN3DS-CHARM**: the project.
- **Witch**: the converter.
- **Enchantment**: the 3DS engine.
- **`.charm`**: a converted game's bundle.

New code uses these names from R0 on. Renaming the GitHub repo needs the repo
owner. Moving the local folder needs the project memory migrated.

## 17. Open decisions

None. Everything is settled in §0. The R1 and R3 re-reviews (D1) may reopen
decisions with measured data.
