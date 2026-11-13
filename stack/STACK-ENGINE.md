# STACK-ENGINE.md — Engine Technology Stack

**Fork base:** [ajusa/VNDS-LOVE](https://github.com/ajusa/VNDS-LOVE) @ release
0.0.13 (MIT license) — see ADR-003.

> **Read this before writing any engine code.** The authoring language is NOT
> plain Lua. Getting this wrong wastes a cycle fighting the build.

## Authoring vs. runtime — the critical distinction

| Layer | Language | Where it lives | Who touches it |
|---|---|---|---|
| **Source (authoring)** | **MoonScript** | `src/engine/*.moon` | Developer agent edits this |
| **Compiled (build artifact)** | Lua | build output dir (gitignored) | Never hand-edited |
| **Runtime** | Lua (executed by LÖVE) | on-device / in Azahar | N/A — this is what actually runs |

MoonScript is a language that compiles to Lua — similar relationship to how
TypeScript compiles to JavaScript. All `love.*` API references, `flux` tween calls,
and runtime behavior described in `VN3DS-spec.md` (e.g. `love.graphics.draw`,
`flux.update(dt)`) are **accurate at the runtime layer** — MoonScript compiles to
exactly that. But when the spec or a work item says "implement X," it means: write
`.moon` source that compiles to the described Lua behavior, then run the build.

**Rule: never hand-edit generated Lua.** If the compiled Lua looks wrong, fix the
`.moon` source and rebuild.

## Toolchain

1. **LuaRocks** — package manager, bootstraps the rest of the toolchain
2. **moonscript** — the language itself + `moonc` compiler (`.moon` → `.lua`)
3. **busted** — test framework (inherited from upstream VNDS-LOVE)
4. **alfons** — build tool that orchestrates the MoonScript compile step
5. **lovebrew** — packages the compiled LÖVE project for 3DS
6. **LÖVE Potion** — the 3DS-targeting LÖVE runtime that executes the compiled Lua

Build flow: `.moon` source → (`alfons` invokes `moonc`) → `.lua` → (`lovebrew`) →
`.3dsx` / `.cia`

## Runtime capabilities (confirmed, spec §9.1)

- `love.graphics.draw(image, x, y, r, sx, sy, ox, oy)` — position, rotation, scale,
  origin offset are native GPU-accelerated PICA200 transforms. Free at runtime.
- `love.graphics.setColor(r, g, b, a)` — alpha tinting confirmed working under
  LÖVE Potion 3.0 via citro2d's tinting mode.
- **Not available:** pixel/fragment shaders (PICA200 is fixed-function). No blur,
  glow, colour grading, or mesh deformation.

## Animation stack

- **flux** (rxi, MIT) — minimal Lua tween library (~150 lines), no dependencies.
  Interpolates numeric fields on a Lua table using standard easing functions.
  Vendor this into the engine or pull via LuaRocks if packaged there.
- Sprite state tables, preset library, keyframe blocks: see spec §9.1 for the full
  design (these are `.moon` source files implementing the described Lua-runtime
  behavior).

## Texture / asset format

- `.t3x` is the **required** custom texture format — confirmed by upstream
  VNDS-LOVE's own documentation. PNG/JPG do not work directly; the Converter
  produces `.t3x` via `tex3ds` (see STACK-CONVERTER.md).
- ETC1 for opaque backgrounds, ETC1A4 for anything needing alpha (spec §10).

## Project layout (`src/engine/`)

```
src/engine/
  main.moon              # LÖVE entrypoint (love.load/update/draw)
  vnds/
    parser.moon          # script.vnds line-by-line interpreter
    commands.moon        # standard + extended VNDS command implementations
    callstack.moon       # call/return stack (IF/FI-style nesting pattern, spec §2.1)
  animation/
    flux.moon            # vendored tween library (or LuaRocks dep)
    presets.moon         # named animation presets (spec §9.1)
    layers.moon          # multi-layer sprite system (§9.2 Option A)
    puppet.moon          # bone/puppet system (§9.2 Option B, Phase 4)
  audio/
    channels.moon        # music/sfx/voice streamed playback via ndsp
  ui/
    dialogue_box.moon    # bottom-screen text/name/choice rendering
    touch.moon           # touch input handling
  save/
    state.moon           # save/load serialization
  3ds_convert.sh          # reference from upstream — asset conversion script
tests/
  engine/                 # busted test suite (.moon test files)
```

## Reference material (study before writing engine code)

- **DDLC-LOVE** (LukeZGD, GPL-3.0) — dual-screen layout, sprite/audio handling
  under LÖVE Potion, save state, `.cia` build via `LovePotion.elf`
- **Original VN3DS** (GBAtemp #396564) — IF/FI nesting counter pattern for
  `ifvar`/call-stack implementation
- **Upstream `3ds_convert.sh`** in ajusa/VNDS-LOVE — existing asset conversion
  reference for the `.t3x` pipeline

## Performance budget (Old 3DS — hard constraints, see base/RULES.md)

- ≤4 concurrent active tweens
- ≤2 simultaneous multi-layer characters (Option A)
- 1 simultaneous puppet character (Option B) unless profiling confirms 2 is safe
- 70MB hard memory ceiling, 45MB target
- Known upstream weak spot: performance on 3DS is tracked as WIP in upstream issue
  #16 — this is exactly what the Phase 0 stress test exists to validate for
  VN3DS-CHARM's own use case.
