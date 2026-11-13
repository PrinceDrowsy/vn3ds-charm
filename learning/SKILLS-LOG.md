# SKILLS-LOG.md — VN3DS-CHARM

> Append-only. Patterns, techniques, and non-obvious learnings discovered
> during cycles. The Orchestrator appends here after every cycle, even if the
> entry is "no new patterns this cycle."

## Pre-Phase-0 learnings (from Phase P research)

- **SKILL-001**: Always verify an upstream repo's actual source language before
  assuming it matches its runtime language. ajusa/VNDS-LOVE runs on Lua at
  runtime but is authored in MoonScript (~93% of the repo) — a fact easy to
  miss if you only check "what does LÖVE Potion execute" rather than "what does
  the `src/` directory actually contain." This changed the entire Engine
  toolchain (ADR-003).
- **SKILL-002**: When a project's `.rpy`/script source is provided by the user
  as owned/legitimate content, it is still *semi-trusted* from a security
  standpoint — archive extraction and subprocess handling should be written as
  if the content could be malformed or malicious, not because the user is
  untrusted, but because malformed data from any external source is a real
  risk class (zip-slip, command injection via crafted filenames).
- **SKILL-003**: For a two-language project (Python + MoonScript/Lua), the
  Developer agent needs an explicit, unmissable statement of which language
  owns which directory before any code is written — this is why
  `STACK-ENGINE.md` opens with the authoring-vs-runtime table rather than
  burying it in prose.

<!-- Cycle entries append below this line -->

## Phase 0 — Cycle 1 / Phase 0.1 Engine Bootstrap (2026-07-04)

- **SKILL-004**: When importing an upstream MoonScript/LÖVE project into a repo
  with a different layout, keep `.moon` authoring files under the project source
  tree and compile to an ignored build directory. Add a structural verifier so
  machines without LuaRocks/LÖVE Potion tooling can still validate the import.
- **SKILL-005**: Preserve upstream one-off conversion scripts as reference only
  unless they were designed for semi-trusted archives. Rebuild converter-facing
  asset pipelines in Python with safe-path confinement and argument-list
  subprocess calls.
