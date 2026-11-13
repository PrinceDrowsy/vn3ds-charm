# ADR-005 — Native C Engine with Embedded MicroPython

**Status:** Accepted
**Date:** 2026-11-13
**Deciders:** PrinceDrowsy
**Supersedes:** ADR-003 (VNDS-LOVE fork, MoonScript on LÖVE Potion)

## Context

ADR-003 forked VNDS-LOVE and ran it on LÖVE Potion. With runtime VNDS
compatibility dropped (ADR-004) and the engine being rebuilt around Ren'Py's
real semantics (`docs/REWORK-PLAN.md`), the fork no longer carries useful
code, and the runtime became the limiting factor.

LÖVE Potion 3.0.2 (August 2025), reviewed from source:
- **Has:** canvases and stereo.
- **Missing or not exposed:** wide mode isn't reachable from Lua, the only
  texture formats are RGBA8/RGB8/RGB565/LA8 (no ETC1/ETC1A4/RGBA4), and there
  is no video module.
- **Still needed:** a fork patched in C++ for anything beyond that.

The project's needs reach well past those gaps:
- compact texture formats for memory
- TEV-stage color effects
- stencil masks
- vertex-shader puppet deformation
- Y2R and MVD video decoding
- worker threads on the system core and the New 3DS cores
- DSP-ADPCM audio
- per-title memory modes

## Decision

1. The engine is written in **C (C17)** with devkitARM, on citro3d, ctrulib
   and ndsp, using the 3DS hardware directly.
2. The core (VM, scene model, ATL, transitions, text layout, screens, saves)
   is portable C behind a thin platform layer. It has a 3DS implementation and
   a **desktop implementation (SDL2 + OpenGL)** used for headless autoplay and
   frame comparison against the original engine.
3. Game logic runs in **embedded MicroPython**, precompiled to `.mpy` at
   convert time, with a `renpy` API shim backed by the engine. Other source
   engines' logic is translated into Python by their converter front ends.
4. MoonScript, the VNDS-LOVE fork and LÖVE Potion are retired once the native
   engine reaches parity (REWORK-PLAN R9).

## Consequences

- Full access to the hardware: every texture format, wide mode, stereo,
  render targets, stencil, vertex shaders, Y2R, MVD, DSP-ADPCM, memory modes.
- Each game's own Python runs nearly verbatim on the device, which removes the
  need to compile Python to another language or emulate its semantics.
- We own text layout, audio streaming, file I/O and input, which were
  previously provided by LÖVE.
- The desktop backend has to be built and kept in step, because the
  automated verification depends on it.
- ADR-002's `script.vnds` format is retired with the old engine. The new
  bundle format gets its own ADR.

## Alternatives considered

- **Fork LÖVE Potion 3.0.2 and patch the gaps in C++.** Keeps MoonScript and
  desktop LÖVE for testing, but most of the engine would still be new C++
  inside someone else's architecture, with less control over memory and
  threads. Rejected.
- **Stay on LÖVE Potion 2.0.0.** No canvases confirmed, no wide mode, no
  video. Rejected.
- **Lua 5.4 plus a Python→Lua compiler for logic.** Every Python semantic
  edge case would become a converter or runtime bug. Rejected in favor of
  MicroPython.
