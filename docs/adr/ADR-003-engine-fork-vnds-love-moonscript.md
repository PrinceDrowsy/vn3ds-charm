# ADR-003 — Engine Fork: ajusa/VNDS-LOVE @ 0.0.13 (MoonScript → Lua on LÖVE Potion)

**Status:** Superseded by ADR-005 (native C engine with embedded MicroPython)
**Date:** 2026-07-04
**Deciders:** Scott, PrinceDrowsy

## Context

VN3DS-CHARM needs a 3DS-capable VN engine. Rather than build a 3DS platform layer
(dual screen, touch, audio, `.t3x` textures) from scratch, the project forks an
existing cross-platform VNDS player and extends its command set. The spec named
"VNDS-LOVE" as the base and described it as a "Lua/LÖVE" player throughout.

On inspecting the actual repository ([ajusa/VNDS-LOVE](https://github.com/ajusa/VNDS-LOVE)),
two facts materially change the toolchain assumptions:

1. **The source is MoonScript, not Lua.** The repo is ~93% MoonScript — a language
   that *compiles to* Lua. The `src/` tree is `.moon` files; a build step (`alfons`)
   transpiles them to the Lua that LÖVE actually runs. Describing the engine as "Lua"
   is correct at runtime but wrong at the authoring layer, and would mislead the
   Developer agent into hand-editing generated Lua and fighting the build.
2. **The repo confirms every 3DS constraint the spec assumed** — 3DS support is
   partial/WIP, the `.t3x` custom texture format is required (PNG/JPG don't work),
   text and audio work unconverted, and performance is the known weak spot (their
   issue #16). This validates the Phase 0 stress-test premise and gives the asset
   pipeline a real reference (`3ds_convert.sh` in the repo).

Other concretes: **MIT licensed** (clean to fork), latest release **0.0.13
(Feb 2023)** — stable but dormant, and **busted** is the existing test framework.

## Decision

Fork **ajusa/VNDS-LOVE at release 0.0.13** (MIT) as the engine base.

- **Authoring language: MoonScript.** The Developer agent edits `.moon` files in
  `src/` and runs the compile step. It must **not** hand-edit generated Lua.
- **Runtime: Lua on LÖVE Potion.** All runtime-layer references to Lua in the spec
  (LÖVE API calls, `love.graphics.draw`, flux tweens) remain accurate — MoonScript
  compiles to exactly that.
- **Toolchain:** LuaRocks → `moonscript` / `busted` (tests) / `alfons` (build), then
  `lovebrew` / LovePotion for the 3DS `.3dsx` (Phase 0–3) and `.cia` (Phase 4+).
- **Test framework: busted** — inherited from upstream; the Tester agent gets a test
  harness rather than starting from zero.
- The exact LÖVE Potion release version is pinned during the Phase 0 spike and
  recorded in the engine STACK doc.

## Consequences

- The engine STACK doc and all agent instructions must describe a MoonScript
  authoring layer with a Lua runtime, and the build must run `alfons` compile before
  any `.3dsx` packaging. Generated Lua is a build artifact, not source.
- The Developer agent needs MoonScript fluency (or a skill for it); MoonScript is
  close to Lua semantically but whitespace-significant with its own syntax.
- The upstream `3ds_convert.sh` and `.t3x` handling are direct references for the
  Phase 1 asset pipeline, reducing unknowns.
- Upstream being dormant (0.0.13, Feb 2023) means the fork is stable but unlikely to
  receive upstream fixes — VN3DS-CHARM owns maintenance from the fork point onward.
  This is acceptable and expected for a hard fork with a divergent extended format.
- Performance being upstream's known weak spot (issue #16) reinforces the Phase 0
  Old-3DS stress test as a hard gate, and the native C/citro2d fallback contingency
  as a real (if unlikely) escape hatch.

## Alternatives considered

- **Native C/C++ (devkitPro + citro2d) from scratch** — maximum performance and
  control, but rebuilds the entire platform layer and throws away VNDS compatibility
  and the existing community script corpus. Retained only as a documented fallback
  contingency gated by the Phase 0 stress test.
- **Fork DDLC-LOVE instead** — DDLC-LOVE is a purpose-built single-game LÖVE Potion
  port and an excellent 3DS reference, but it is not a general VNDS player and would
  need more stripping-back than VNDS-LOVE to become a general engine. Kept as a
  primary *reference* (dual-screen layout, save state, CIA build) rather than the
  fork base.
- **Treat the engine as Lua and ignore MoonScript** — rejected outright: the source
  is MoonScript, and pretending otherwise would produce a build the Developer agent
  can't correctly modify.
