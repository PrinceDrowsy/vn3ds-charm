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

## Rework R0 → R2.2 (2026-11-13 / 14)

- **SKILL-006: Generate the C header from the Python schema.** One declaration
  (`schema.py`) drives Witch's writer and reader and Enchantment's header,
  with `_Static_assert` on every size and offset, compiled under desktop gcc
  and devkitARM in a test. Drift between the sides is a compile error.
- **SKILL-007: Harvest from inside the original engine.** Copy the game to
  scratch (hard-link read-only media), install one script that runs at the
  very end of init when an environment variable is set, write the result
  under a temporary name and rename it, then `os._exit`. Works on every
  Ren'Py from 6.15 to 8.5 without depending on launch arguments.
- **SKILL-008: Ask the engine for its own transforms.** Where the original
  engine transforms code before running it (Ren'Py's `py_compile`), call that
  and record the output: `ast.unparse` on Python 3, the tree as JSON on
  Python 2. Don't reimplement version-specific engine logic the engine can
  be asked for.
- **SKILL-009: Stand-in DLLs without a compiler.** A DLL that only has to
  export names returning 0 can be written directly as a PE image (one
  section, one `xor eax, eax; ret`, the export names read from the real DLL),
  for x86 and x64. Used to keep Steam out of harvests.
- **SKILL-010: Diagnose a stuck process from inside it.** A probe that starts a
  thread at the earliest init and dumps every thread's stack after a delay;
  if it never writes, the process exited or blocked in C, so check the exit
  code next. Never screenshots.
- **SKILL-011: Inherited vs introduced.** Give the verifier what the original
  engine itself loaded (`Source`: labels, image tags). A fault the original
  has too is reported but doesn't gate the build.
- **SKILL-013: Grow a shim from placeholders.** Unimplemented API names
  resolve to recording placeholders (with the statement running at the
  time), unimplemented modules to placeholder modules registered in
  `sys.modules` from the original's own module list, and the original
  library's pure-Python modules run from its source a statement at a time.
  One run then lists every gap, ranked. Dunder names must never be
  placeholders (import machinery and `hasattr` probe them), and a package's
  catch-all must try the real submodule first.
- **SKILL-014: MicroPython vs CPython, as found running Ren'Py's code.**
  `dict(x)`/`update(x)` ignore dict subclasses (patched:
  `src/enchantment/micropython/patches/`); a built-in subclass is built
  from the constructor's arguments before `__init__`, and `super()` doesn't
  reach its special methods (use `get`, factories); unbound `dict.items(self)`
  fails on subclasses (use `super()`); no `vars`, `collections.defaultdict`,
  `copy`, `os.environ`; built-in modules are read-only (proxy them in
  `sys.modules`); module `__getattr__`, `exec` into dicts and overriding
  built-ins all work. Functions take no attributes of their own
  (`f.help = …`), which Ren'Py relies on: patched with a lazily created
  dict per function (`0002-function-attributes.patch`, checked with
  MicroPython's own basics suite, 534 tests). Tuples, strings and bytes
  refused stepped slices (`args[0::2]`, `s[::-1]`; lists took them), and
  built-in types had no `__new__` (`tuple.__new__(cls, x)`, which Ren'Py's
  `Color` and 74 corpus call sites use): patches 0003 and 0004, each checked
  against CPython's output and the basics suite. Native list, dict and
  set operations refused instances of their subclasses on the right
  (`[1] == RevertableList([1])` was False; `list + RevertableList`
  raised): patch 0005. Patches must apply in order on a clean checkout;
  rebuild each later patch against the earlier ones (`git diff --no-index`
  from a patched copy) and check the result matches the working tree.
- **SKILL-015: Produce, check, fall back.** When part of an original
  engine has to be rewritten by hand (D27's description classes), have
  the rewrite produce the output, have the original engine produce the
  same output in a neutral form, and compare on every conversion. Where
  the two differ and the output doesn't depend on runtime state, ship the
  original's. A hand-written layer then can't silently drift, and every
  game converted is a conformance run.
- **SKILL-016: Decide a boundary from measurements, at the original's own
  seams.** D27 came from five numbers (source size, heap per line,
  per-frame cost, how much the public API moves across versions, how many
  games subclass the API), not from taste; and the zones follow what
  Ren'Py itself compiled versus left in Python.
- **SKILL-017: Emulate the original's phases, not just its order.** Ren'Py
  creates every store and runs `python early` while it *loads* the
  script, before init; running only the init order left `gui` undefined
  for styles that name it. Harvest which statement classes have an
  `early_execute` from the game's own Ren'Py instead of hard-coding them,
  since the set changes between versions (8.3 added `transform`).
- **SKILL-018: Python 2 list comprehensions leak their variables;
  Python 3 can emulate it.** Run each loop under a private name and bind
  the real one with `:=` as the comprehension's first condition (`:=`
  binds in the enclosing scope). Not allowed in a class body or on a name
  an enclosing comprehension iterates; leave those unleaked.
- **SKILL-012: Spike on the real target early,** with go/no-go numbers set in
  advance, and keep the spike's code (`spikes/hardware/`) so the numbers can
  be reproduced.
