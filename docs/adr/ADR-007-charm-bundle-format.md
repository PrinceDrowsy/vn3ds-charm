# ADR-007 — The `.charm` Bundle Format

**Status:** Accepted (format version 0.x: unstable until R3)
**Date:** 2026-11-13
**Deciders:** PrinceDrowsy
**Supersedes:** ADR-002's `script.vnds` + `manifest.json` bundle

## Context

The bundle is the only contract between Witch and Enchantment
(`docs/REWORK-PLAN.md` §4). The old text bundle let the two sides drift
apart: the engine silently skipped opcodes it didn't know (all 219
transitions in Mice Tea), the converter wrote jumps to labels that didn't
exist (203 in Cooking Companions), and a flat asset namespace collapsed 46
different `Eyes Neutral.png` files into one. Parsing the whole text script
at load also cost ~40 MB for Mice Tea.

The new format has to be read on an Old 3DS with no parsing, and it has to
make those failures detectable before a bundle ever reaches the device.

## Decision

1. **One schema, two readers.** The format is declared once, in
   `src/witch/bundle/schema.py`. Witch's writer and reader are driven by it,
   and the C header Enchantment uses (`src/enchantment/include/charm_schema.h`)
   is generated from it, with `_Static_assert`s on every struct size and field
   offset. A test fails if the committed header is out of date, and the
   header is compiled for both the desktop and devkitARM so the layouts are
   checked on the real target.
2. **Container.** Little-endian (both the ARM11 and x86 are). A 16-byte header
   (`"CHRM"`, major and minor version, section count, file size), then a table
   of 16-byte section entries (tag, chunk, offset, size). Sections start on
   16-byte boundaries. Offsets are `u32`; FAT32 caps a file at 4 GiB anyway.
   Content too large for one file (video, voice) will live in companion files
   when R3/R6 need them.
3. **Fixed-layout tables, used in place.** Every record field is 4 bytes
   (`u32`, `i32`, `f32` or a reference), except the node and displayable
   headers, which pack `kind` and `flags` as two `u16`s. A reference is an
   index into another table, with `0xFFFFFFFF` meaning none. A string is a
   byte offset into the string pool (`STRS`), which starts with an empty
   string, so offset 0 is `""`. Strings are UTF-8 and NUL-terminated.
4. **Nodes.** `NODE` holds one 12-byte record per Ren'Py node:
   `kind`, `flags`, `next` and `args`. `args` is the word offset of the
   kind's payload struct in `ARGS`, a pool of `u32` words. Payloads with lists
   store them as (word offset, count) pairs in the same pool. `next` is
   always explicit, as in Ren'Py's own chained AST; `none` ends the script.
   Parallel tables hold what the runtime rarely needs: `NAME` (Ren'Py's node
   name, the id saves use, so saves survive reconversion) and `LOCS` (source
   file and line, for reports and crash messages).
5. **Kinds are numbered explicitly and never renumbered.** Kind 0 is
   `unknown`: the harvester emits it for a Ren'Py node class it has no
   mapping for, with the class name, so the gap is reported instead of
   silently skipped. A kind number the reader doesn't know is a hard error.
6. **Other tables.** `LABL` (label name to node, sorted by name for binary
   search, so `jump expression` needs no index build at load), `CODE`
   (Python source plus its precompiled `.mpy` blob, filled in R2), `ASST`
   (assets by their original path inside the game, sorted, with their data in
   `DATA`), `IMGS` (Ren'Py image names to displayables, sorted) and `DISP`
   (displayable records, same shape as nodes). Sections are added as later
   phases need them (ATL, screens, styles, the init snapshot).
7. **Chunks.** Every section entry carries a chunk number, 0 meaning global.
   The format can split script sections per source file or label range for
   on-demand loading; how they are split is decided in R3 from measured
   memory.
8. **Versioning.** A minor version adds sections, kinds or trailing payload
   fields; a reader rejects a newer major version. Major version 0 promises
   nothing: until Enchantment reads bundles (R3), any change is allowed and
   bundles are simply reconverted.
9. **The verifier gates every bundle.** `python -m witch verify` checks the
   structure (bounds, references, sorting, string offsets) and then the
   meaning (missing labels, unknown kinds, missing images and assets, asset
   paths that collide when case is ignored, as FAT32 and Windows ignore it),
   and writes Problem Report v2 (`REWORK-PLAN` §13.2). It exits non-zero on
   any crash or stuck problem a player can reach.

## Consequences

- Loading a section is one read into memory; nothing is parsed or
  rebuilt on the 3DS.
- Any change to the schema shows up as a diff in the generated header and
  fails to compile on whichever side disagrees.
- Paths keep the game's own directory tree, so name collisions can't happen
  by construction; the verifier still checks for case-only collisions.
- Two fields of every node are references, so a bad reference can't crash
  the engine silently: the verifier rejects any out-of-range one first.
- Python payloads and displayable trees beyond plain images are filled in by
  later phases (R1, R2, R4) as minor versions.

## Alternatives considered

- **JSON or MessagePack.** Needs a parser and a second in-memory copy on the
  3DS; the old pipeline's text format is what cost ~40 MB. Rejected.
- **FlatBuffers or Cap'n Proto.** Zero-copy, but adds a schema compiler and a
  runtime library on both sides for what fixed records already give. Rejected.
- **SQLite.** Convenient queries on the PC, but a heavyweight dependency and
  page cache on the 3DS. Rejected.
- **A hand-written C header kept in step with Python by review.** This is how
  the old allowlist drifted. Rejected for generation.
