# STACK-TESTING.md — Testing Stack

VN3DS-CHARM has two independent test suites, matching the two-language split.

## Converter tests — `pytest`

- **Location:** `tests/converter/`
- **Regression corpus (spec §14):**
  - Ren'Py's bundled sample **"The Question"** — full convert expected zero
    `blocking` items
  - Hand-written `.rpy` snippets, one per flagged category in `problems.json`'s
    `category` enum (`python`, `screen`, `atl`, `displayable`, `video`, `text-tag`,
    `audio`, `asset`, `flow`, `live2d`, `missing-dlc`, `unknown`), each asserting
    the Problem Report contains the expected entry
- **Determinism tests:** same input run twice → byte-identical bundle output
- **Coverage target:** TBD — set once Phase 1 converter skeleton exists; record
  here once decided

## Engine tests — `busted`

- **Location:** `tests/engine/` (`.moon` test files, or `.lua` if testing compiled
  output directly — prefer testing `.moon` source pre-compile where `busted`
  supports it)
- **Regression corpus (spec §14):**
  - Existing VNDS community scripts (Tsukihime, Saya no Uta, Kanon — standard
    VNDS format, freely available) — must play correctly, unmodified, on the
    forked engine. If these break, it's a fork regression, not a feature gap.
- **Inherited from upstream:** ajusa/VNDS-LOVE already uses `busted`; the Tester
  agent inherits this harness rather than starting from zero.

## Hardware/emulator validation (not part of the automated suite)

- **Azahar, Old 3DS profile** — the default iteration loop for both converter
  output and engine behavior. Not scriptable as a unit test; validated manually
  or via phase-boundary checklists (spec §13 per-phase exit criteria).
- **Real Old 3DS hardware** — validated at phase boundaries only, not per-cycle.
- **O3DS stress test (Phase 0 gate):** background (ETC1) + two sprites (ETC1A4) +
  streamed OGG simultaneously; memory measured via LÖVE Potion's reporting; must
  stay under the 70MB hard ceiling (target ≤45MB). This is a manual/scripted
  Azahar check, not a `pytest`/`busted` unit test — record results in
  `learning/METRICS-HISTORY.md`.

## What "tests pass" means for the factory loop

The Tester agent's cycle output (spec/factory contract) requires:
- `pytest` suite green for any converter change
- `busted` suite green for any engine change
- No memory regression beyond the 70MB ceiling for engine changes (spot-checked
  via Azahar Old 3DS profile stress test at minimum every phase boundary, more
  often if a change plausibly affects memory)
