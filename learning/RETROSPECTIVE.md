# RETROSPECTIVE.md — VN3DS-CHARM

> Written at the close of each phase (or at cutover). Not a per-cycle log —
> see `METRICS-HISTORY.md` for that. This file captures higher-level lessons:
> what worked, what didn't, what to change for the next phase or project.

<!-- Phase retrospectives append below this line, most recent last -->

## Rework R0 → R2.2 (2026-11-13 / 14)

The first phases of `docs/REWORK-PLAN.md`: the bundle format and verifier
(R0), the Old 3DS spike (H), the Ren'Py harvester across the whole library
(R1), and the start of game logic (R2.1–R2.2).

### Decisions that worked, and why

- **Measure the hardware before building on it (phase H).** Five runs on the
  owner's Old 3DS turned three assumptions into numbers before any engine
  code existed: logic fits (37–45 ms per interaction), GC pauses don't shrink
  with heap size (110–160 ms), and boxed floats are the real per-frame cost.
  Each became a design decision (D24 NaN-boxing, D25 VM on its own thread,
  D26 native C for known libraries) instead of a late rewrite.
- **Use the original engine as the reader, not a hand parser (R1).** The old
  pipeline's hand-written `.rpy` parser was the root of the November crash
  bugs. Running each game's own Ren'Py read 17 games across Ren'Py 6.15–8.5,
  3.67 million nodes, every count matching Ren'Py's own.
- **Ask the engine for its own transformations instead of copying them
  (R2.1).** Ren'Py's literal wrapping and Python 2 fixes differ in nearly
  every version. `py_compile(ast_node=True)` returns exactly what that
  version would compile; reimplementing it per version would have drifted.
- **One measurable check per claim.** "Node count matches Ren'Py's", "every
  snippet converts and compiles", "no conversion-introduced crash": each runs
  on the whole corpus, so a regression shows as a number changing.
- **Separate "we broke it" from "the original has it".** Jumps to DLC labels
  and images a game never defined were first reported as our crashes.
  Checking against what Ren'Py itself loaded showed they're the game's own;
  reporting them apart keeps the gate meaningful.

### Mistakes, what they cost, and what prevents them now

- **Harvests made Steam launch the owner's installed games.** Long Live the
  Queen and Magical Diary call `SteamAPI_RestartAppIfNecessary`; started from
  a copy, they ask Steam to start the real game and quit. Several harvests
  opened the owner's real copies (logging a little playtime) before the
  cause was found, and the first symptom ("did you open Long Live the
  Queen?") was first explained wrongly as a stuck harvest.
  *Prevention:* scan scripts for the call before launching; a stand-in
  steam_api DLL in the scratch copy; a watch on the installed folder that
  closes anything a harvest starts; `RENPY_NO_STEAM` always.
  *Lesson:* a program run "headless" can still reach other software on the
  machine. When it misbehaves, look at what else started.
- **A screenshot captured the owner's desktop.** Trying to see a game's
  window, a full-screen capture took the owner's browser and editor instead.
  Deleted at once. *Prevention:* never capture the screen to debug; make the
  program report its own state (the harvest's `.error` file, stack probes).
- **Assumed launch arguments were stable across Ren'Py versions.** DateWarp's
  6.17 launcher inserts the base directory itself, so `. witch_harvest` was
  read as the command `.`. *Prevention:* the harvest starts from an
  environment variable at the end of init, with no arguments to parse.
- **Assumed `isinstance(x, list)` meant the built-in list inside Ren'Py's
  store.** The store rebinds `list`/`dict` to rollback-tracking subclasses, so
  lists came out as opaque objects, and Katawa Shoujo's 1.4 million nodes held
  in those containers ran a 32-bit Ren'Py out of memory. *Prevention:* fetch
  the real built-ins; stream output node by node.
- **Read node fields from `__slots__` only.** Ren'Py 8.5 dropped `__slots__`
  for class annotations and keys its name map by node, so one game harvested
  empty and failed later with a `KeyError`. *Prevention:* read slots,
  annotations and instance attributes; take names from the nodes.
- **Spike measurements that measured the test.** H.1's 4.5 ms frame worst case
  came from running 600 frames with GC disabled, and its "largest malloc
  512 MB" from a probe the allocator fooled. Both nearly drove decisions.
  *Lesson:* when a number surprises, check the harness before the hardware;
  prefer measurements that can't be fooled (mallinfo; GC kept out of the
  timed region but still running).
- **A file rewrite that changed line endings and corrupted UTF-8.** A script
  converting call sites wrote CRLF and used `ast` column offsets (UTF-8
  bytes) as string offsets, mangling a line of Japanese text. Caught by the
  diff size and a failing test. *Prevention:* rewrite source as bytes with
  line endings kept, and read the diff before running tests.
- **Shell quoting ate escapes in generated code, three times.** Heredocs
  through the Bash tool turned `\\n` into newlines or failed on quotes.
  *Prevention:* write code and notes with the Write/Edit tools, never through
  shell heredocs.
- **A `sed` by line number after an insertion overwrote the wrong line.**
  (R2.3) An Edit inserted 17 lines above the target, then `sed '364s/…/'`
  replaced an unrelated `if i:`, with its `\n` escapes turned into newlines
  too. Caught by reading the diff; restored from git and redone with Edit.
  *Prevention:* never address lines by number in a file just edited; match
  on content with the Edit tool, and check `git diff` for unexpected `-` lines.
- **Tests with their own bugs.** Twice a failing test was the test's fault (a
  hard-coded node index, a jump placed after another jump). Read the failure
  before changing the code under test.

- **A build installed Python on the owner's machine.** (Found R2.3, caused
  2026-11-13.) Building MicroPython's `mpy-cross` from Git Bash, its makefile
  ran a bare `python3`, which Windows resolved to the Python install
  manager's alias. That installed Python 3.15.2 into the build folder, added
  Start Menu and Add/Remove Programs entries for it, removed Python 3.14's,
  and updated the manager. Unnoticed for a day; found only through `git
  status` in the MicroPython checkout. Cleaned up with the owner's approval
  (registry backups in `D:\ClaudeScratch\python-cleanup-backup`), and 3.14's
  registrations restored with `py install --refresh`.
  *Prevention:* never run a build with a bare `python`/`python3` on Windows;
  pass an absolute interpreter (`PYTHON=…`) and a PATH without WindowsApps.
  *Lesson:* check `git status` and the filesystem after any tool's first run,
  and read a build's log for anything it did beyond building.
- **A catch-all `__getattr__` shadowed real submodules.** (R2.3) The shim's
  package-level `__getattr__` answered `from renpy import py2` with a
  placeholder, so the Python 2 helpers were silently never installed; it
  showed up only because placeholders report every use. *Prevention:* a
  catch-all must try the real thing first (import the submodule), and its
  uses must be reported, never silent.

- **Order lost through a Python 2 dict.** (R2.4) The harvest built its
  module list as a dict inside Ren'Py's Python 2, where dicts are unordered,
  so `renpy.preferences` loaded before the `renpy.object` it subclasses.
  *Prevention:* anything the harvest emits whose order matters is a list of
  pairs; never rely on dict order in code that may run on Python 2.
- **Staged changes went into the wrong commit.** (R2.4) A `git rm` staged
  earlier rode along with an unrelated "normalize line endings" commit,
  because `git add X && git commit` commits everything staged. Pushed, so
  left as is. *Prevention:* `git diff --cached --stat` before every commit.
- **Line endings again.** Four files had been committed as CRLF after Python
  `write_text` rewrites. *Prevention:* same as above; and
  `git ls-files --eol | grep crlf` now and then.

- **A converter check that tested syntax, not meaning.** (R2.4) R2.2's
  corpus check was "every snippet converts and compiles", and it passed,
  but the plan's own list for R2.2 included Python 2's list-returning
  `keys()`/`items()` and it had been left out. It surfaced only when Ren'Py's
  common code ran: 33 of Jisei's 62 init errors were `view + view`.
  *Prevention:* go through the plan's checklist item by item when closing a
  step, and test a converter on behaviour (run the output), not only on
  whether it compiles.

- **A comparison test that never reached the branch it should have
  tested.** (R2.4) The `colorsys` stand-in matched CPython on 20,000
  random cases, yet its `rgb_to_hls` used `2.0 - (maxc + minc)` where
  CPython uses `2.0 - maxc - minc`, which rounds differently in about half
  of the light colours. The random values rarely reached that branch. Found
  by recalling CPython's own comment on it, then confirmed (154,935
  differences in 300,000 light colours). *Prevention:* when comparing a
  rewrite against the original, pick inputs that drive every branch, and
  count how many cases each branch saw.

### What to do differently

- Run the widest corpus as early as possible: the version differences
  (Ren'Py 6.15 to 8.5) were the real work, and each surfaced only when a game
  of that version ran.
- Before running anything a game ships, ask what else it can touch: the
  network, other processes, Steam, files outside its folder.
- Keep this file and `SKILLS-LOG.md` current while working, not only at the
  end of a phase.
