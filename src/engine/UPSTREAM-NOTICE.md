# Upstream import notice

This directory is the Phase 0.1 bootstrap import of the engine source from:

- Repository: https://github.com/ajusa/VNDS-LOVE
- Tag: `0.0.13`
- Commit: `e74532066d07085deb01084e1993ec56de2352f3`
- License: MIT. The upstream 0.0.13 tag has no root `LICENSE` file, so the
  license from upstream's default branch is copied here as
  `LICENSE-VNDS-LOVE`. The imported third-party Lua libraries retain their
  embedded copyright/license notices.

The imported source keeps the upstream MoonScript authoring layer. Do not hand-edit
compiled Lua output; fix `.moon` files and rebuild through `alfons compile`.

Project-local adaptations added around the import:

- Root `Alfons.moon` compiles from `src/engine/` to `build/engine/vnds/`.
- Root `lovebrew.toml` packages `build/engine/vnds/` for the 3DS target.
- Upstream busted specs live in `tests/engine/upstream/`.
- Upstream `3ds_convert.sh` is preserved as `tools/engine/3ds_convert.sh` for
  Phase 1 asset-pipeline reference only; it is not safe enough to use as-is for
  untrusted archives.
