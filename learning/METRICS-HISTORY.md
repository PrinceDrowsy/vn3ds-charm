# METRICS-HISTORY.md — VN3DS-CHARM

> Append-only. The Orchestrator writes one entry per cycle here during the LOG
> step. Never edit or delete past entries — this is the system's memory.

## Phase P — Planning (2026-07-04)

- Converter language decided: Python (ADR-001)
- Script format decided: `script.vnds` (ADR-002)
- Engine fork decided: ajusa/VNDS-LOVE @ 0.0.13, MoonScript source (ADR-003)
- Corrected Lua→MoonScript authoring-layer references across `VN3DS-spec.md`
  and `docs/ai/` planning docs
- Generated `base/PROJECT.md`, `base/ARCHITECTURE.md`, `stack/STACK-*.md` (4
  files), three ADRs, `GAME-PLAN.md` (BUILD mode), `PHASES.md`
- Generated factory operational layer: `AGENTS.md`, `CLAUDE.md` (pointer),
  `agents/*.md` (4 role files), `orchestrator/loop-config.md`,
  `orchestrator/SKILLS-DISCOVERY.md`, `orchestrator/PLANNING.md`,
  `orchestrator/CUTOVER.md`
- Scoped `docs/ai/agent-workflow.md`'s "GitHub Issues are canonical" line to
  apply from cutover onward, resolving the conflict with `GAME-PLAN.md`'s
  BUILD-mode canonical status
- **No Phase 0 cycles have run yet.** Next entry should be Cycle 1 of Phase 0.

<!-- Cycle entries append below this line -->

## Phase 0 — Cycle 1 / Phase 0.1 Engine Bootstrap (2026-07-04)

- Imported `ajusa/VNDS-LOVE` tag `0.0.13` / commit
  `e74532066d07085deb01084e1993ec56de2352f3` under `src/engine/`.
- Preserved upstream MoonScript authoring source and upstream busted specs under
  `tests/engine/upstream/`; did not commit generated Lua runtime output.
- Added project root `Alfons.moon` to compile `src/engine/` into
  `build/engine/vnds/`, run upstream specs, and invoke LÖVE/lovebrew once local
  tooling exists.
- Added root `lovebrew.toml` for 3DS-only packaging from `build/engine/vnds/`.
- Added `tools/engine/verify_bootstrap.py` and ran it successfully.
- Verification result: structural check PASS; Python syntax compile PASS;
  `git diff --check` PASS.
- Blocked verification: `moonc`, `alfons`, `busted`, and `lovebrew` are missing
  from the local PATH, so MoonScript compile, busted specs, and lovebrew package
  verification were not run.
- Security review: `tests/security-reports/security-cycle-1.md` recorded 0
  critical, 0 high, 1 medium, 1 low. The medium finding flags the preserved
  upstream `3ds_convert.sh` as reference-only and unsafe for semi-trusted archive
  conversion.

## Phase 0 — Cycle 2 / Phase 0.2–0.6 Hardware Validation (2026-07-04)

- Wired a local `.3dsx` build (`tools/engine/build_3dsx.py`: smdhtool +
  3dsxtool against LÖVE Potion 2.0.0), replacing the dead lovebrew bundler
  service. Also stages an SD-card-ready folder (`build/lovebrew/sdcard/`)
  with an external `game/` folder, working around a LÖVE Potion 2.0.0
  `boot.lua` regression that otherwise blocks loading romfs-embedded content.
- **0.2/0.3 (dual-screen + touch):** fixed `main.moon`'s 3DS screen routing
  and an end-of-script nil crash in `next_msg`; added touch input from
  scratch (`love.touchpressed`, tap-to-advance in `text.moon`, touch
  hit-testing for choices in `listbox.moon`). Confirmed on real Old 3DS
  hardware with the `hello-vn` fixture.
- **0.4 (real script smoke test):** ran `ajusa/VNDS-TEST` (purpose-built VNDS
  test script, not a copyrighted commercial VN port) through the interpreter
  on desktop LÖVE 11.5. Zero errors across a full script cycle exercising
  labels/goto looping, global variables + interpolation, colored text,
  16-option choice, auto-advancing text, long-text word-wrap, background
  transitions, multi-position sprites, and sound/music loop + cutoff logic.
- **0.5 (O3DS stress test):** confirmed LÖVE Potion 2.0.0 has no
  memory-reporting API reachable from Lua (checked `love.system`/
  `love.graphics` source directly), so byte-precise RAM measurement isn't
  currently possible. Substituted a stability test: `stress-test` fixture
  (ETC1 background, two ETC1A4 sprites, 30s looping streamed OGG) ran 2
  minutes on real hardware — one brief audio hitch at stream start, otherwise
  stable, no crash/freeze. **Numeric RAM ceiling: not measured (see note).**
- **0.6 (version pin):** LÖVE Potion pinned to **2.0.0** (final, not
  `2.0.0-rc1` — rc1 has a real per-screen draw-loop bug fixed in the final
  release). Recorded in `base/ENVIRONMENT.md`.
- Two other real bugs found and fixed along the way: `love.filesystem.getInfo`
  unreliable on this LÖVE Potion 3DS backend (replaced with a
  `getDirectoryItems`-based check), and raw PNG/JPG crashing the 3DS image
  loader natively (all image fixtures now ship as `.t3x` via `tex3ds`).
- Azahar/Citra-lineage emulators (mainline Azahar, AzaharPlus, original
  pre-shutdown Citra Nightly 2104) all fail to boot LÖVE Potion on this dev
  machine, while unrelated homebrew boots fine on the same builds — real
  hardware is the working validation path for now.
- **Phase 0 exit criteria met. Phase 1 is unblocked.**

## Rework R0 — Verification first (2026-11-13)

- **Tests:** 27 new pytest tests (`tests/witch/`), all green; the frozen old
  converter suite unchanged at 367 green.
- **Build:** `charm_schema.h` compiles with `-Wall -Werror` under desktop gcc
  and devkitARM (armv6k, hard float), with every struct size and offset
  asserted. A C reader built against it reads a Python-written bundle
  identically to Witch's reader.
- **Exit:** each audit crash class fails verification: `missing-label`
  (crash), `unsupported-statement` and `unknown-kind` (statements the engine
  can't run), `duplicate-entry` (an asset path listed twice).
- Found along the way: Git for Windows' `mingw64\bin` on PATH ahead of
  MSYS2's makes cc1 load the wrong DLLs and exit `0xC0000139` with no
  message. The C test puts the compiler's own directory first.

## Rework phase H — Hardware spike (2026-11-13)

Old 3DS, `.3dsx` over 3dslink, MicroPython 1.29.0 through its embed port,
synthetic Mice Tea-sized workload (`spikes/hardware/`). Five hardware runs.

- **Interaction** (say, 2 layered shows, 5-item menu, rollback snapshot):
  worst 45.0 ms normal, 37.5 ms NaN-boxed, against 50 ms. Pass.
- **Per-frame Python:** ATL functions and DynamicDisplayables 0.1–0.25 ms.
  60-glyph kinetic text 1.4–4.9 ms (D26).
- **GC:** 110–160 ms for 4–16 MB heaps; heap size barely matters (D25).
- **Garbage per animated frame:** 5.49 KB → 0.79 KB with NaN-boxing (D24).
- **Heap:** 1.16 MB, or 2.03 MB NaN-boxed, against 12 MB. Pass.
- **Native ARM code:** runs (the kernel grants executable memory), but only
  5–15% faster; not adopted.
- **SD (stdio):** sequential read 8.9 MB/s, writes 1.4–6.0 MB/s, random 4 KB
  reads 5.3 ms. Asset loads must be large, grouped and prefetched.
- **Azahar** tracks hardware timings within about 15%, doesn't implement
  `svcControlProcessMemory`, and reports a bogus app-memory-free figure.
- Spike bugs found on the way: a malloc probe that "succeeded" at 512 MB
  (replaced with mallinfo), a 600-frame GC-disabled loop that inflated H.1's
  frame worst case, and MicroPython's privileged CP15 cache flush on ARM.
