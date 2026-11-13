# ENVIRONMENT.md — VN3DS-CHARM

## Development machine

- **Host:** Windows 11 desktop or laptop. No machine-specific paths are
  committed; tools find paths at runtime.
- **Large scratch data** (game copies, harvests, bundles) lives outside the
  repo and is never committed.
- **GitHub account:** confirm the account before any push.

## Converter environment (Python)

- Python 3.14.3 (dev machine's system Python; no strict minimum enforced yet)
- `pip install --break-system-packages` if running in a container/CI environment
  without a virtualenv; prefer a virtualenv locally
- External tools invoked as subprocesses:
  - `tex3ds` (devkitPro tool) — image → `.t3x` conversion
  - an audio encoder for OGG/Vorbis re-encoding (TBD in STACK-CONVERTER.md)
  - archive extraction tools for later Phase 6 engines (`KrkrExtract`, `GARbro`,
    `FreeMoteToolkit`, `nsadec`/`sarconv`, etc. — installed per-phase as needed)
- `pip install pillow` — used by `assets/pipeline.py` to downscale source
  images that exceed the PICA200 (3DS GPU)'s 1024px max texture dimension
  before handing them to `tex3ds` (which otherwise rejects them outright).
  Optional at runtime (the pipeline falls back to skipping the downscale,
  same as before, if Pillow isn't installed) but required to actually fix
  oversized real-game CGs.
- Test framework: `pytest`

## Engine environment (MoonScript / Lua / LÖVE Potion)

- **Fork base:** [ajusa/VNDS-LOVE](https://github.com/ajusa/VNDS-LOVE) @ release
  0.0.13 (MIT license)
- **Authoring language:** MoonScript (`.moon` files) — compiled to Lua via `alfons`
- **Toolchain:** LuaRocks → `moonscript` (language) / `busted` (test framework) /
  `alfons` (build tool) → `lovebrew` / LÖVE Potion (3DS packaging)
- **devkitPro** required for 3DS toolchain (`tex3ds`, 3DS SDK). Work laptop IT
  restrictions allow Docker Desktop; devkitPro/LÖVE Potion toolchain runs on a
  personal machine, not the work-restricted one.
- **Build outputs:** `.3dsx` (Phase 0–3, primary iteration target), `.cia` (Phase
  4+, via `makerom`)
- **LÖVE Potion release version: 2.0.0** (final release, not `2.0.0-rc1`).
  Deployment requires an external `game/` folder alongside the `.3dsx` on the
  SD card (produced by `tools/engine/build_3dsx.py`'s sdcard staging step),
  because LÖVE Potion 2.0.0's `boot.lua` has a regression where a stale error
  from its default `game`-folder lookup fires even when our romfs-embedded
  content loads fine via its fallback path.

## Test/iteration environment

- **Primary emulator: Azahar**, **Old 3DS profile** by default. New 3DS profile
  used only at phase-boundary validation.
- **Real hardware validation:** an actual Old 3DS unit, used at the end of each
  phase (not per-iteration) — see spec §14 Testing Approach.
- No SD-card reflash needed per iteration; the whole convert → run → inspect loop
  works in the emulator.

## Homelab context (secondary, not this project's runtime)

- A homelab Ubuntu Docker host — not part of the VN3DS-CHARM
  runtime path; relevant only if CI/build automation is later moved there.
- No production deployment target — this is a personal homebrew toolchain, not a
  hosted service.

## Known environment gaps (fill in as Phase 0 proceeds)

- [x] Exact Python version pin — 3.14.3 (dev machine); `pytest` installed via pip
- [x] Exact LÖVE Potion release version — 2.0.0 (final)
- [ ] Exact devkitPro/LÖVE Potion install steps for this machine (reference
      DDLC-LOVE's Makefile/LovePotion.elf setup per spec §13 Phase 0)
- [ ] Audio encoder tool choice for OGG re-encoding
