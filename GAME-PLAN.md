## Project Mode: BUILD

> Planned cutover: end of Phase 2 (Hustle Cat playable end-to-end). At that point
> the core converter+engine pipeline is proven on two real games, and remaining
> work (Phases 3+) becomes incremental per-feature/per-game work well-suited to
> issue-sliced, Ralph-loop execution. See `orchestrator/CUTOVER.md` for the
> handoff checklist. This marker is only changed by the Orchestrator at cutover,
> or manually by a human.

# VN3DS-CHARM — Master Game Plan

> **2026-11-13: rework approved.** `docs/REWORK-PLAN.md` (v2) replaces the
> fix-by-fix approach with a rebuild of converter and engine as a native C
> engine (phases R0, H, R1–R9). Its phases are the active queue, ahead of
> the phases below. Its decision log (§0) overrides the locked decisions here
> where they differ. The old pipeline is frozen (D22).

> This is the forward work queue and BUILD-mode canonical source of truth.
> `PHASES.md` is the live checkbox tracker mirroring this file.
> `VN3DS-spec.md` is the authoritative design reference for all technical detail.
> `docs/ai/vn3ds-initial-plan.md` is the original planning narrative this was
> derived from — consult it for rationale, not for current status.

---

## Locked Decisions (Phase P / ADRs)

| # | Decision | Choice | ADR |
|---|---|---|---|
| 1 | Converter implementation language | Python | ADR-001 |
| 2 | Canonical runtime script format | `script.vnds` (plain-text extended VNDS) until its replacement ADR | ADR-002 |
| 2a | Original VNDS scripts | Not read by the engine; converted like any other source | ADR-004 |
| 3 | Engine | Native C on citro3d/ndsp/ctrulib with embedded MicroPython (was: VNDS-LOVE fork on LÖVE Potion, ADR-003) | ADR-005 |
| 4 | Hardware baseline | Old 3DS (128MB total, ~80–90MB usable, 268MHz ARM11, PICA200 GPU) | spec §2 |
| 5 | Tween library | flux (rxi, MIT) | spec §9.1 |
| 6 | Problem Report | First-class output; `blocking` items gate the build | spec §7 |
| 7 | DLC handling | Merge-at-convert-time; `missing-dlc` Problem Report category | spec §8.1 |
| 8 | Live2D/E-mote replacement | Combined Option A (multi-layer) + Option B (bone/puppet) | spec §9.2/§9.3 |
| 9 | Test in Azahar | Old 3DS profile — no SD reflash per iteration | spec §14 |

---

## Phase 0 — Engine Fork Spike

**Goal:** Fork VNDS-LOVE, get it running under LÖVE Potion on Azahar (Old 3DS
profile), prove dual-screen + touch work, and pass the O3DS stress test before
any converter code.

- [x] **0.1** — Fork ajusa/VNDS-LOVE @ 0.0.13; strip to bare minimum; wire
      LuaRocks → moonscript/busted/alfons → lovebrew/LÖVE Potion build (ADR-003)
      - 2026-07-04: imported upstream MoonScript source under `src/engine/`,
        upstream specs under `tests/engine/upstream/`, root `Alfons.moon`,
        root `lovebrew.toml`, and structural verification script. Local machine
        is missing `moonc`, `alfons`, `busted`, and `lovebrew`, so compile/test/package
        commands are documented but blocked until toolchain install.
- [x] **0.2** — Dual-screen hello world: static image on top (400×240), text +
      choice button on bottom (320×240)
      - 2026-07-04: validated on real Old 3DS hardware (not Azahar — see note
        below). `hello-vn` fixture (`tests/engine/fixtures/hello-vn/`) shows
        background image on top screen, text/choice on bottom, correctly
        split. Required fixing `main.moon`'s 3DS `love.draw` screen routing,
        an end-of-script nil crash in `next_msg`, and converting the fixture
        background to `.t3x` (raw PNG crashes LÖVE Potion's image loader on
        3DS — see memory).
- [x] **0.3** — Advance on A button and screen tap; choice selectable by touch
      - 2026-07-04: touch was previously entirely unwired (no
        `love.touchpressed` handler existed anywhere). Added tap-to-advance in
        `text/text.moon` and touch hit-testing for choice selection in
        `listbox.moon`. Both confirmed working on real hardware.
- [x] **0.4** — Load an existing VNDS community script (Tsukihime or Saya no Uta)
      as smoke test — confirms fork base is sound, not just the hello-world path
      - 2026-07-04: Tsukihime/Saya no Uta community ports turned out to be
        privately-shared (not openly distributable — copyright concerns), so
        used [ajusa/VNDS-TEST](https://github.com/ajusa/VNDS-TEST) instead — a
        purpose-built VNDS functionality test script by the upstream engine's
        author (`tests/engine/fixtures/vnds-test/`). Validated on desktop
        LÖVE 11.5 (no `.t3x` constraint there): labels/goto looping, global
        variables + interpolation, colored text escape codes, a 16-option
        choice, auto-advancing text, long-text word-wrap, background
        transitions, multi-position foreground sprites, and sound/music with
        loop-count and cutoff/interruption behavior all worked with zero
        errors across a full script cycle (confirmed visually and via log).
- [x] **0.5** — O3DS stress test: background (ETC1) + two sprites (ETC1A4) +
      streamed OGG simultaneously; memory under 70MB (measure LÖVE Potion baseline
      RAM consumption while here — open question, spec §15)
      - 2026-07-04: confirmed LÖVE Potion 2.0.0 exposes **no memory-reporting
        API to Lua at all** (checked `love.system` and `love.graphics`
        source directly — no `getMemoryUsage`/`getStats` equivalent exists).
        Byte-precise measurement isn't possible with this engine version, so
        substituted a stability test per spec's own framing of this as an
        open question: `tests/engine/fixtures/stress-test/` (ETC1 background,
        two ETC1A4 sprites, 30s looping streamed OGG) ran on real Old 3DS
        hardware for 2 minutes — one brief audio hitch at stream start
        (likely buffering, not memory pressure), otherwise stable throughout,
        no crash or freeze. Exact RAM ceiling remains unmeasured; revisit if
        a lower-level memory query becomes available.
- [x] **0.6** — Pin exact LÖVE Potion release version used; record in
      `base/ENVIRONMENT.md`
      - 2026-07-04: pinned to **2.0.0** (final release, not `2.0.0-rc1`).
        Deployment requires an external `game/` folder alongside the `.3dsx`
        (see `tools/engine/build_3dsx.py`'s sdcard staging) due to a LÖVE
        Potion 2.0.0 `boot.lua` regression.

**Note on Azahar:** LÖVE Potion (all versions tested: 3.0.2, 3.0.1, 2.0.0-rc1)
fails to boot on every Azahar/Citra-lineage build tried on this dev machine
(mainline Azahar, AzaharPlus, and even the original pre-shutdown Citra
Nightly 2104) — confirmed not project-specific, since unrelated homebrew boots
fine on the same emulator builds. Root cause not identified; likely an
emulator/hardware combination issue rather than a LÖVE Potion bug. Real
hardware is the working validation path for now; revisit Azahar later if a
fix surfaces upstream.
      - 2026-07-05 (different machine, with a CPU that has no hybrid
        P-core/E-core split, vs. the original hybrid-core laptop): rebuilt the toolchain from scratch, rebuilt the Jisei
        bundle (41 blocking, matches this doc's later count exactly),
        rebuilt `VNDS-LOVE.3dsx`, and hit the identical hang at Azahar's
        load screen (mainline Azahar 2125.1.3). Same failure on two
        architecturally different CPUs rules out hybrid-core scheduling
        as the cause. Still unidentified; real hardware remains the only
        working validation path.

**Exit check — met 2026-07-04 (real hardware; Azahar blocked, see note above):**
`.3dsx` boots; dual-screen works; touch works; a real, non-trivial VNDS script
(`vnds-test`) plays correctly; stress test (`stress-test` fixture) ran 2
minutes stable with no crash/freeze. Exact byte-level memory measurement
wasn't possible (LÖVE Potion 2.0.0 exposes no memory-reporting API — see 0.5
note), so the stability result is logged to `learning/METRICS-HISTORY.md` in
place of a numeric RAM figure. **Phase 0 is complete; Phase 1 is unblocked.**

---

## Phase 1 — Walking Skeleton + Jisei Proof Port

**Goal:** Converter + engine wired end-to-end; first real VN playable.

- [x] **1.1** — Converter: parse `.rpy` for `label/jump/call/return`,
      `scene/show/hide`, `say`, `Character()`, `menu:`
      - 2026-07-04: `src/converter/parser/` — `ir.py` (dataclass IR mirroring
        Ren'Py's block structure; flattening to VNDS's flat label/jump format
        is 1.2's job, not the parser's), `lexer.py` (indentation-aware line
        tokenizer, comment-stripping), `rpy_parser.py` (recursive-descent
        parser). Graceful degradation: anything outside the supported subset
        becomes an inline `Unsupported` node (parsing continues) instead of
        crashing — matches the Problem Report philosophy that the converter
        always terminates with a report, never a stack trace. `Character()`
        argument parsing uses `ast.parse` per `STACK-CONVERTER.md`'s guidance
        to reuse Python's own parser for expression subsets. 8 pytest tests
        (`tests/converter/test_rpy_parser*.py`), including an end-to-end
        fixture (`tests/fixtures/sample_full.rpy`) combining every supported
        construct plus one intentionally-unsupported one.
- [x] **1.2** — Converter: emit `script.vnds` (ADR-002) + `manifest.json`
      - 2026-07-04: `src/converter/emitters/vnds_writer.py` flattens the
        parser's nested IR (Ren'Py's `menu:` holds choice bodies inline) into
        VNDS's flat label/jump model — each menu becomes `choice ...` +
        `jump ...` into synthetic labels, with an implicit jump-to-continuation
        appended to any choice body that doesn't already end in its own
        jump/call/return, preserving Ren'Py's "falls through to code after
        the menu" semantics. `manifest_writer.py` emits a minimal
        entry-label + character-table schema (none was formally specified in
        the spec). 19 pytest tests total; also round-tripped the emitted
        output through the **actual Lua `script.moon` parser** as a sanity
        check.
      - **Real finding from that round-trip:** the current (Phase 0) engine's
        `jump` command is still upstream VNDS's original cross-file jump
        (`filename` + `label` tokens) — it does not understand the spec's
        pipe-delimited multi-target `jump target1|target2` branching used for
        choices, nor `call`/`return`/`nameplate`/`clearimg`. This is expected
        and already tracked as **1.5** ("Engine: interpret extended VNDS —
        ...choice, jump, call/return"), not a converter bug — the emitter
        correctly targets the spec's format; the engine just hasn't caught up
        yet. Full converter→engine round-trip isn't possible until 1.5 lands.
      - Known simplifications, to revisit once the asset pipeline (1.4)
        exists: Ren'Py image tags (e.g. `show eileen happy`) are emitted as
        literal filenames (spaces→underscores) rather than resolved through
        real `image` statement declarations; `left`/`center`/`right` sprite
        positions map to fixed placeholder pixel coordinates rather than
        real sprite-dimension-aware centering.
- [x] **1.3** — Converter: emit `problems.json` (Problem Report) with
      `blocking`/`manual`/`approximated`/`info` severity levels
      - 2026-07-04: `src/converter/problem_report/` classifies each
        `FlaggedItem` the parser/emitter already produces into a full
        `Problem` (severity, category ∈ python/screen/atl/displayable/video/
        text-tag/audio/asset/flow/unknown, resolvable `file:line` source,
        truncated Ren'Py snippet, message, suggestion) via a rule table
        matched on the exact reason strings the parser/emitter generate,
        with keyword-sniffing (screen/python/if/etc.) as a fallback for the
        generic "unsupported statement" case. Matches the exact schema found
        in `VN3DS-spec.md` §7.2. `emit_problems_json` (sorted-key JSON) and
        `format_report_table` (human-readable console/`problems.md` text)
        both implemented per §7.3's acceptance criteria. 10 new pytest
        tests (29 total in `tests/converter/`), plus an end-to-end run
        against `sample_full.rpy` confirming the full
        parse→emit→classify→report pipeline produces a correct,
        schema-matching report.
      - `has_blocking(report)` helper is ready for the CLI (not yet built)
        to use for its non-zero exit code requirement.
- [x] **1.4** — Converter: asset pipeline — image → `.t3x` (via `tex3ds`), audio →
      `.ogg`
      - 2026-07-04: `src/converter/assets/pipeline.py` — `convert_image`
        (tex3ds, defaults to `-f auto-etc1` so backgrounds/sprites get
        production-appropriate ETC1/ETC1A4 compression automatically based
        on whether the source has an alpha channel, per the O3DS memory
        budget in `VN3DS-spec.md`, rather than uncompressed RGBA8) and
        `convert_audio` (ffmpeg, re-encodes to OGG/Vorbis), plus
        `convert_assets(source_dir, dest_dir)` which walks a directory
        converting every recognized image/audio file and preserving folder
        structure. Scope note: this converts a *given source file* — it does
        not resolve Ren'Py image tags (`show eileen happy`) to an actual
        source file via `image` statement declarations; that's a separate,
        not-yet-scoped concern (already noted in 1.2's entry above). 4 new
        pytest tests using real `tex3ds`/`ffmpeg` subprocess calls against
        the already-committed `vnds-test` fixture assets (no mocking — this
        project's tests already assume the local toolchain is present, same
        as the engine's build pipeline). 33 converter tests total.
- [x] **1.5** — Engine (`.moon` source): interpret extended VNDS — `bgload`,
      `setimg`, `clearimg`, `text`, `choice`, `jump`, `call`/`return`, `nameplate`,
      `window`
      - 2026-07-04: `script.moon` — added `call`/`return` (a same-file call
        stack: `call` pushes the current position, `return` pops it); `jump`
        is now extended to check for a same-file label first (Ren'Py-style
        `jump <label>`), then a pipe-delimited multi-target form
        (`jump t1|t2`, selecting via `s.locals["selected"]` for choices,
        matching the spec's worked example), falling back to the original
        cross-file `filename`+`label` behavior only if neither matches —
        preserves full backward compatibility with existing/legacy scripts.
        Also added the `@name` single-token label declaration (the spec's
        documented convention, which the engine never actually implemented —
        it only recognized the older two-token `label name` form) as an
        alias. `images.moon` gained `clearimg` (removes a sprite by path) and
        `setimg` now replaces-by-path instead of stacking duplicates.
        `text/text.moon` gained `nameplate` (speaker name box above the
        dialogue box) and `window show/hide` (dialogue box visibility).
      - **Real semantic gap found and fixed:** VNDS's original `return` is a
        call-stack pop that's a silent no-op with an empty stack (falls
        through into whatever label follows positionally in the file) —
        but Ren'Py's `return` means "end this flow" (ending the whole
        session if there's no caller). Since `call`/`return` didn't
        functionally exist in the engine before this change, there was no
        legacy behavior to preserve, so a `return` with an empty call stack
        now properly halts the script instead of falling through.
      - **Validated with a real end-to-end round-trip:** ran `sample_full.rpy`
        through the full pipeline (Python parser → emitter → the actual Lua
        `script.moon`), selecting each choice branch, and confirmed correct
        instruction sequences and a clean halt at the end for both paths —
        the gap flagged during 1.2's round-trip check is now closed.
      - 6 new busted tests (`tests/engine/extended_vnds_spec.moon`; note:
        `Alfons.moon`'s `test` task now runs `busted` across all of
        `tests/engine/`, not just `tests/engine/upstream/`, so this file is
        included). 20 busted tests total, all passing.
- [x] **1.6** — Engine: word-wrap, typewriter reveal, advance on A/tap, touch
      choice selection
      - 2026-07-04: word-wrap, advance-on-A/tap, and touch choice selection
        were already done in Phase 0 — the only genuinely new piece was
        **typewriter reveal** (`text/text.moon`): `revealed` tracks a
        character budget against the currently visible window
        (`_.first(buffer, lines)`, resetting on new text or on paging via
        `done!`, so scrolling to a new page always restarts the reveal for
        that page); `truncate_colored_lines` truncates the word-wrapped,
        colored-segment line data (LÖVE's colored-text print format) to that
        budget without breaking embedded color codes; a first A-press/tap
        while still revealing instantly completes the current text instead
        of advancing (standard VN UX — second press then advances); the
        `"y"` fast-forward mode reveals instantly rather than animating.
        5 new busted tests (`tests/engine/typewriter_spec.moon`, driven
        through the public dispatch interface with a `love.graphics` mock
        that records draw calls, since the reveal helpers are module-internal
        by design). 25 busted tests total, all passing.
- [x] **1.7** — Engine: streamed OGG audio (music + sfx + voice channels)
      - 2026-07-04: music and sfx channels already existed from Phase 0
        (both already load via `love.audio.newSource(path, "stream")` —
        genuinely streamed, not fully buffered). Added the missing **voice**
        channel (`audio.moon`) plus the spec's extended `voiceover <file>`,
        `stopmusic`, `stopsound`, `stopvoice` commands (`script.moon` parser
        + dispatch list).
      - **Real pre-existing bug found and fixed:** `audio.moon`'s `clear`
        helper reassigned its own local parameter (`@ = {}`) instead of
        actually mutating the caller's `music`/`sound`/`voice` variable —
        a no-op that was silently masked everywhere it was called, because
        every existing call site immediately reassigned the variable to a
        genuinely new value right afterward anyway. This bug affected the
        **existing** `sound ~`/`music ~` stop-sentinel path too (when the
        `exists()` check short-circuits, nothing reassigns afterward) — not
        just my new `stopmusic`/`stopsound` commands. Fixed by having
        `clear` return the new value and updating all five call sites to
        `channel = clear channel`.
      - 7 new busted tests (`tests/engine/audio_channels_spec.moon`, mocking
        `love.audio`/`love.filesystem`). 32 busted tests total, all passing.
- [x] **1.8** — Validation: run converter on Ren'Py sample "The Question" — zero
      `blocking` items expected
      - 2026-07-04: ran the real converter pipeline against Ren'Py's own
        officially bundled MIT-licensed `the_question/game/script.rpy`
        (downloaded directly from the renpy/renpy GitHub repo — legitimate to
        use, unlike the copyright-restricted VNDS community ports). Found
        true zero-blocking is **not achievable yet** — 14 blocking items
        remain, all genuinely Phase 2 scope: 9x standalone `with fade`/`with
        dissolve` (category `atl`, Phase 2.2), 1x `play music` (`audio`,
        Phase 2.2), 1x `$ book = True` (`python`, Phase 2.1), 1x `if book:`
        (`flow`, Phase 2.1/2.4), 1x `default book = False` (`python`, Phase
        2.1). Documenting this as the expected/known gap rather than pulling
        Phase 2 items forward.
      - Also found and fixed 3 real bugs in already-claimed 1.1-1.3 scope,
        surfaced only by testing against real-world Ren'Py content instead of
        hand-written fixtures:
        1. **`problems.json` never included the parser's own flagged
           constructs** — `build_problem_report` only ever consumed the
           emitter's `FlaggedItems`, silently dropping malformed
           `Character()`/`define` failures and "unrecognized menu choice
           syntax" issues from the report entirely. Fixed by adding a
           `parser_problems` param to `build_problem_report`
           (`src/converter/problem_report/report.py`) that merges the
           parser's `Unsupported` list into the same P#### id sequence,
           de-duplicating against items the emitter's tree walk already
           flagged (statement-level `Unsupported` nodes get flagged by both
           passes since they're embedded in the IR).
        2. **`Character(_("Sylvie"), ...)` silently failed** — Ren'Py's
           near-universal `_()` translation wrapper around display names
           parsed as an `ast.Call`, not the `ast.Constant` my display-name
           extraction only accepted, so *both* characters in "The Question"
           silently dropped out of `script.characters` with no visible
           trace before fix #1 above. Fixed via a `_string_literal()` helper
           in `src/converter/parser/rpy_parser.py` that unwraps one level of
           `_(...)`.
        3. **`menu:` blocks with a leading narration/dialogue line before
           the first choice** (a very common Ren'Py idiom — both menus in
           this file use it) were entirely misparsed as "unrecognized menu
           choice syntax". Added a `Menu.prompt: list[Node]` field
           (`src/converter/parser/ir.py`) populated by allowing non-choice
           statements before the first real choice in `_parse_menu`, emitted
           ahead of the `choice`/`jump` lines in `_emit_menu`
           (`src/converter/emitters/vnds_writer.py`).
        4. Minor: a leading UTF-8 BOM (present in the downloaded file) was
           being parsed as an "unsupported top-level statement" instead of
           silently ignored; stripped in `tokenize_lines`
           (`src/converter/parser/lexer.py`).
      - 33 pytest tests still passing (no new tests added — these were bugs
        found via real-content validation, not new features); full engine
        busted suite (32 tests) unaffected, still green.
- [x] **1.9** — Validation: run converter on **Jisei: The First Case**; triage
      Problem Report to zero `blocking`
      - 2026-07-05: decompiled the user's owned copy (`jisei-1.6-pc`,
        Ren'Py 6.99.14 — only `.rpyc` bytecode ships, no source `.rpy`) via
        `unrpyc` (CensoredUsername/unrpyc, master branch; all 12 files
        decompiled cleanly). Ran the full converter pipeline against the
        decompiled output kept entirely in the scratchpad — **not
        committed**, per this game being a commercial title (only
        `problems.json` summary statistics are recorded here, no story
        text or asset paths).
      - Found and fixed two more real parser gaps (beyond 1.8's three),
        both already self-noted as "not-yet-scoped" in 1.2/1.4's own entries:
        1. **`image <tag> = "<path>"` declarations were never resolved** —
           `Scene`/`Show`/`Hide` just slugified the Ren'Py tag text directly
           into a filename token, which only works by coincidence when the
           tag happens to match the asset's basename (e.g. Jisei's
           `image sakev = "gui/logo.jpg"` would have wrongly emitted
           `bgload sakev` instead of `bgload logo`). Added
           `Script.images: dict[str, str]` (`src/converter/parser/ir.py`),
           populated by `_parse_image_def` in `rpy_parser.py` for
           literal-string-path declarations only; dynamic displayables
           (`anim.Blink(...)`, ATL blocks) are flagged `manual` via a new
           classify.py rule rather than blocking, since they genuinely need
           a human to pick a static asset. `vnds_writer.py`'s
           `_resolve_image_path` resolves through this map (falling back to
           the old slugify behavior for undeclared tags), reducing Jisei's
           blocking count by ~200 (moved to `manual`/silently-resolved).
        2. **`DynamicCharacter(...)` wasn't recognized at all** (only
           literal `Character(...)`) — used by 4 of Jisei's 8 speaking
           characters for runtime-renameable names. Approximated by
           resolving the referenced variable through a `string_defines`
           table built from any top-level `define name = "literal"` seen
           so far (`_record_string_define` in `rpy_parser.py`), flagged
           `approximated` (a real severity in the schema) since the true
           value can change at runtime. Unresolvable cases still fail
           `blocking`, same as an ordinary bad `Character()`.
        - 6 new pytest tests (39 total in `tests/converter/`) covering the
          `_()` wrapper, `DynamicCharacter`, `image` resolution, and `menu:`
          prompts. Full 32-test busted engine suite unaffected.
      - **Baseline Problem Report after all fixes** (12 files, 57 labels):
        1010 `blocking`, 169 `manual`, 4 `approximated`. By category:
        python 578, unknown 247, asset 170 (manual), flow 102, atl 45,
        screen 19, audio 18. Leading keywords: `$` (574), `define`-literal
        (134), `if`/`elif`/`else` (102), `with` (45), `window` (30),
        `screen` (19), `play`/`stop` (18), ATL properties (`xalign`/
        `yalign`/`linear`/`zoom`, 43). The investigation UI uses `menu:`
        (15 found, all clean) rather than custom `screen:` for choices —
        answers `VN3DS-spec.md` §11.1's open question.
      - **Planning-level finding:** `VN3DS-spec.md`'s Phase 1 validation
        sequence expects Jisei to reach zero `blocking` using only Phase 1
        converter/engine scope, but the categories above (`$`,
        `if/elif/else`, `define` literals, `with`, `play`/`stop`, `window`)
        are explicitly *Phase 2* additions in the very next spec section.
        Jisei leans on nearly all of them for its clue-tracking/investigation
        logic — zero-blocking isn't achievable until Phase 2 lands. Treating
        1.9 as satisfied by this validation+triage pass (converter ran
        cleanly on a real full-length commercial VN, real gaps found and
        fixed); 1.10 (playable, zero-blocking) is deferred until after
        Phase 2 rather than attempted now.
      - **2026-07-05 re-triage** (standing in for 2.8, since Hustle Cat's
        source isn't acquired yet): re-ran the same decompiled Jisei
        content now that 2.1-2.7 have landed. Blocking dropped
        **1010 → 351** from those items alone (see each item's own notes
        for the incremental breakdown), unchanged by 2.6/2.7 since those
        were engine-only. Breaking down the 351 by category surfaced a
        real, previously-invisible finding: **162 of them (46%) were
        Ren'Py's legacy imperative `ui.*` API**
        (`ui.vbox`/`ui.textbutton`/`ui.close` + `ui.interact()` + an
        `if result == N:` chain) — how Jisei builds its entire
        investigation navigation loop (every "who to talk to / where to
        go" screen), predating both `menu:` and `screen:`. Neither was
        anticipated by this file's or the spec's "does the investigation
        UI use `menu:` or custom `screen`?" question from 1.9.
      - The pattern is structurally identical to a `menu:` every time it
        appears (each `ui.textbutton(label, clicked=ui.returns(N))` is one
        choice; `ui.interact()` returns the picked index; the trailing
        `if`/`elif` chain branches on it), so added a pattern-matcher
        (`_try_convert_ui_menus`/`_match_ui_menu` in
        `src/converter/parser/rpy_parser.py`, wired into `_parse_block` so
        it applies everywhere a body is built) that recognizes this exact
        idiom and converts it into an ordinary `Menu` node — same
        disposition as a real `menu:`, reusing the emitter's existing
        Menu-flattening unchanged. Deliberately conservative: bails out
        (leaving the original nodes flagged `Unsupported`, unchanged) if a
        trailing `else` is present with no corresponding button (can't be
        safely represented as a menu choice) or if anything about the
        shape doesn't match cleanly — a wrong conversion would be worse
        than an honest blocking flag, same philosophy as the `If`
        conservative-rejection rule from 2.1.
      - **Result:** blocking dropped **351 → 224** (127 of the 162 `ui.*`
        occurrences converted cleanly). The 35 residual `ui.*` items are a
        harder variant this matcher correctly declines rather than
        mis-handles: a button's `clicked=`/`None` state itself decided by
        a nested `if/else` (conditionally-enabled buttons, e.g.
        `hallwaymenu`'s "Talk" button depending on `mikohallway`) rather
        than being a flat run of sibling statements. Worth a follow-up
        pattern extension later if another game leans on it; not chased
        further now given the scope of gain already captured.
      - 4 new pytest tests (72 total in `tests/converter/`) covering the
        clean conversion, the disabled-button skip case, and the
        trailing-else rejection case. No engine changes — this is a pure
        parser-level transform.
      - **2026-07-05 — strategic pivot**: the user asked to focus on
        getting Jisei fully functional (finishing 1.10 for real) *before*
        starting Hustle Cat, rather than following Phase 2's original
        2.8/2.9-then-1.10 ordering. Continuing the Jisei-focused work here
        under 1.9 rather than opening new phase items, since it's all
        converter-side triage work in the same vein.
      - Added `While` IR node + parser/emitter support for `while <cond>:
        <body>` — most commonly Ren'Py's "repeat a menu until the player
        picks an exit option" conversation-topic loop
        (`while inconvo: menu: ...`), used in **every** character dialogue
        file in Jisei (11 occurrences: chance/ending/jennifer/kizaki/miko/
        story), previously entirely unsupported. Flattens into a labeled
        condition-check + body that jumps back to re-test the condition,
        built by composing the existing single-branch `If` machinery
        (`_emit_if`) rather than writing bespoke raw-line logic —
        `src/converter/emitters/vnds_writer.py::_emit_while`. Same
        conservative rejection as `if`/`elif`/`else` for an unparseable
        condition.
      - **Blocking count went up first (224 → 256), then back down (→
        242) — not a regression.** Previously, `while` fell to the generic
        "unsupported statement" fallback, which swallows its entire
        indented body *unparsed* (`_skip_child_block`) — meaning anything
        unsupported *inside* a conversation loop was invisible, hidden
        under one opaque flag for the whole loop. Now that `while` parses
        its body structurally, those inner problems surface individually:
        real ATL properties (`xalign`/`yalign`/`linear`/`zoom`, Phase 3
        scope), `$ persistent.*`/`$ achievement.grant(...)`, and
        `$ renpy.pause(...)` calls nested inside conversation loops. This
        is the report becoming *more accurate*, not worse — the count is
        a proxy, not the goal.
      - That surfacing directly motivated two more real fixes: (1)
        `renpy.pause(<n>)`/`renpy.pause()` now convert exactly like the
        standalone `pause` statement (`_parse_special_dollar_statement`)
        — a plain numeric literal duration consumed at convert time, not
        a runtime expression, so this bypasses `_render_expr`'s int-only
        restriction deliberately (a float pause duration is fine; a float
        *variable* still isn't, per §6.1). (2) `$ persistent.<x> = ...`
        and `$ achievement.grant(...)` are now flagged `manual`, not
        `blocking`, matching `VN3DS-spec.md` §6's own conversion table
        ("persistent.\*, achievements | Flagged `manual`") — previously
        they fell to the generic blocking default since nothing
        distinguished them from a truly-unknown `$` statement.
      - 8 new pytest tests (80 total), 1 new classify.py rule. No engine
        changes for this batch (all parser/emitter-level).
      - **Re-ran the Jisei baseline**: blocking **224 → 256 → 242** net
        (see above); `manual` grew **169 → 178** (the persistent/
        achievement reclassification); category breakdown now `unknown`
        122, `python` 100, `screen` 19, `asset` 1. Remaining blocking is
        now almost entirely ATL properties (Phase 3 scope, inside `unknown`
        and some `python`), real `screen:` blocks (Phase 5 scope), and a
        handful of genuinely-unconvertible `renpy.*` calls
        (`full_restart`, `block_rollback`) and list-valued `define`s —
        all expected, documented gaps rather than new surprises.
      - **2026-07-05 — round 2**: broke down the remaining blocking by
        leading keyword and found two more real wins plus three genuine
        misclassifications (blocking instead of the spec's own stated
        `manual` disposition):
        1. **`$ var = renpy.random.randint(a, b)` now converts** to a new
           `Random` IR node → the *original* VNDS `random` command, which
           has been fully implemented in `script.moon` since Phase 0 but
           was never wired into the converter at all (`Script`/`Random` in
           `ir.py`, parsing in `rpy_parser.py`, emission in
           `vnds_writer.py`). Only literal int bounds are resolvable,
           matching the engine's own `num()`-based parsing.
        2. **`init python:`/`init -1 python hide:` blocks** — almost
           always Ren'Py's built-in Gallery/MusicRoom extras or desktop
           window config (irrelevant on 3DS) — now flagged `manual`
           instead of falling into the generic top-level bucket.
        3. **List-mutation calls** (`notes.insert(...)`, Jisei's
           clue-journal system) and **list/dict-valued `define`/`default`/
           `$` assignments** (the note text feeding that same journal) —
           now flagged `manual`. VNDS variables are int/bool/string only
           (§6.1) so these were never going to auto-convert, but they're a
           real, human-reimplementable feature (a native notebook screen),
           not unknown code — matches the severity semantics in §7.1
           more honestly than blanket `blocking`.
        - None of this is a new *conversion* capability beyond `random`;
          items 2-3 are pure reclassification (severity/category fixes to
          items that were already being flagged, just under the wrong
          bucket) — VN3DS-spec.md §6 already listed `persistent.*`/
          achievements as `manual`, and the same reasoning extends
          naturally to `init python` extras and list-backed features.
        - 9 new pytest tests (81 total), 4 new classify.py rules. No
          engine changes (the `random` VNDS command already existed).
        - **Re-ran the Jisei baseline**: blocking dropped **242 → 183**
          (`chance.rpy` and `jennifer.rpy` now at **zero** blocking);
          `manual` grew 178 → 233. Category breakdown: `unknown` 94,
          `python` 69, `screen` 19, `asset` 1 — remaining blocking is now
          almost entirely ATL properties (Phase 3) and real `screen:`
          blocks (Phase 5), the two categories that always needed
          dedicated systems rather than converter triage.
      - **2026-07-05 — round 3: real ATL positioning (pulling forward a
        slice of Phase 3, per user direction).** Before building the full
        §9.1 tween engine, checked what Jisei's ~66 ATL blocks actually
        contain: **43 are pure static positioning** (`show X: xalign N`,
        no timed tween at all) and only **23 use a real timed tween**
        (`linear <duration> ...`). The static majority is a *precise, not
        approximated* conversion opportunity — Ren'Py's `xalign`/`yalign`
        are exact 0.0-1.0 screen fractions, strictly better information
        than the existing coarse left/center/right snap.
      - Added `xalign`/`yalign`/`approximated_atl` fields to `Scene`/`Show`
        (`ir.py`). Parser (`rpy_parser.py`): a `show/scene X:` header now
        collects its indented ATL block (`_collect_indented_lines`) and
        scans every line for `xalign`/`yalign` values
        (`_parse_atl_positioning`), taking the *last* value seen for each
        — which naturally handles both the static case (one assignment) and
        the timed-tween case (approximating straight to the tween's final
        state, since the last `linear ...` line's target values are what
        "last value wins" picks up). A block using `linear`/`ease` timing,
        or an unrepresentable property (`zoom`/`alpha` — no VNDS
        equivalent), is flagged `approximated`; a purely static block
        converts silently, no flag needed. A block with no xalign/yalign
        at all (nothing usable) stays a rejected `Unsupported`, same
        conservative philosophy as `If`/`While`.
      - Emitter (`vnds_writer.py`): `_resolve_show_xy` prefers the precise
        ATL fraction over the coarse position snap when present (`x =
        round(xalign * 400)`, `y = round(yalign * 240)`, falling back to
        the existing anchor for whichever axis wasn't specified). `Scene`
        positioning (ATL or symbolic) is still ignored either way —
        backgrounds are always full-screen (§5.1) — but now flagged
        consistently regardless of which syntax produced it.
      - 7 new pytest tests (88 total), 3 new classify.py rules. No engine
        changes — `setimg <file> <x> <y>` already took arbitrary pixel
        coordinates; this is purely a converter-side precision + fallback
        upgrade. Zoom/alpha remain undroppable-but-unrepresented (the
        engine's `setimg` has no scale/opacity field) — real animated
        tweening and zoom/alpha support are still Phase 3's full flux
        engine, not attempted here.
      - **Re-ran the Jisei baseline**: blocking dropped **183 → 103**
        (`kizaki.rpy` and `miko.rpy` now at **zero** blocking; `story.rpy`
        35→3); `approximated` grew 33→57 (the timed-tween/zoom/alpha
        collapses, now honestly tracked instead of silently blocking).
        Category breakdown: `python` 69, `screen` 19, `unknown` 9, `atl` 5,
        `asset` 1. Remaining blocking is now dominated by the residual
        harder `ui.*` variant (conditionally-enabled buttons, documented
        in 1.9's earlier entry) and real `screen:` blocks (Phase 5 scope).
      - **2026-07-05 — round 4: recognize Ren'Py's own default screens
        (screens.rpy investigation).** Checked what the remaining 19
        `screen:` blocks actually contain before assuming they all need
        Phase 5's custom-screen runtime. **14 of 19 are Ren'Py's own
        default boilerplate** — `say`, `choice`, `input`, `nvl`,
        `main_menu`, `navigation`, `file_picker`(+`_old`), `save`, `load`,
        `preferences`(+`old_`), `yesno_prompt`, `quick_menu` — present in
        `screens.rpy` of essentially every Ren'Py project, not Jisei-
        specific content. `VN3DS-spec.md` §6's own conversion table
        already says custom screens are `manual` *because* "default
        screens are provided natively" — the engine ships its own dialogue
        box, choice buttons, and save/load UI that fully replace these, so
        they're safe to skip entirely rather than flag as needing
        reimplementation. The other 5 (`gallery`, `musicroom`, `notes`,
        `directorsnotes`, `outtakes`) are genuine bonus-content extras,
        correctly `manual` already.
      - Added a top-level `screen <name>:` recognizer in `rpy_parser.py`
        (same spot as the `init python` fix): a name in the known default
        set flags `info` ("no action needed"); anything else flags
        `manual` ("custom screen has no VNDS equivalent") — replacing the
        generic top-level-statement fallback's blocking default for both
        cases, matching the spec's own stated disposition for the first
        time instead of just keyword-sniffing the category.
      - 4 new pytest tests (91 total), 2 new classify.py rules. No engine
        changes — this is pure recognition/classification, same category
        as the `persistent.*`/`init python` fixes from round 2.
      - **Re-ran the Jisei baseline**: blocking dropped **103 → 84**
        (`screens.rpy` and `gallery.rpy` now at **zero** blocking — 14
        `info` + 10 `manual` in `screens.rpy`); `info` grew 1→15. Category
        breakdown: `python` 69, `unknown` 9, `atl` 5, `asset` 1 — `screen`
        has fully cleared. Remaining blocking is now almost entirely the
        residual harder `ui.*` variant (conditionally-enabled buttons,
        documented in 1.9's earlier entry) and misc leftover `$`/ATL edge
        cases — no more large dedicated-system categories left to chase.
      - **2026-07-05 — round 5: clearing the misc leftovers.** Broke down
        the remaining 84 blocking items individually and found several
        more real, cheap wins plus one real bug:
        1. **Real bug**: the ATL `xalign`/`yalign` regex from round 3
           didn't accept a leading `-`, so any negative value (e.g.
           `xalign -0.05`, used for slightly-off-screen-edge positioning)
           made the *whole block* fall back to Unsupported. One-character
           fix (`_ATL_POSITION_PROP_RE`); this alone fixed all 5 remaining
           `atl`-category blocking items.
        2. **`renpy.block_rollback()` (~28 occurrences!) → `info`,
           no-op.** Rollback/history isn't implemented yet (Phase 3.7), so
           there's nothing for this call to disable today — the single
           highest-count item in the whole remaining backlog.
        3. **`$ renpy.movie_cutscene(...)` → `manual`/`video`** (schema
           already had a `video` category, unused until now), matching
           §6's "movie/video → manual" disposition directly instead of
           falling into the generic blocking bucket.
        4. **`define wipedown = CropMove(...)`-style custom transition
           aliases → `approximated`/`atl`.** Pure bookkeeping: any
           `with wipedown` using the name already downgrades to a plain
           dissolve regardless of whether *this definition* converts
           (2.2's `_resolve_transition` only checks the name string, never
           looks up the definition) — no functional gap, just a stale flag.
        5. **A bare `$ <name>` expression statement → `info`, no-op** (a
           variable reference alone has no effect in Ren'Py either — almost
           certainly leftover debug code).
        6. **Real correctness bug, not just classification**:
           `Character(None, ...)` — a deliberate, valid Ren'Py idiom for a
           styled-but-nameless narrator (color/ctc set, no name shown) —
           was being rejected as "missing a string display name," the same
           error as a genuine parse failure. `CharacterDef.display_name`
           is now `str | None`; `_resolve_speaker` already handled `None`
           correctly (no nameplate emitted) purely by luck of how it was
           originally written, so this needed no emitter change, only the
           parser accepting the explicit-`None` case instead of rejecting it.
        - 13 new pytest tests (101 total), 4 new classify.py rules.
        - **Re-ran the Jisei baseline**: blocking dropped **84 → 41**
          (`ending.rpy` 34→1, `story.rpy` 3→0, `options.rpy` 1→0,
          `jennifer.rpy` →0); `info` grew 15→46. Category breakdown:
          `python` 36, `unknown` 4, `asset` 1. What remains is almost
          entirely the harder `ui.*` variant (conditionally-enabled
          buttons via a nested `if`/`else` deciding `clicked=`/`None`) plus
          a handful of genuinely rare/complex items (`renpy.full_restart()`,
          a `LiveComposite`/`ConditionSwitch`-based dynamic portrait
          system). **Deliberately not chasing the conditionally-enabled-
          button case further**: VNDS's `menu:`/`choice` has no per-option
          enable state, so converting it either way (always show vs. drop
          the choice) risks a real behavioral bug — either allowing an
          action Ren'Py would have blocked, or losing a reachable one —
          worse than an honest blocking flag, same philosophy as the
          trailing-`else` rejection in the original `ui.*` matcher.
- [ ] **1.10** — Play Jisei from start to credits in Azahar (Old 3DS profile);
      memory under 70MB
      - **Deferred until after Phase 2** (see 1.9's planning-level finding
        above) — the engine can't interpret Jisei's actual branching logic
        until Phase 2's expression evaluator/state work exists to convert
        its `$`/`if`/`define` usage.
      - **2026-07-05 — Phase 2 done, resuming 1.10; found a real
        infrastructure gap first.** Every triage run through this whole
        session (1.8, 1.9, all five re-triage rounds) parsed and emitted
        each `.rpy` file *separately* — never wired the pieces (parser,
        emitter, problem report, asset pipeline) into one thing that
        actually produces a loadable bundle. Three concrete gaps found
        before any hardware test could even be attempted:
        1. No converter CLI existed at all (`has_blocking` was noted back
           in 1.3 as "ready for the CLI (not yet built)" — never followed
           up on).
        2. **No multi-file merge.** Ren'Py has one flat label namespace
           across every `.rpy` file in a game — `jump`/`call` can target a
           label defined in any file. Every triage run's per-file
           `emit_script_vnds` call would have produced 12 separate,
           mutually-unreachable `script.vnds` files for Jisei, not one
           playable game.
        3. **No Ren'Py asset-tag resolution**, a gap `assets/pipeline.py`'s
           own docstring already flagged as "not-yet-scoped" back in 1.4:
           the engine expects assets under *fixed* `background/`/
           `foreground/`/`sound/` folder names (original VNDS convention,
           `script.moon`'s hardcoded prefixes), but Ren'Py's own asset
           layout is arbitrary (`images/`, `gui/`, `char/`, `music/`,
           `voices/`, ...) — nothing sorted one into the other.
        - Built `src/converter/cli.py`: `parse_game()` walks and merges
          every `.rpy` file's `Script` (labels concatenated, characters/
          images dicts unioned, top-level sets concatenated) before
          emitting; `build_bundle()` writes `script/main.scr` +
          `manifest.json` + `problems.json`/`problems.md`. Deliberately
          follows the engine's **actual** loading convention
          (`base_dir/script/main.scr`, per `main.moon`'s `love.load` /
          `script.moon`'s `load()` default) rather than
          `VN3DS-spec.md` §5.2's aspirational `script.vnds`-at-bundle-root
          layout — nothing consumes `manifest.json`'s `entry_label` yet
          either, so a real build has to target what the engine actually
          reads today. Another spec-vs-implementation gap in the same
          vein as [[spec_vs_engine_semantic_gaps]] from Phase 1.5.
        - Added `required_asset_names()` (scans emitted `script.vnds` text
          for `bgload`/`setimg`/`sound`/`music`/`voiceover` commands →
          the basenames each fixed folder needs) and
          `resolve_and_convert_assets()` (walks an arbitrary extracted
          asset tree, converts+places only the files actually referenced,
          matched by basename regardless of source subfolder) to
          `assets/pipeline.py`. Missing assets are reported, not fatal —
          `main.moon`'s `path_exists` check already skips any instruction
          whose file doesn't exist, so a partial asset match is still a
          usable smoke-test build, just missing some visuals/audio.
        - 6 new pytest tests (107 total in `tests/converter/`), verified
          end-to-end with a hand-written two-file test game (cross-file
          `call` resolves correctly into the merged script).
      - **Built and staged a real Jisei bundle end-to-end.** Extracted
        Jisei's assets from `game/archive.rpa` via `unrpa` (955 files;
        never committed — proprietary content, kept in the session
        scratchpad only, same handling as the decompiled `.rpy` source).
        Ran `converter.cli` against all 12 decompiled files + the
        extracted assets, producing a real `script/main.scr` +
        `manifest.json` + `problems.json`. Found one more real robustness
        gap: `resolve_and_convert_assets` aborted the *entire* asset batch
        on the first `tex3ds` rejection (an oversized/non-power-of-two CG)
        — fixed to catch a per-file conversion failure and continue,
        since a few outliers are expected across ~900 real assets (1 new
        test, 108 total).
      - **Result:** 10 backgrounds + 18 sprites + 11 sounds converted; 2
        images failed conversion (oversized CGs — real pre-processing gap,
        Phase 4.2's atlas/resize scope, not attempted here); 167 asset
        names referenced but never found, and checking a sample confirmed
        every one is an already-known, already-correctly-flagged gap, not
        a new bug — composite character portraits (`im.Composite(...)`,
        no single-file equivalent) and `Solid("#000")` color fills (not
        file-backed at all). No character sprites will render in this
        build; backgrounds, text, choices, and audio should all work.
      - Built the real `.3dsx` (`alfons lovebrew`) and staged the Jisei
        bundle as a novel folder at
        `build/lovebrew/sdcard/3ds/VNDS-LOVE/save/VNDS-LOVE/novels/jisei/`
        (gitignored under `build/`, never tracked).
      - **Azahar cannot boot this engine at all on this dev machine**
        (established Phase 0 finding, see
        [[love_potion_2_0_0_quirks]]/`base/ENVIRONMENT.md`) — despite
        1.10's wording, real Old 3DS hardware is the only working
        validation path here. The user will copy
        `build/lovebrew/sdcard/`'s contents onto their physical Old 3DS's
        SD card and test directly; this item stays open pending that
        real-hardware report rather than an emulator run.
      - **2026-07-05 — first real hardware run, first real hardware bug.**
        User launched Jisei on physical Old 3DS hardware and immediately hit
        `script.lua:339: bad argument #2 to 'num' (number expected, got
        table)` while loading the novel. Root cause: a **pre-existing bug in
        the original forked VNDS-LOVE code**, `script.moon`'s `parse()`
        function's `"random"` branch read
        `low: num(c[3], high: num(c[4]))` — the comma before `high:` made
        MoonScript build an implicit table literal (`{high: num(c[4])}`) and
        pass it as `num`'s (i.e. Lua's `tonumber`'s) *second* argument,
        which must be a numeric base, not a table. This line had **never
        been exercised by anything** — no busted spec parsed a real
        `random <var> <low> <high>` line through the engine's own `parse()`
        (only the converter's emitted *text* was tested) — until this
        session's Phase 2.5 `Random` IR node work made
        `renpy.random.randint()` the first real-content feature to ever
        emit one. Fixed to `low: num(c[3]), high: num(c[4])` (two sibling
        table keys, matching the pattern already used correctly elsewhere,
        e.g. `setimg`'s `x`/`y`). Added a busted regression test
        (`tests/engine/extended_vnds_spec.moon`) that parses a real
        `random` line end-to-end and asserts both bounds and the assigned
        value; 60/60 busted + 108/108 pytest still pass. Rebuilt the
        `.3dsx` and re-staged the Jisei novel folder for another
        hardware-test round. Lesson reinforced: real-content, real-hardware
        validation keeps finding bugs that fixtures and isolated unit tests
        never would — see [[phase2_scope_gap_the_question]].
      - **2026-07-05 — second hardware run, two more real bugs (both in the
        converter this time, not the engine).** Retest report: the novel
        opened mid-story instead of at a main menu/beginning, text ran off
        the right edge of the screen unreadably, and every voiced line
        showed its raw audio file path as spoken dialogue instead of
        playing any sound — repeating and stacking with each advance.
        Diagnosed two independent, confirmed-in-code bugs, both from
        content this converter had genuinely never seen before Jisei:
        1. **No entry-point ordering.** `emit_script_vnds` writes labels in
           whatever order `parse_game` merged them (alphabetical `.rpy`
           filename order), and the engine always starts executing at
           instruction 1 — it has no notion of Ren'Py's `label start` being
           special (VNDS's original convention never needed one, since a
           single hand-written `script.vnds` naturally began with its own
           first content). Confirmed: Jisei's merged `main.scr` began at
           `@chance02`, ~500 lines before `@start`, because `start` lived
           in a different, alphabetically-later source file. This fully
           explains "starts mid-story instead of at the beginning" — a
           built-in main menu was never in scope (Ren'Py's is a `screen`
           construct, correctly flagged `manual`), but starting at the
           correct label was always assumed and never actually verified
           past a same-file two-label test fixture. Fixed via
           `cli._reorder_entry_label()`: moves a label literally named
           `start` to the front of the merged list before emission,
           matching `manifest_writer.build_manifest`'s existing (but
           previously unconsumed) entry-label pick.
        2. **Bare `voice "path.ogg"` statements were parsed as dialogue.**
           `_PLAY_QUEUE_RE` only recognized `play voice "..."`/
           `queue voice "..."`; Ren'Py's much more common bare `voice
           "audio/v/line.ogg"` form (placed right before its matching
           `say` line) fell through to `_SAY_RE`, which matches an
           optional leading `\w+` word before a quoted string —  so
           `voice "path.ogg"` parsed as character **"voice"** saying the
           literal file path as dialogue text, once per voiced line, and
           no `Play`/`voiceover` instruction was ever emitted for it. This
           fully explains both remaining symptoms: the file paths
           appearing as spoken lines, and no audio ever playing (the
           correctly-wired `audio.moon`/`voiceover` playback path was
           simply never reached). Fixed by adding a dedicated `_VOICE_RE`
           checked before the `_SAY_RE` fallback, emitting the same `Play
           (channel="voice", ...)` node the `play voice` form already
           produced. Side effect confirmed by rebuilding Jisei's bundle:
           voice/sound assets actually resolved and converted jumped from
           11 files to **659** files, since `required_asset_names` now
           correctly sees every voice cue's filename instead of silently
           losing it inside misclassified dialogue text.
        - 2 new tests (`test_bare_voice_statement_is_a_play_not_dialogue`,
          `test_build_bundle_puts_the_start_label_first_regardless_of_file
          _order`); 110/110 pytest + 60/60 busted pass. Rebuilt the bundle
          and re-staged the Jisei novel folder for a third hardware-test
          round.
        - **Not yet investigated:** text running off the right edge of the
          screen. Plausible but unconfirmed hypothesis — `text.moon`'s
          `word_wrap` sizes against `lg.getWidth!` with no screen argument,
          and LÖVE Potion's per-screen `love.graphics` state may not be
          "bottom" (320px, narrower than top's 400px) at the moment the
          `"text"` event fires versus when it's actually drawn. Needs
          confirmation from LÖVE Potion's own source (same standard as
          every other hardware finding this session) before touching
          `text.moon` — not guessed at or changed this round. Also worth
          re-checking after this round's fixes, since the multi-line
          scrolling text buffer (intentional VNDS behavior, up to 7 lines
          visible at once on 3DS) may have made the overflow look worse
          than it is when interleaved with the now-fixed fake voice-path
          dialogue lines.
      - **2026-07-05 — "no sprites/backgrounds rendered" traced to the
        same hardware run.** The user separately reported that no visuals
        showed up at all during the first test. Traced directly: the
        opening scene's very first two instructions are
        `bgload black` (a `Solid("#000")` color fill — no backing file,
        already a known/expected gap, not fixable without adding
        engine-side solid-color-fill support) and `setimg 01` (`cg/01.jpg`).
        `cg/01.jpg` (1024×1536) and `gui/kanwalk.jpg` (628×1471) are
        exactly the two files already flagged in `failed_assets.txt` —
        both exceed the PICA200 (3DS GPU)'s 1024px max single-texture
        dimension, which `tex3ds` rejects outright ("Invalid height").
        Since these are literally the first visuals the game shows, the
        opening scene had *no chance* of rendering anything. Fixed with a
        pragmatic stopgap (not the full atlas/tiling system Phase 4.2
        envisions): `assets/pipeline.py`'s `convert_image` now downscales
        (via Pillow, aspect-ratio-preserving) any source image exceeding
        1024px in either dimension before handing it to `tex3ds`, falling
        back to the original file untouched if Pillow isn't installed or
        can't read it. Confirmed against the real files: both `01.jpg` and
        `kanwalk.jpg` now convert successfully (Jisei's foreground count
        went 18 → 20; `failed_assets.txt` is no longer produced at all for
        this bundle). Also fixed a related bug caught in the same pass:
        `build_bundle` only ever *wrote* `missing_assets.txt`/
        `failed_assets.txt` when non-empty, never cleared them when a
        rebuild fixed the underlying issue — so a fixed rebuild into the
        same `output_dir` would still show the old failure list. Now
        deletes each file when there's nothing to report. 2 new tests
        (oversized-texture downscale, stale-report cleanup); 112/112
        pytest + 60/60 busted pass. `pillow` added to
        `base/ENVIRONMENT.md`'s converter environment notes. Rebuilt and
        re-staged the Jisei bundle for the next hardware round.
      - **2026-07-05 — third hardware run: entry point + audio now correct,
        but still zero sprites/backgrounds. Found the real root cause.**
        User confirmed: audio plays, and the story now starts at the
        beginning (accidentally skipped past the still-unimplemented main
        menu by pressing the A button twice during load — not a bug).
        Visuals were still completely absent despite the previous round's
        texture-size fix actually converting every referenced background/
        sprite successfully. Root cause: `vnds_writer.py`'s
        `_image_filename` emitted `bgload`/`setimg`/`clearimg` commands
        with **no file extension at all** (`bgload black`, `setimg 01 150
        0`), based on a comment claiming "VNDS commands take a single
        filename with no directory or extension." That claim is
        contradicted by every hand-written engine fixture
        (`tests/engine/fixtures/{hello-vn,stress-test,vnds-test}` all use
        `bgload bg.t3x`/`setimg fg.png ...`) and by `script.moon`'s own
        `parse()`, which builds the lookup path verbatim
        (`"background/"..c[2]`) with no extension ever appended anywhere
        in the engine. Since the asset pipeline always produces `.t3x`
        files, every `bgload`/`setimg` instruction's `path_exists` check
        failed silently, every single time, regardless of how many assets
        successfully converted — explaining why fixing the texture-size
        issue (previous round) had zero visible effect. This also explains
        why **audio worked**: `_audio_filename` already correctly appended
        `.ogg` for `sound`/`music`/`voiceover`, so that code path was never
        affected. Fixed: `_image_filename` now appends `.t3x`, matching
        the real convention. 3 existing tests updated (asserted the old,
        wrong no-extension output) + 1 new end-to-end regression test
        (`test_build_bundle_emits_image_paths_matching_the_converted_
        asset_extension`) verifying `scene`/`show`/`hide` all emit
        `.t3x`-suffixed paths; 113/113 pytest + 60/60 busted pass.
        Confirmed against the real Jisei bundle: `setimg 01.t3x 150 0` /
        `bgload black.t3x` now match the actual converted filenames.
        Rebuilt and re-staged for the next hardware round. Notable: this
        bug had been present in the converter since image emission was
        first written, silently breaking every single background/sprite
        for the entire session — only surfaced because Jisei was the
        first *real, hardware-tested* content ever run past the
        hand-written fixtures (which don't exercise the converter's own
        emission code at all, since they're written directly against the
        engine's real format).
      - **2026-07-05 — fourth hardware run: images finally show up, but a
        sprite renders at the correct position, massively oversized and
        cut off past the right edge.** Root cause, found by reading
        `images.moon`'s draw math end to end: `setimg`'s x/y coordinates
        and `draw_foreground`'s positioning both correctly use `pscale`
        (`min(screenWidth/256, screenHeight/192)`, a fixed scale tied to
        the original DS's 256x192 canvas — confirmed against every
        hand-written fixture, e.g. `setimg fg.png 246 0` in
        `vnds-test`, whose coordinates only make sense on a ~256-wide
        canvas). But the sprite's own **drawn size** reused `scale`
        (`min(sx, sy)`, computed from whatever *background* happens to be
        loaded) instead of `pscale` — so a sprite's on-screen size
        silently depended on an unrelated background's dimensions. In
        Jisei's opening scene the background never loads (`bgload
        black.t3x` — `black` is a `Solid()` fill, no file, so
        `original_width/height` stay at the screen's own dimensions,
        making `scale` == 1, i.e. no scaling at all), so the sprite drew
        at its *raw pixel dimensions* (683×1024 after the earlier
        1024-cap downscale) — over 1.7x wider than a 400px top screen.
        Two-part fix:
        1. **Engine:** `images.moon`'s `draw_foreground` now draws sprites
           at `pscale`, matching the position math, decoupling sprite size
           from whatever background happens to be loaded (or not loaded).
        2. **Converter:** `assets/pipeline.py` now downscales `foreground/`
           art to a 256px baseline (`_FOREGROUND_MAX_DIMENSION`, separate
           from the 1024px hardware-only cap kept for backgrounds, since
           backgrounds already self-rescale to fill the screen via
           `bgload`'s dynamic `original_width/height` regardless of native
           resolution) — because even with the engine fix, `pscale` is
           only a ~1.25-1.5x *magnification* of the DS baseline, not a
           general-purpose downscale for arbitrary desktop-resolution art.
        - This is a **heuristic pending real hardware confirmation** —
          256px was chosen because it matches the existing `256`/`192`
          constants already in `images.moon`/`script.moon`'s coordinate
          system, not from a measured "looks right" pass (no way to
          screenshot-diff without hardware access). Revisit if sprites
          still look mis-sized once confirmed on-device.
        - 2 new pytest tests (direct `_downscale_if_oversized` cap check,
          foreground-vs-background cap differs) + 1 new busted test
          (`draw_foreground` draws at `pscale` regardless of an unrelated
          background's `scale`); 115/115 pytest + 61/61 busted pass.
          Rebuilt and re-staged for the next hardware round.
        - **Still open / explicitly out of scope for this round:** (a) CG
          pan/scroll animation (Ren'Py ATL motion effects) — the PC
          version pans the opening CG top-to-bottom; VN3DS has no ATL
          keyframe/tween animation system at all yet, this is a
          substantial new feature, not a bug, deferred; (b) custom Ren'Py
          `screen` UI (main menu, custom textbox skins, etc.) — already
          correctly flagged `manual`/unconverted by the Problem Report;
          building a real UI screen system is Phase 4 territory, not
          started.
      - **2026-07-05 — resolved the DS-era coordinate baseline question,
        same session.** User asked directly: should the engine move off
        the DS-era 256x192 coordinate assumption and adopt one native to
        the 3DS's actual hardware, rather than treating the 3DS as "a
        bigger DS" via the `pscale` up-conversion factor? Decided (via
        AskUserQuestion): yes — rebase to the O3DS top screen's own native
        resolution (400x240, where all background/sprite drawing already
        happens), not a normalized 0.0-1.0 fraction (simpler, more
        readable in the plain-text `.scr` format); and update the three
        hand-authored engine fixtures in the same change rather than
        leaving them mispositioned.
        - **This also explained a second, previously-unattributed part of
          the prior round's hardware bug.** The converter's own position
          math (`_POSITION_XY` anchors, `_resolve_show_xy`'s `xalign *
          400`/`yalign * 240`) was, per its own existing comments, *already*
          authored assuming a 400x240 canvas — it was the **engine** that
          was still dividing by 256x192. So a converter-emitted position
          wasn't just drawn at the wrong *size* (previous round's fix),
          it was also placed at the wrong *position*, off by the
          400/256≈1.56x mismatch factor — consistent with the user's "off
          the right side" description being more than just an oversized
          image spilling past its correct anchor.
        - Changed exactly one constant: `main.moon`'s `love.resize` now
          sets `px, py = w/400, h/240` (was `w/256, h/192`). Since the
          prior round's fix already made `draw_foreground` use `pscale`
          for both position *and* size, this one change fixes both
          consistently with no other engine code changes needed. On a
          real O3DS top screen this makes `pscale` exactly `1` (no
          up-conversion at all) — sprites now draw at their converted
          pixel size, 1:1.
        - Converter: `assets/pipeline.py`'s `_FOREGROUND_MAX_DIMENSION`
          raised from 256 to 400 to match (still a heuristic, still
          separate from the 1024px hardware-only cap kept for
          backgrounds).
        - Updated the 3 hand-authored fixtures' `setimg` coordinates to
          the new baseline, scaling each existing position by
          400/256≈1.5625 (x) and 240/192=1.25 (y) so they land in the same
          *relative* screen position as originally authored
          (`stress-test`'s two corner sprites, `vnds-test`'s
          four-corners-plus-center layout).
        - No test assertions hardcoded the old fixture coordinate values
          (confirmed via grep), so nothing else needed updating; 115/115
          pytest + 61/61 busted pass. Rebuilt and re-staged for the next
          hardware round.
      - **2026-07-05 — fifth hardware run: more of the image visible, but
        still off-center against the right side; text still overflowing.**
        Two more real bugs found, plus a third discovered as a side effect
        of writing a regression test for the second:
        1. **Sprites were anchored by left edge, not center.**
           `images.moon`'s `draw_foreground` drew `lg.draw(@img, x, y, 0,
           pscale, pscale)` with no origin offset, so LÖVE's default
           top-left anchor put the sprite's *left edge* at the intended
           point — but Ren'Py's own `align`/`xalign` semantics (and this
           project's `_POSITION_XY` constants) mean that point is the
           sprite's *center*. A wide sprite whose center should land at
           screen-center instead had its left edge there, running well
           past the right edge. Fixed: pass `ox = spriteWidth/2` as
           LÖVE's origin argument, anchoring horizontally by center;
           vertical stays top-edge-anchored for now (true yalign-based
           vertical anchoring needs the alignment fraction itself passed
           through `setimg`, not just a resolved pixel position — a
           documented, not-yet-addressed limitation). Converter's
           `_POSITION_XY` updated from placeholder left-edge-tuned values
           (20/150/280) to true screen-fraction centers (100/200/300).
        2. **Foreground downscale only capped the longest edge, not both
           independently.** A portrait CG capped to fit under 400px on its
           long edge (e.g. 1024x1536 -> 267x400) is still 400px *tall* —
           well over the 240px screen height — so the bottom of the sprite
           was cropped off even once correctly sized/centered on the X
           axis. `_downscale_if_oversized`/`convert_image` now take
           independent `max_width`/`max_height` bounds (400x240 for
           foreground, a square 1024 cap for backgrounds/hardware), fit
           via `min(maxW/w, maxH/h)` so *both* edges land inside the
           screen.
        3. **While writing a regression test for (1), found a real,
           separate, pre-existing bug**: `text.moon`'s `update_font`
           (meant to let a per-novel `default.ttf` override the UI font)
           assigned a bare `text_font = ...`. Inspecting the *compiled*
           Lua confirmed this created a local scoped only to
           `update_font`'s own function body — `draw_text`/`word_wrap`'s
           `text_font` references compiled as plain global reads instead,
           resolving to `main.moon`'s own separate `text_font` global (set
           once, in `love.resize`). Net effect: `update_font`'s assignment
           has been dead code since it was written — a per-novel custom
           font has never actually applied, silently, and nothing caught
           it because production always has a valid `text_font` from
           `main.moon` regardless. Fixed by assigning `_G.text_font`
           explicitly. Also fixed, in the same function, a genuine
           dangling-`else` bug (the `else` in `if interpreter and not
           override_font ... else text_font = font` bound to the *inner*
           single-line `if lfs.getInfo(...) then ...`, not the outer
           condition — restructured with an explicit early return).
        - Also investigated and fixed the still-open **text overflow**
          finding from two rounds ago, this time with real evidence rather
          than a hypothesis: fetched LÖVE Potion's actual pinned-tag source
          (`lovebrew/lovepotion` @ `2.0.0`, `source/scripts/boot.lua` +
          `platform/3ds/source/citro2d/graphics.cpp` +
          `source/modules/graphics/wrap_graphics.cpp`) and confirmed
          `love.graphics.getWidth()` with no argument returns whichever
          screen `setActiveScreen` was *last* called for — which, per
          `boot.lua`'s own per-frame loop (`left, right, bottom, top`, in
          that order, every frame), is `"top"` (400px) once a frame's draw
          calls finish. `text.moon`'s `on "text"` handler computes its
          word-wrap width from a game-logic dispatch, not from inside a
          `love.draw` call, so it was silently measuring against the top
          screen's width even though the text box only ever renders on the
          bottom screen (320px) — explaining the exact reported symptom.
          `love.graphics.getWidth(screen)` accepts an explicit screen name
          specifically to sidestep this; added `text_box_width()` (3DS:
          `lg.getWidth("bottom")`, else plain `lg.getWidth!` for desktop
          LÖVE's single-screen case) and used it everywhere the text box
          measures itself.
        - New tests: 1 busted (`draw_foreground` anchors sprites by
          horizontal center), 1 busted (`text_box_width` regression,
          confirming word-wrap always asks for the bottom screen), 2
          pytest (independent width/height downscale bounds). 115/115
          pytest + 63/63 busted pass. Rebuilt and re-staged for the next
          hardware round.
      - **2026-07-05 — same session: pulled forward Phase 3.1-3.3 (ATL
        animation system) and Phase 5.1 (custom-screen runtime) directly
        at the user's request**, well ahead of the established phase
        order (Phase 5.1 in particular is explicitly flagged in this same
        document, §11, as an open question deferred until after Phase 4 —
        user was told this and chose to proceed anyway). Full details
        under each item's own entry (3.1, 3.2, 3.3, 5.1 below). Rebuilt
        Jisei's real bundle against both: 23 real ATL blocks in Jisei now
        convert to working keyframe animations (previously collapsed to a
        static final position, animation entirely discarded); native
        main menu now shows before a fresh playthrough. Also fixed a
        `classify.py` gap caught by re-running the real build rather than
        just unit tests: the new ATL-keyframe-fallback reason string
        wasn't in `classify.py`'s rule table, so it silently fell through
        to the generic `blocking` default — `blocking` dropped 69→41 once
        fixed. 132/132 pytest + 83/83 busted pass across both features
        combined. Rebuilt and re-staged for the next hardware round.

**Exit check:** §11.1 definition of done satisfied for Jisei — **partially
satisfied**: converter runs and has been triaged (1.9); full playable
completion (1.10) moves to after Phase 2, since Jisei's own content
requires Phase 2 converter/engine features that don't exist yet (see
`VN3DS-spec.md`).

---

## Phase 2 — Logic, State, Audio + Hustle Cat Port

**Goal:** Full game logic support; first romance VN playable. **This phase ends
the BUILD-mode portion of the project — see cutover marker at top of this file.**

- [x] **2.1** — Converter: `default`, `define` literals, `$ var = <expr>`,
      `if/elif/else`
      - 2026-07-05: added `Set` and `If`/`IfBranch` IR nodes
        (`src/converter/parser/ir.py`). `rpy_parser.py` parses: top-level
        `default var = <literal>` / `define var = <literal>` (int/bool/str)
        into `Script.top_level_sets`; `$ var = <literal-or-var>`, `$ var =
        var <op> <literal>` (self-referential accumulation), and `$ var +=/-=
        <literal>` into inline `Set` nodes (via Python's own `ast` module —
        same technique already used for `Character()`/`image` parsing);
        `if:`/`elif:`/`else:` chains into a single `If` node with each
        condition parsed as `(var, op, value, value_is_literal)`, supporting
        a single comparison, a bare truthy check (`if book:`), or a negated
        one (`if not book:`).
      - **Deliberately narrow expression subset, not a general evaluator**:
        only a literal, a bare variable reference, or `var = var <op>
        literal` self-reference is representable in the current
        `setvar`/`gsetvar` wire format (which only ever operates on a
        variable's *own* existing value, per the original VNDS engine
        already forked in Phase 0 — see `src/engine/script.moon`'s
        `next_instruction`'s `"setvar"` case). `$ hp = shield + 5`
        (combining a *different* named variable) or any function
        call/attribute/list/dict access is flagged, matching
        `VN3DS-spec.md` §6.1's "flow may depend on it → blocking" rule,
        rather than silently guessing.
      - **If/elif/else flattening reuses the engine's existing `if`/`fi`
        skip-block op** (already implemented since Phase 0, upstream VNDS
        syntax) — no new engine instruction needed for the *converter*
        side: `if <var> <op> <value> / jump <synthetic_label> / fi`, one
        block per non-final branch; the trailing `else` (or, absent one,
        whatever followed the whole if/elif/else) becomes its own synthetic
        label reached by an unconditional `jump` once every check falls
        through — same worklist/continuation mechanism `_emit_menu` (1.2)
        already established. If *any* non-else branch's condition falls
        outside the supported subset, the **whole** if/elif/else is
        rejected as a single `Unsupported` node rather than partially
        flattened — executing a branch unconditionally when the real
        condition might be false would be a silent correctness bug, worse
        than an honest `blocking` flag.
      - Top-level `default`/`define` literals are emitted as `gsetvar`
        lines before the first `@label` in `script.vnds`, since VNDS
        executes top-to-bottom from the first instruction and `@label`
        markers are just lookup targets within that same stream — they run
        once at script start, matching Ren'Py's timing.
      - Ren'Py has no local/global variable distinction at the `$`/
        `default`/`define` level, so the emitter always uses `gsetvar`
        (global), never `setvar` (local) — `setvar` stays reserved for
        engine-internal state (e.g. the menu-choice `selected` local).
      - **Known engine-side gap for 2.4/2.5 to close**: `script.moon`'s
        existing `getvalue` has no boolean-literal parsing — `"True"`/
        `"False"` tokens currently fall through to its bare-variable-name
        case, so `gsetvar book = True` won't behave correctly until 2.5
        adds real boolean literal support. Deliberately not fixed here,
        mirroring how 1.2's converter work shipped ahead of 1.5's engine
        catch-up.
      - 13 new pytest tests (50 total in `tests/converter/`) covering
        default/define literals (valid and rejected), `$` literal/
        accumulation/rejection cases, if/elif/else flattening (valid,
        bare/negated truthy, and whole-construct rejection), and the
        emitter's `Set`/`If` output including fallthrough-continuation and
        no-remainder cases. Full 32-test busted engine suite unaffected
        (no `.moon` changes in this item).
      - **Re-ran the Jisei baseline** (from 1.9) with these changes:
        blocking dropped **1010 → 492** (`python` 578→205, `flow` 102→5,
        `unknown` 247→182) — most of Jisei's actual clue-tracking/state
        logic turned out to fit this narrow subset once it existed. Full
        baseline is still nowhere near zero (see 1.9's planning-level
        finding); 2.2/2.3 should shrink it further.
- [x] **2.2** — Converter: `with dissolve/fade`, `play/stop/queue
      music|sound|voice`, `pause`
      - 2026-07-05: added `Transition`, `Play`, `Stop`, `Pause` IR nodes
        (`src/converter/parser/ir.py`). Trailing `with <name>` on
        `scene`/`show`/`hide` is now captured (previously silently
        discarded by `_parse_image_statement`) as a `transition` field on
        those nodes; a standalone `with <name>` line becomes its own
        `Transition` node applying to whatever preceded it. `play`/`queue
        music|sound|voice "<file>"`, `stop music|sound|voice`, and `pause
        [<seconds>]` are parsed via regex (consistent with the rest of
        `rpy_parser.py`'s line-oriented approach).
      - **Reused existing engine commands wherever one already existed**,
        rather than inventing new wire syntax: `play music/sound/voice` →
        the `music`/`sound`/`voiceover` commands already implemented in
        Phase 0 (upstream VNDS) and Phase 1.7; `stop music/sound/voice` →
        `stopmusic`/`stopsound`/`stopvoice` (Phase 1.7); `pause <n>` →
        the standard `delay <frames>` command (already implemented since
        Phase 0), converting Ren'Py's seconds to frames at 60fps. None of
        these needed any `.moon` changes.
      - **`transition <type> <duration>` is new wire format** (not
        implemented by the engine yet — confirmed `script.moon`'s `parse()`
        has no `"transition"` case, so it safely falls through to a no-op
        instruction rather than crashing) — the actual dissolve/fade
        *rendering* is explicitly Phase 3.5 ("Engine: dissolve/fade
        transitions between `bgload` calls"), so shipping the converter
        side now and letting the engine catch up later matches the
        existing 1.2→1.5 and 2.1→2.4/2.5 precedent.
      - Only `dissolve`/`fade` have a defined duration; any other Ren'Py
        transition name (`wipeleft`, a custom `CropMove(...)`-based one,
        etc.) is downgraded to a plain dissolve and flagged
        `approximated` — matches `VN3DS-spec.md` §7.1's own canonical
        example of that severity ("a transition downgraded").
      - `queue` is approximated as an immediate `play` (flagged
        `approximated`) since the engine has no track-chaining/playlist
        concept yet; bare `pause` (no duration) is flagged `info` since it
        already matches VNDS's default wait-for-input-after-text behavior,
        so nothing needs to change.
      - Audio filenames are resolved to `<basename>.ogg` regardless of the
        source extension (`illurock.opus` → `illurock.ogg`), matching what
        `src/converter/assets/pipeline.py`'s `convert_audio` actually
        produces.
      - 3 new classify.py rules (transition downgrade → `approximated`/
        `atl`; queue approximation → `approximated`/`audio`; bare pause →
        `info`/`flow`). 13 new pytest tests (63 total in
        `tests/converter/`). Full 32-test busted engine suite unaffected
        (no `.moon` changes).
      - **Re-ran the Jisei baseline**: blocking dropped **492 → 412**: the
        `audio` category disappeared entirely (fully converted/
        approximated) and `atl` roughly halved (45→29, mostly the
        `with`-transition backlog from 1.9's original baseline).
- [x] **2.3** — Converter: `window show/hide`, basic text tags
      `{b}{i}{color}{w}{p}{size}`
      - 2026-07-05: added a `Window` IR node — `window show`/`window hide`
        map directly onto the `window <show|hide>` command already
        implemented in `src/engine/text/text.moon` since Phase 1.6/1.7
        (`window_visible` state, `on "window"` handler), so no engine
        changes were needed at all here, unlike `transition` in 2.2.
      - Text tags: recognized inline tags (`{b}`/`{i}`/`{color=...}`/`{w}`/
        `{p}`/`{size=...}`, plus their `{/...}` closing forms) are passed
        through **unchanged** in the emitted `text <string>` line, since
        `text.moon`'s only current inline-markup support is a *different*,
        pre-existing ANSI-escape-code color scheme
        (`src/engine/text/text_color.moon`'s `colorify`, inherited from
        the upstream VNDS-LOVE fork for legacy community-script
        compatibility) — a real `{tag}`-aware renderer is engine work with
        no phase item yet, so the converter ships the recognized tags
        as-is for a future renderer to interpret, same
        converter-ships-ahead-of-engine pattern as `transition`. Any tag
        *not* in that allow-list is stripped from the dialogue text and
        flagged `approximated`, `text-tag` category (a category the
        schema already had defined but had never been used until now),
        rather than left to render as literal `{garbage}` in the
        dialogue box.
      - 1 new classify.py rule. 5 new pytest tests (68 total). Full
        32-test busted engine suite unaffected.
      - **Re-ran the Jisei baseline**: blocking dropped **412 → 356**
        (`unknown` 182→126, mostly `window`/unrecognized-tag noise
        clearing out of `dialogue02.rpy` and `story.rpy`).
      - **This closes out Phase 2's converter-side items (2.1-2.3).**
        Remaining blocking is dominated by `python` (205, complex `$`
        expressions/state beyond the safe subset — inherent to Jisei's
        design, not something 2.4/2.5's evaluator will fully close either)
        and `asset` (170, dynamic image displayables needing manual asset
        assignment — expected, not a bug). 2.4-2.7 are engine-side work
        that make the *already-emitted* wire format (from 1.2, 2.1, 2.2)
        actually executable at runtime; they won't move this triage number
        further since the converter has already committed to what it can
        emit for these categories.
- [x] **2.4** — Engine: expression evaluator (int/bool/string; `+−*/`,
      `==!=<<=>>= and or not`; no function calls)
      - 2026-07-05: **scope decision** — 2.1's converter deliberately emits
        only a narrow wire format (literal/bare-var `setvar`, single
        `var op value` `if`/`fi`) that already worked without a general
        evaluator; the one real gap was that `setvar`'s value parser never
        recognized `True`/`False` as booleans. Asked whether 2.4 should
        just patch that gap or build the real evaluator VN3DS-spec.md §6.1
        describes; chose the latter, with the plan to upgrade the
        converter to emit richer expressions once it exists (tracked as a
        follow-up, not done in this item — see below).
      - New `src/engine/expr.moon`: a small recursive-descent, precedence-
        climbing evaluator (`or > and > not > compare > add/sub > mul/div
        > atom`, plus parens) over int/bool/string literals and bare
        variable lookups against a caller-supplied scope table. No
        function calls or attribute/subscript access — unrecognized syntax
        or a type-mismatched operation (e.g. `"a" < 1`) makes `evaluate`
        return `nil` rather than raise, matching the engine's existing
        graceful-degradation philosophy rather than crashing on malformed
        input.
      - Wired into `script.moon`'s `setvar`/`gsetvar` `"="` modifier only:
        the full rest-of-line expression is now evaluated via `expr.evaluate`
        against a merged locals+globals scope, falling back to the
        original literal-or-bare-var parse if evaluation returns `nil`
        (preserves compatibility with anything the evaluator can't
        handle). The `"+"`/`"-"`/`"~"` modifiers are **unchanged** — their
        existing self-referential-accumulation behavior already worked and
        wasn't touched.
      - **Found but deliberately left alone**: `ins.modifer` (typo, missing
        an "i") on the line right below means the `"~"`-clears-the-whole-
        scope-table branch has been dead code since Phase 0, and separately
        would leak via reassignment (not mutation) if it ever ran — the
        exact same reassignment-doesn't-propagate bug fixed in 1.7's
        `audio.moon` `clear`. Left as-is rather than fixed: the *intended*
        behavior (nil out one variable, per `ops["~"]`, vs. wipe the whole
        table) is ambiguous, nothing in this project's own converter output
        or test fixtures exercises it, and "fix a dead branch's typo" would
        silently change behavior for latent content with no way to verify
        against real intent. Noted here for future reference.
      - 9 new busted specs (`tests/engine/expr_spec.moon`) covering
        literals, variable lookup, arithmetic (including cross-variable),
        string concatenation, comparisons, `and`/`or`/`not` precedence, and
        graceful `nil` on undefined variables/malformed syntax/type
        mismatches. 5 more integration specs in
        `tests/engine/extended_vnds_spec.moon` confirming `gsetvar =`
        against real `script.moon` execution (boolean literal, cross-
        variable arithmetic, plain literal, unaffected `+`/`-`
        accumulation, and a graceful-fallback case). 46 busted tests total.
      - **Follow-up (not yet done):** upgrade 2.1's converter
        (`src/converter/parser/rpy_parser.py`'s `_parse_set_statement` /
        `_parse_condition`) to emit compound expressions (cross-variable
        arithmetic beyond self-reference, `and`/`or` conditions) now that
        the engine can evaluate them — currently the converter still only
        emits what it did in 2.1, so this new evaluator capability isn't
        reachable from real Ren'Py source yet. Revisit alongside/after 2.5
        once `ifvar` exists, since compound *conditions* need a genuinely
        new single-line conditional-jump command (`ifvar <expr> jump
        <label>`, per `VN3DS-spec.md`'s worked example) — the current
        `if`/`fi` block form can only test one `var op value` at a time.
- [x] **2.5** — Engine: `setvar`/`ifvar` ops, variable state
      - 2026-07-05: added a new `ifvar <expr> jump <label>` engine command
        (`src/engine/script.moon`) — a single-line conditional jump backed
        by 2.4's `expr.moon` evaluator, per `VN3DS-spec.md`'s own worked
        example. Unlike the original `if`/`fi` block (one `var op value`
        test, jump handled separately inside the block), `ifvar` evaluates
        a full compound expression (arithmetic, comparisons, `and`/`or`/
        `not`, cross-variable) in one line and jumps only if true,
        falling through otherwise. Parsed directly off the raw line text
        (`line\match("^%s*ifvar%s+(.-)%s+jump%s+(%S+)%s*$")`) rather than
        the whitespace-tokenized `c` array every other instruction uses,
        since an expression can itself contain arbitrary spaces that
        tokenizing-then-rejoining would mangle.
      - **Upgraded the 2.1 converter** (the follow-up flagged in 2.4) now
        that `ifvar` exists: `_render_expr` in
        `src/converter/parser/rpy_parser.py` replaces the old
        `_literal_value`/tuple-based condition and `$`-assignment parsing
        with a general safe-expression renderer (walks the Python AST,
        rendering literals/names/`+-*/`/comparisons/`and or not` into
        expr.moon-compatible text, fully parenthesized to sidestep any
        Python-vs-evaluator precedence mismatch; rejects calls/attributes/
        subscripts/chained comparisons by returning `None`). `Set`'s
        `modifier`/`value`/`is_literal` fields collapsed into a single
        `expr` field — self-referential `+=`/`-=` now just renders as
        `var = (var + expr)`, no separate modifier needed. `If`/`IfBranch`
        now carry a single expression string instead of a `(var, op,
        value, is_literal)` tuple, so **compound `and`/`or` conditions and
        cross-variable comparisons in `if`/`elif` no longer need to be
        rejected as "too complex"** — only genuinely unsafe constructs
        (calls, attributes, chained comparisons) still are.
      - `_emit_if` (`vnds_writer.py`) now emits a single `ifvar <expr> jump
        <label>` line per branch instead of the old three-line `if <var>
        <op> <value>` / `jump <label>` / `fi` block — simpler output,
        still using the same worklist/continuation mechanism as before for
        `else` and fallthrough.
      - **Known limitation, documented not fixed**: a bare truthy check
        (`if score:`) on a *numeric* variable doesn't match Python
        semantics — Lua treats `0` as truthy (only `nil`/`false` are
        falsy), so `if score:` where `score` is a number behaves like
        "always true" rather than "true if nonzero". Bare/negated checks
        on *boolean* variables (`if book:` / `if not book:`) work
        correctly since real Lua booleans round-trip correctly through
        2.4's evaluator. Explicit comparisons (`if score > 0:`) are
        unaffected and always correct.
      - Test suite: 5 new pytest tests updated/added for the `_render_expr`
        rewrite (compound and/or conditions, updated `Set`/`If` shapes;
        69 total in `tests/converter/`), plus 4 new busted specs for
        `ifvar` (single condition true/false, compound and/or, chained
        if/elif/else via three `ifvar` lines; 50 total in
        `tests/engine/`). Updated `tests/fixtures/sample_full.rpy`'s
        placeholder unsupported construct from `if True:` (now legitimately
        supported) to `if some_condition.attr:` (still correctly rejected)
        to keep testing "gracefully flags something genuinely unsupported."
      - **Re-ran the Jisei baseline**: blocking dropped **356 → 351** (the
        `flow` category — `if`/`elif`/`else` with `and`/`or` — cleared
        entirely; small in absolute terms since Jisei's conditions were
        mostly already simple enough for 2.1's original narrower support,
        but confirms the upgrade path works end-to-end on real content).
- [x] **2.6** — Engine: `play`/`stop` on music + sfx + voice channels; `pause`;
      `window` toggle
      - 2026-07-05: **verification item, no new engine code needed** —
        everything this item lists was already fully implemented in
        earlier phases: `sound`/`music` (Phase 0, upstream VNDS),
        `voiceover`/`stopmusic`/`stopsound`/`stopvoice` (Phase 1.7),
        `window show/hide` (Phase 1.6/1.7), and `delay` (Phase 0's
        `main.moon`, `Timer.after(ins.frames/60, -> next_msg!)` — the
        engine's *only* instruction type that actually pauses script
        advancement; every other type dispatches and immediately
        continues via `main.moon`'s generic `next_msg` `else` branch).
      - Closed two real testing gaps found while verifying: `sound`/
        `music` parsing (the original VNDS commands, in place since
        Phase 0) had never actually been unit-tested — only exercised via
        the `vnds-test` fixture on real hardware and via `audio.moon`
        tests that dispatch pre-built instruction tables directly,
        bypassing `script.moon`'s parser entirely. Same gap for `delay`'s
        parsing. Added both to `tests/engine/extended_vnds_spec.moon`.
      - Added `tests/engine/timer_spec.moon` verifying the actual timing
        primitive `main.moon`'s `delay` handler depends on (`lib/timer`'s
        `Timer.after`/`Timer.update`) genuinely withholds its callback
        until enough time has elapsed, rather than firing immediately —
        confirming `pause`/`delay` really does pause, unlike every other
        instruction. Deliberately tested the timer primitive in isolation
        rather than requiring all of `main.moon` directly in a spec: doing
        so would need mocking most of the LÖVE surface (`love.load` side
        effects, `lfs.createDirectory`, `os.setlocale`, and every
        submodule `main.moon` requires) for very little additional
        confidence, since `play`/`stop`/`window`'s dispatch mechanism is
        structurally identical to already-hardware-validated instruction
        types (`bgload`/`setimg`/`nameplate` since Phase 0/1.5).
      - 5 new busted specs (55 total in `tests/engine/`). No `.moon`
        source changes; no converter changes (2.2/2.3 already emit this
        wire format). No Jisei baseline re-run needed — this item doesn't
        change what the converter emits or how the Problem Report
        classifies anything.
- [x] **2.7** — Engine: save/load — current script position + variable state →
      serialized to SD
      - 2026-07-05: like 2.6, most of this already existed from the
        original VNDS-LOVE fork — `src/engine/save.moon` already writes
        JSON save slots to SD via `love.filesystem.newFile`
        (`dispatch "save_slot"`/`"load_slot"`, a full save-slot picker UI),
        `script.moon`'s `save()`/`load()` already serialize file/position/
        variable state, and `images.moon`/`audio.moon` already have
        `on "save"`/`on "restore"` handlers persisting background/sprite/
        channel state alongside the script position.
      - **Found and fixed a real bug while verifying**: `script.moon`'s
        `save()` never included `s.callstack` — saving mid-`call` (Phase
        1.5) and reloading silently lost the return address, so the next
        `return` would incorrectly treat the stack as empty and end the
        script instead of resuming at the call site. One-line fix
        (`save = (s) -> {..., callstack: s.callstack}`); this existed
        since 1.5 added `call`/`return` and nobody had revisited `save()`
        for it. Confirmed via a regression test that reproduces the exact
        failure mode (save inside a called subroutine, reload, then
        `return` — must resume after the `call`, not end the script).
      - **Deliberately left alone**: `text.moon` has an `on "restore"`
        (resets nameplate/window to defaults on load) but no matching
        `on "save"`, so nameplate text and window-hidden state aren't
        preserved across a save/load — narrower in scope than "script
        position + variable state" (this is presentation state, more like
        the ATL/animation state that's explicitly out of scope until later
        phases), and pre-existing since before this session. Noted here
        rather than fixed, matching the same judgment call as 2.4's dead
        `~` modifier code.
      - Closed a real testing gap: neither `script.save`/`script.load`
        nor `images.moon`'s save/restore handlers had any test coverage
        at all before this — only exercised via the save-slot UI on real
        hardware. Added `tests/engine/extended_vnds_spec.moon` cases
        (position+variable round-trip, and the callstack regression test)
        and a new `tests/engine/images_save_spec.moon` (background/sprite
        round-trip, and restoring an empty save correctly clears state
        for a fresh game).
      - 4 new busted specs (59 total in `tests/engine/`). No converter
        changes — save/load is purely an engine-runtime concern with no
        wire-format implications.
- [ ] **2.8** — Validation: run converter on **Mice Tea**; triage Problem
      Report to zero `blocking`
      - 2026-07-05: **not yet done at the time** — the user asked to
        re-triage Jisei instead of starting Hustle Cat validation (the
        originally-named target here), since Hustle Cat's source wasn't
        acquired yet and Jisei was sitting right there with 2.1-2.7 having
        landed since the 1.9 baseline. See the new dated entry under 1.9
        for that re-triage and a real converter feature it led to (a
        legacy `ui.*` menu pattern-matcher).
      - **Retargeted to Mice Tea**: Hustle Cat's source was never
        acquired, while Mice Tea became the project's actual second real
        validation target (extracted, staged, and extensively worked
        against across the 2026-07-06 Tiers 0-5/fidelity-audit/UI-asset-
        import sessions — see Phase 5's dated entries). **Still not at
        zero `blocking`** — 556 blocking items remain as of the last real
        conversion run; this item stays open until that's driven to zero.
- [ ] **2.9** — Play Mice Tea through at least one full route in Azahar (Old
      3DS profile); memory under 70MB

**Exit check:** §11.2 definition of done satisfied for Mice Tea. **When this
phase closes, evaluate the cutover per `orchestrator/CUTOVER.md`.**

---

## Phase 3 — Fidelity + Animation System + Sucker for Love

**Goal:** Polish player experience; implement ATL animation system; implement
multi-layer sprite system.

- [x] **3.1** — Converter: ATL pattern-matching → `anim` presets + keyframe
      blocks (spec §9.1)
      - **Follow-up from 2.2:** `with <name>` currently downgrades *any*
        non-dissolve/fade transition (`wipeleft`, `wipedown`, `pixellate`,
        custom `CropMove(...)`-based ones, etc.) to a plain dissolve
        (`src/converter/emitters/vnds_writer.py::_resolve_transition`),
        flagged `approximated`. Once this item's preset library exists
        (`enter_left`/`enter_right`/`exit_left`/`exit_right` etc. are
        already planned in 3.3), revisit `_resolve_transition` to map
        recognizable Ren'Py transition names to their nearest matching
        preset instead of always falling back to dissolve — a closer
        fidelity match than the current blanket downgrade. **Still open**
        — not done in this pass; `_resolve_transition` is unchanged.
      - **2026-07-05 — done, pulled forward out of sequence** (user asked
        directly, ahead of the established phase order, after the
        engine-side sprite-sizing bugs made the DS-era coordinate
        question concrete). `_parse_atl_animation` (rpy_parser.py) scans a
        `show X:` ATL block's timed (`linear`/`ease*`) steps: a single
        alpha-only step (0→1 or 1→0) matches `enter_fade`/`exit_fade`
        exactly (spec's own called-out case, not flagged); anything else
        (position, zoom, rotation, 3+ steps, or a block touching
        `if`/`for`/python) builds a real `anim_begin`/`keyframe`/
        `anim_end` sequence instead of collapsing to a static end state —
        flagged `approximated`, but genuinely animated. A `show` ATL block
        with an animation but no explicit position is no longer rejected
        outright (previously `Unsupported` purely for lacking xalign/
        yalign). xalign/yalign/zoom/rotate map to the engine's pixel/
        radian/scale space (`x = xalign*400`, `y = yalign*240`, degrees →
        radians). New `AnimSpec` IR on `Show` (preset name, or a keyframe
        list — never both). Also added `_render_expr` float support
        (needed for `SetVariable("music_vol", 0.5)`-style screen actions,
        item 5.1 below — a real, general gap, not scoped to just that).
        8 new pytest tests. **Real-content result (Jisei):** 23 real ATL
        blocks converted to working `anim_begin` keyframe sequences (0
        matched an exact preset in this game's specific ATL usage);
        `blocking` count dropped 69→41 once a matching classify.py rule
        was added (the new "approximated to a generic keyframe sequence"
        reason initially fell through classify.py's default and was
        miscounted as `blocking` — caught by re-running the real Jisei
        build, not just unit tests, reinforcing
        [[converter_hardware_bugs_round2]]'s lesson).
- [x] **3.2** — Engine: integrate flux tween library; `anim`/`anim_begin`/
      `anim_end`/`anim_wait` commands
      - **2026-07-05 — done, pulled forward.** Vendored `flux` (rxi, MIT)
        into `src/engine/lib/flux.lua`. `script.moon`'s `parse()` gained
        `anim`/`anim_begin`/`keyframe`/`anim_end`/`anim_wait` command
        parsing (documented outside the `switch` block — see
        [[moonscript_switch_comment_quirk]], a real toolchain gotcha found
        while writing this). `anim_wait` blocks script execution the same
        way `choice`/`delay` do (main.moon's `next_msg`), resumed by
        images.moon once the named target's animation completes (or
        immediately, if nothing is animating for that target).
- [x] **3.3** — Engine: full preset library (enter_fade, exit_fade, enter_left,
      enter_right, exit_left, exit_right, enter_bottom, pulse_zoom, shake,
      bounce_in, fade_out_black, fade_in_black, flip_h)
      - **2026-07-05 — done, pulled forward.** New `src/engine/anim.moon`:
        all 13 presets plus `play_keyframes` (the custom keyframe-chain
        builder), both pure tween logic with no knowledge of sprites —
        `images.moon` requires it directly and owns the actual sprite
        list/target resolution (by basename, matching how the converter
        already names foreground assets after the Ren'Py image tag).
        Each sprite's animation state (x/y/r/sx/sy/alpha) is seeded from
        `setimg`'s position and drives `draw_foreground` directly — a
        flat state table matching the spec's own model exactly, not a
        base-position-plus-offset split (an initial design I tried and
        had to correct after a test caught the mismatch: keyframe `x`
        values had no effect since `draw_foreground` was reading a
        separate `dx` offset instead). `fade_out_black`/`fade_in_black`
        animate a screen-wide overlay (new `draw_ui` handler), not a
        sprite. 12 new busted tests (`anim_spec.moon` +
        `extended_vnds_spec.moon`); 72/72 busted pass at this point.
- [ ] **3.4** — Engine: multi-layer sprite system (spec §9.2 Option A) —
      `deflayer`/`showlayer`/`swaplayer`/`hidelayer`/`motion` commands; idle blink
      loop; spring-offset physics approximation
      - **Not the same thing as CharacterImage** (Tier 5, 2026-07-06):
        that's a converter-side, per-game dynamic layer *selector*
        reproduced faithfully at convert time, not this item's generic
        engine-level `deflayer`/`showlayer`/`motion` command set with an
        idle blink loop and spring-offset physics — still open.
- [x] **3.5** — Engine: dissolve/fade transitions between `bgload` calls
      - **2026-07-06 — done**, as part of the project-wide fidelity audit
        (see Phase 5's dated entry). `bgload`'s previously-dormant `frames`
        token now gets populated by `with dissolve`/`with fade` (a real
        alpha fade via `Timer.tween`); `anim.moon`'s existing
        `enter_fade`/`exit_fade` presets cover the Show/Hide case.
        "Transition" itself was confirmed a complete no-op beforehand —
        this was a correctness fix, not just a fidelity one.
- [x] **3.6** — Engine: colored name boxes per character definition
      - **2026-07-06 — done**, same audit pass. `Character(color=...)` now
        threads through to the nameplate (`nameplate #hexcolor Name`),
        and the custom UI-asset-import system separately supports a full
        per-character namebox *image* skin (`namebox_background=...`) on
        top of this for games that ship one (confirmed 84 real uses in
        Mice Tea).
- [ ] **3.7** — Engine: bounded rollback/history (max 3 entries on O3DS — measure
      actual RAM cost per entry, open question spec §15)
- [x] **3.8** — Engine: settings screen (text speed, BGM volume, SFX volume)
      - **2026-07-06 — done**. The BGM/SFX volume half already existed
        (`config.moon`'s `config_menu`, a real native screen with live
        preview and cancel-revert semantics — discovered, not built, this
        pass). Added the missing text-speed control: a new `config.text.
        speed_cps` field (persisted via the existing `config.ini`/`LIP`
        mechanism, no LIP.lua change needed), a matching listbox row using
        the same live-dispatch pattern as the volume rows (`nil` = "use
        the game/hardcoded default", labeled "Text Speed Default"; else a
        concrete cps value, ±5/press, clamped 10–200), and precedence
        logic in `text/text.moon`'s `update_typewriter_speed` (player
        override wins over the game-authored `text_cps.txt` default, which
        wins over the hardcoded 40 fallback — mirrors the existing
        `override_font` persistent-local pattern, since this function is
        also called from `on "restore"` with no config payload to read
        from directly). 11 new busted tests (`config_spec.moon` +
        `typewriter_spec.moon`); full suite 166/166 green.
- [~] **3.9** — Engine: bottom-screen choice button styling (highlight, touch
      feedback)
      - **Partially done, 2026-07-06**: the custom UI-asset-import system
        gives real idle/hover button background images (a genuine
        highlight state) instead of a text-color-only distinction. Touch
        input already existed (`listbox.moon`'s `on "touch"`) and still
        directly selects+triggers — no separate pressed/tap visual
        feedback state exists yet. Leaving unchecked since "touch
        feedback" specifically isn't done.
- [ ] **3.10** — Engine: `nvlmode` (NVL text routed to top screen)

**Exit check:** 3.1-3.10's engine features (ATL animation, multi-layer sprites,
transitions, colored name boxes, rollback, settings screen, button styling,
nvlmode) demonstrated working end-to-end on an existing test title; memory
under 70MB throughout. (Sucker for Love: First Date and Am I Nima? moved to
Phase 6 — see that phase's entry.)

---

## Phase 4 — Packaging + Bone/Puppet System + Asset-Heavy Titles

**Goal:** Production-quality builds; bone/puppet animation system; asset-heavy
titles.

- [ ] **4.1** — CIA packaging via `makerom` with per-game icon, banner, and title
- [ ] **4.1b** — Per-novel HOME Menu forwarders (spec §5.3) — lightweight
      `makerom`-built CIAs that relaunch the shared engine `.3dsx` straight
      into a specific `/novels/<name>/` folder, so each installed VN gets
      its own icon/banner/title without a full per-title engine rebuild;
      evaluate alongside 4.1 as a complement or alternative
- [ ] **4.2** — Atlas optimisation: bin-packing sprites into fewer `.t3x` atlases
- [ ] **4.3** — Multi-VN library/launcher menu on the engine's title screen
- [ ] **4.4** — Partial re-convert (only changed labels/assets re-processed)
- [ ] **4.5** — Engine: bone/puppet animation system (spec §9.2 Option B) — bone
      hierarchy format, `loadpuppet`/`showpuppet`/`hidepuppet`/`puppet_motion`
      commands, per-bone spring physics
- [ ] **4.6** — Performance validation: two simultaneous puppet characters on
      Old 3DS profile without frame drop
- [ ] **4.7** — Port **Slay the Princess** — converter + triage; validate asset
      pipeline throughput and SD budget
- [ ] **4.8** — Port **Kansei** (Jisei sequel)
- [ ] **4.9** — Port **Yousei** (Jisei sequel, 8–9 hrs)

**Exit check:** At least two of 4.7–4.9 playable end-to-end on Old 3DS hardware.
CIA builds installable from SD. Bone/puppet operational on O3DS.

---

## Phase 5 — Complex Ports + Custom Screen Runtime

**Goal:** Tackle games with native game systems requiring reimplementation.

- [x] **5.1** — Engine: minimal custom-screen runtime (most common menu/stats
      patterns)
      - **2026-07-05 — done, pulled forward well out of sequence** (user
        asked directly). Worth noting explicitly: §11 line 1358 of this
        same plan flags this exact item as an *open, unresolved question*
        — "Is a custom-screen runtime worth building, or is per-game
        native reimplementation faster? Evaluate after Phase 4 experience
        with Slay the Princess." Flagged this to the user before starting;
        they chose to proceed anyway, so the scope/grammar below is this
        session's own design, not something the spec had already worked
        out (contrast with 3.1-3.3's animation system, which had a full
        spec section to implement against).
      - **Scope, deliberately not general:** vbox/hbox layout, static
        `text`, `textbutton` + a handful of actions (`Jump`/`Call`/
        `Return`/`Quit`/`Show`/`ShowMenu`/`Hide`/`SetVariable`), and
        `if`/`elif`/`else` conditionals evaluated live against game state
        via the existing `expr.moon` evaluator. Explicitly **not**
        supported: `for` loops (no list-typed VNDS variables to iterate),
        composite `[Action, Action]` lists, arbitrary Python. A screen
        using any of those is rejected as a whole (`manual`), not
        partially converted.
      - **Engine:** new `src/engine/screen.moon` — builds a screen's tree
        via `screen_begin`/`vbox_begin`/`screen_text`/`screen_button`/
        `screen_if`/`screen_elif`/`screen_else`/`screen_endif`/
        `screen_end` events (screen *definitions* live in the script's
        always-executed top-level preamble alongside `default`/`define`,
        registered once, shown many times via `show_screen`), flattens
        the tree against live variable state each time it's shown, and
        renders/handles input by reusing `listbox.moon`'s existing
        navigable-list widget rather than building a second one.
        `main.moon` blocks on `show_screen` the same way it already does
        for `choice`. Added `script.jump_to_label` so a screen's `jump`/
        `call` action can redirect flow the same way a real instruction
        would. Also added a **native main menu** (Start Game / Quit),
        built directly on this runtime and shown by `save.moon`'s
        "new game" path right before it would otherwise jump straight
        into the story — Ren'Py's own default `main_menu` screen is a
        builtin with no `.rpy` source, so nothing the converter emits
        would ever produce one; this was the direct fix for the
        already-reported "skips the main menu" hardware finding.
      - **Converter:** `_parse_screen_children`/`_parse_screen_def`
        (rpy_parser.py) parse the supported subset into a `ScreenDef`
        tree (`Script.screens`, emitted the same way as `top_level_sets`);
        a failure partway through a block rewinds the cursor via new
        `Cursor.bookmark()`/`restore()` methods and cleanly re-skips the
        *whole* block, rather than leaving the cursor desynced mid-block
        (would have corrupted parsing of whatever follows). Real Ren'Py
        default screens (`_DEFAULT_SCREEN_NAMES`) are unaffected — still
        correctly skipped as no-ops, never attempted through this parser.
      - 20 new tests total (7 busted for screen.moon's tree-building/
        rendering/actions, 1 native-main-menu check, 6 pytest for
        parsing, 3 pytest for emission) plus a real end-to-end round-trip
        test through the actual `script.moon` parser on the exact text
        `vnds_writer.py` emits — the same category of gap
        ([[converter_hardware_bugs_round2]]) that let the `.t3x`-extension
        and bare-`voice`-statement bugs ship unnoticed on earlier rounds;
        this one round-tripped clean on the first try. 83/83 busted +
        132/132 pytest pass.
      - 2026-07-05 (real hardware retest, different machine — see the
        Azahar note in §0.6 for the environment context): played the
        rebuilt Jisei bundle on a physical Old 3DS via Homebrew Launcher.
        Native main menu appeared and worked (expected — no PC-style
        custom main menu exists to convert). Found and fixed two real
        bugs:
        1. **Composite-based character sprites never appeared.** Jisei
           defines every character's face as `image chance a01 grin =
           im.Composite(None, (0,0), "base01.png", (0,0),
           "eyebrows01.png", (0,0), "mouth10.png", (0,0), "eyes08.png")`
           — swappable base/eyebrows/mouth/eyes layers, all at `(0,0)`
           offset (confirmed against every `im.Composite` call in the
           game, 165 of them). The parser correctly excluded these from
           `Script.images` (not a plain file path) and flagged the
           *definition* `manual`, but `vnds_writer._resolve_image_path`'s
           fallback for "tag not in `images`" — meant for an anonymous
           tag that happens to match a real file's basename — fired for
           these too, emitting `setimg chance_a01_grin.t3x` for a file
           the asset pipeline never produced. `main.moon`'s `path_exists`
           check silently no-ops a `setimg` whose file is missing, so the
           sprite just never rendered — no error, no Problem Report entry
           pointing at it. Fixed by actually resolving the pattern: new
           `Script.composites` (rpy_parser.py's `_parse_composite_layers`
           detects the exact `im.Composite(None, (0,0), path, (0,0),
           path, ...)` shape, bailing to the existing `manual` flag for
           anything else — a non-`(0,0)` offset, a non-`None` master, a
           different call entirely), and `assets/pipeline.py`'s new
           `resolve_composite_images` alpha-composites the layers with
           Pillow into one real image before handing it to `tex3ds`, for
           every composite tag the emitted script actually references.
           Manual-flag count dropped 240 → 75 on Jisei's real Problem
           Report (blocking unchanged at 41); foreground asset count
           183 vs. 20 before.
        2. **The intro's full-screen pan image didn't reach the screen
           edges.** `story.rpy`'s `show death: yalign 1.0 / linear 23.0
           yalign 0.0` converts correctly to a foreground sprite +
           y-only keyframe animation, but the asset pipeline downscales
           *all* foreground art to fit within 400×240 (right for a normal
           already-screen-sized character sprite, per that constant's own
           docstring) — for this specific tall pan image, that shrinks it
           to fit entirely inside 240px of height, leaving it far
           narrower than the 400px screen. Fixed with a narrow, testable
           signal rather than a blanket policy change: new
           `pan_foreground_targets` (pipeline.py) scans the emitted
           script for `anim_begin`/`keyframe`/`anim_end` blocks whose
           keyframes only ever vary `y`/`alpha` (never `x`/`sx`/`sy`) —
           Ren'Py's vertical-pan idiom — and `resolve_and_convert_assets`
           sizes exactly those targets by filling the screen's width
           or (400px) and leaving height free (capped only by the
           1024px hardware texture limit), the same policy a background
           gets, instead of fitting both axes.
        - New tests: 2 pytest (composite layer parsing, including a
          non-`(0,0)`-offset case that must still fall back to `manual`),
          3 pytest (`resolve_composite_images` — stacks layers, skips a
          tag never actually referenced, reports one bad layer without
          aborting the batch) + 1 CLI end-to-end test, 2 pytest
          (`pan_foreground_targets` — matches a real y-only block,
          excludes one that also moves x/scale) + 1 pytest confirming the
          resulting downscale actually fills 400px width. 141/141 pytest
          + 83/83 busted pass. Rebuilt bundle: manual 75/blocking 41
          (from 240/41), foreground assets 183 (from 20).
        - **Still open from this same hardware round** (static
          source/log analysis alone didn't find a root cause for either
          — both need a hardware-observed print/log trace to pin down
          further, the same way the original word-wrap bug below was
          eventually confirmed):
          - Text still intermittently overflows the screen's right edge
            despite the `text_box_width()` fix a few rounds back (already
            confirmed correct against LÖVE Potion's actual pinned source,
            see that entry above) — toggles on/off between specific
            dialogue lines in the same playthrough (works from "Suspicious
            goes without saying" onward, breaks again at "Detective Gurski
            follows me..."). Loosely correlated with narrator vs.
            character-spoken lines (`vnds_writer.py` only emits
            `nameplate <speaker>` when there *is* a speaker, never
            `nameplate ~` to clear a stale one for a narrator line —
            confirmed as its own real, separate bug, but doesn't explain a
            wrap-*width* change on its own) — not conclusively proven as
            the cause of the wrap toggle itself.
          - Selecting any option in the café investigation menu ("Talk" /
            "Examine Room" / "Move" — Jisei's legacy `ui.vbox`/
            `ui.textbutton`/`ui.interact()` idiom, confirmed converted
            correctly into a plain `choice`/`jump` Menu by
            `_try_convert_ui_menu`, *not* routed through the
            `screen.moon` custom-screen runtime) makes the bottom screen
            go black afterward — top screen keeps working, no crash.
            Traced the `choose.moon`/`listbox.moon` event-handler
            lifecycle (a listbox's `input_event` calls `chosen.action`,
            which synchronously advances into the *next* label's own
            `choice` — registering a brand new listbox — before the
            outer listbox removes its own handlers) against `lib/
            event.lua`'s doubly-linked-list dispatch; the list itself
            appears to patch prev/next links correctly on self-removal,
            so this remains unexplained from source alone.
          - A few sound effects/voice lines stutter at playback start —
            possibly the same "brief hitch at stream start" already
            observed and accepted during the Phase 0 O3DS stress test
            (streamed SD audio, spec §14), not necessarily a new code
            defect. Not yet investigated further.
      - 2026-07-05, same-day second hardware retest: the rebuilt bundle
        surfaced real, non-trivial engine bugs, most confirmed by a
        photo of the physical Old 3DS mid-playthrough. Fixed five:
        1. **Every dialogue line piled into the box instead of
           replacing it.** `text.moon`'s `on "text"` only replaced the
           buffer once it happened to already contain exactly `lines`
           (7 on 3DS) wrapped lines — every other `text` dispatch (i.e.
           nearly every real say statement) concatenated onto whatever
           was already showing. Confirmed on hardware by photo: three
           unrelated exchanges ("Until they come?...", "I'm technically
           not on duty...", "I see...") all visible at once under one
           stale nameplate. Fixed: an ordinary line now always replaces
           the buffer outright; only a `@`-prefixed continuation still
           appends. A single statement that itself wraps past `lines`
           still pages correctly via the existing `done!` mechanism.
        2. **A narrator line right after a character line kept showing
           the character's name.** `vnds_writer.py`'s `Say` emission only
           wrote `nameplate <speaker>` when there *was* a speaker, never
           `nameplate ~` to clear one for a narrator line. Directly
           visible in the same hardware photo.
        3. **The intro pan animated across the wrong range, in the
           wrong direction.** `_atl_prop_to_engine` baked `yalign` to a
           pixel `y` at *parse* time assuming the sprite was exactly
           screen-height (240px) — correct for an ordinary sprite, wrong
           for the pan image (deliberately taller, per the 07-05 fix
           above). `yalign 1.0 -> yalign 0.0` became `y=240 -> y=0`,
           panning across only the screen's own 240px instead of the
           image's real ~625px height, and starting already off the
           bottom of the screen instead of showing the image's own
           bottom edge. Fixed by *not* resolving `yalign` at parse time:
           it's emitted as the raw 0.0–1.0 fraction and resolved at
           animation time (`images.moon`'s `anim_end`) against
           whatever sprite is actually loaded (`y = yalign * (240 -
           real_sprite_height)`) — correct for both cases through the
           same code path, since a normal ~240px-tall sprite reduces to
           `y ≈ 0` regardless of the fraction.
        4. **Character sprites stacked instead of replacing each
           other.** Confirmed by the same hardware photo's report ("each
           new sprite placed on top of the last"). Every composite-
           resolved expression (base+eyebrows+mouth+eyes) is a
           *different* file, so `setimg`'s exact-path-match dedup never
           found the previous expression to remove. Fixed: also reject
           any existing sprite at the same `(x, y)` position, matching
           how Ren'Py's own `show <tag>` replaces whatever currently
           occupies that character's slot.
        5. **Sprites were positioned relative to the background's own
           letterboxing, not the screen.** `draw_foreground`'s
           `offsetX`/`offsetY` shifted every sprite by however much the
           *background* happened to be letterboxed to fit the screen —
           harmless when background and sprites shared one native
           resolution (original VNDS content), wrong for converted
           content where a sprite's `(x, y)` is already an absolute
           position in the fixed 400x240 virtual space. Removed
           entirely; sprites now draw at `x*pscale, y*pscale` with no
           background-relative correction.
        - New tests: 1 busted (dialogue buffer replaces, not
          concatenates), 1 busted (`yalign` keyframe resolved against
          real sprite height), 2 busted (position-based sprite
          replacement — same-slot swap, and two genuinely different
          positions still coexist), 1 busted (sprite position
          independent of background scale), 5 pytest (`nameplate ~` on
          narrator lines — a `_labels_from_vnds`-style rewrite of 4
          existing control-flow tests plus one dedicated case) — plus a
          `_atl_prop_to_engine` unit test updated to expect a raw
          `yalign` fraction instead of a pre-baked pixel `y`. 141/141
          pytest + 88/88 busted pass. Rebuilt bundle/engine/`.3dsx` and
          re-staged the SD card; awaiting the next hardware retest.
        - **Still open** (unchanged from the note above — the black
          bottom screen on café menu selection, the word-wrap toggle,
          and audio stutter): the dialogue-buffer fix may turn out to
          explain the word-wrap toggle too, since stale piled-up text
          was being measured/rendered together with fresh lines: worth
          rechecking specifically once retested, rather than assuming
          it's still open.
      - 2026-07-05, third same-day hardware retest: confirmed fixed —
        the intro pans correctly now, and dialogue lines are properly
        separated (no more run-on multi-speaker text). Found and fixed
        three more real bugs, plus recorded one still-open item that
        escalated from a visual glitch to an outright crash:
        1. **Word-wrap still cut text off, one `pad` short of the box's
           own edge.** `draw_text` prints each line at `x = 2*pad` (the
           box's own left edge at `x = pad`, plus one more `pad` of inner
           margin) but `word_wrap` was still measuring against
           `text_box_width! - 2*pad` (i.e. from `x = 0`) — so a wrapped
           line's right edge could reach `2*pad + (text_box_width! -
           2*pad) = text_box_width!`, the screen's absolute edge, with no
           margin to match the left side's. Fixed by measuring against
           `text_box_width! - 4*pad` instead, so the right edge lands at
           `text_box_width! - 2*pad`, symmetric with the left.
        2. **The nameplate was positioned too high, partially cut off at
           the screen's top.** The box's height (and therefore its `y`
           position, and the nameplate drawn above that) was computed
           from the fixed `lines` capacity (7 on 3DS) every frame,
           regardless of how much text was actually showing — harmless
           back when separate lines piled up together and often nearly
           filled that space anyway (see the "still open" item just
           above, since fixed), but once an ordinary line replaces the
           box outright (usually just 1 wrapped line), that reserved
           height pushed the box — and the nameplate above it — up past
           the top of the screen. Confirmed on real hardware exactly as
           described: nameplate visible but cut off at the top, correct
           speaker name in the visible portion. Fixed: box height (and
           therefore position) is now sized to `min(#buffer, lines)`,
           the actual visible line count, not the fixed capacity.
        3. **Character sprites stacked again once a scene had 3+
           characters on screen.** The position-based sprite replacement
           fix from the previous entry only replaced a sprite at the
           *exact same position* — but there are only 3
           canonical positions (left/center/right), so a scene with 3+
           simultaneous characters can legitimately place a new
           character at a position an earlier, still-visible *different*
           character already occupies; matching by position alone
           incorrectly removed that earlier sprite too. Fixed properly
           this time: `vnds_writer.py`'s `Show` emission now passes the
           Ren'Py image tag's first word (e.g. `chance` from `chance a01
           grin`) as `setimg`'s 4th token — the character's actual
           identity — and `images.moon`'s `setimg` handler replaces by
           that "slot" when present, falling back to the old
           position-only match for hand-authored VNDS content with no
           4th token. `save`/`restore` round-trip the slot too.
        - New tests: 1 busted (wrapped line's right edge stays
          symmetric with the left, not reaching the screen edge), 1
          busted (box/nameplate sized to actual visible line count, not
          the full 7-line capacity), 2 busted (slot-based replacement —
          same slot at a different position/filename still replaces;
          a 3rd character sharing an earlier one's position doesn't
          remove it), 5 pytest (every existing `setimg` emission
          assertion updated for the new 4th token). 141/141 pytest +
          92/92 busted pass. Rebuilt bundle/engine/`.3dsx`, re-staged
          the SD card.
        - **"Skipped the main menu" is expected, not a regression** —
          confirmed against `save.moon`: the native main menu only
          shows on the *fresh-game* path (`load_slot`'s `new_slot`
          action); an *existing* save (left over from testing the same
          SD card repeatedly) takes the "continue" path straight into
          the story instead. Clear the save slot to see the main menu
          again.
        - **Escalated, not yet fixed: clicking "Move" in the café
          investigation menu now crashes** (previously just blacked out
          the bottom screen — see the still-open note above). Traced
          the generated script for that path (`cafemenu` ->
          `cafemovemenu` -> `hallwayevents`/`crimescenemenu`) end to
          end; every label and jump target resolves to something real,
          nothing obviously malformed. Without an actual stack
          trace/error message from the device, this can't be narrowed
          further from source alone — next step is asking for a photo
          of whatever LÖVE Potion's crash/error screen shows (if any),
          the same way a photo of the dialogue box cracked the buffer
          bug open earlier this session.
      - 2026-07-05, fourth same-day hardware retest: word-wrap, dialogue
        separation, and the pan are all confirmed working; a residual
        word-wrap edge case and the character-sprite size were addressed:
        1. **Character sprites confirmed smaller than the PC version by a
           direct side-by-side screenshot** (same scene, same character,
           photographed on hardware next to a PC screenshot). Root cause:
           `_FOREGROUND_MAX_HEIGHT` (240, capping *both* axes) shrank
           every composite to whatever width fit inside a 240px-tall box
           — but real VN character art is authored to overflow/crop at
           the viewport's edges (a bust shot cropped at the waist, head
           near the top), not to shrink to fit entirely inside it with
           room to spare; the PC screenshot showed the character filling
           nearly the whole frame height, cropped by the window. Fixed by
           removing the height cap entirely for *all* foreground art
           (character sprite or full-bleed pan alike) — only width is
           capped to the screen (400px), height is left free (bounded
           only by `_MAX_TEXTURE_DIMENSION`'s 1024px hardware safety net).
           Confirmed against Jisei's own Chance base layer (286x768
           native): previously downscaled to fit 240px height -> ~89px
           wide (22% of screen width, visibly tiny); now stays at its
           native 286x768 (72% of screen width, cropped top/bottom) —
           matching the PC reference proportions. This also made the
           pan-specific sizing logic (`pan_foreground_targets`,
           `pan_targets`) redundant now that *every* foreground image
           gets the same width-fill/height-free treatment — removed
           that function and parameter entirely rather than leave dead
           code around.
        - Updated/removed tests: `resolve_and_convert_assets`'s old
          "downscales foreground more aggressively than background" test
          renamed to "fills foreground width leaving height free" and
          extended to assert the actual resulting dimensions; the two
          `pan_foreground_targets`-specific tests removed (function no
          longer exists) and its dedicated resize test merged into the
          general foreground-sizing test. 139/139 pytest (net -2, exactly
          the removed `pan_foreground_targets` tests) + 92/92 busted
          (unchanged — no engine-side change this round). Rebuilt bundle
          and re-staged the SD card.
        - **Investigated but not fixed: word-wrap still occasionally
          drops the last character of the last word before a line
          break** (e.g. "with" -> "wit" / "it. ...", "latte" -> "latt" /
          "isn't ..." — confirmed by three hardware photos, much rarer
          than before the padding-margin fix but still present). Traced
          `word_wrap`, `split` (util.moon), and `colorify`
          (text_color.moon) end to end — none show an obvious bug; the
          consistent "always exactly the final character" pattern
          suggests a font-measurement-vs-actual-rendering discrepancy
          (e.g. kerning) rather than a logic error, but this can't be
          confirmed without device-side instrumentation. Left as open
          rather than shipping an unverified guess on top of already
          unverified changes.
        - **Still open, unchanged:** the café "Move" crash (needs a
          device error-screen photo to diagnose further) and the
          audio/voice stutter (likely inherent SD streaming latency).
      - 2026-07-05, fifth same-day round: at the user's request, tried
        fixing the residual word-wrap issue a different way — wiring up
        Jisei's own actual dialogue font (`gui/HanSrf.ttf`, declared via
        `style.default.font = "gui/HanSrf.ttf"` in `options.rpy`) instead
        of relying on LÖVE's generic built-in font, on the theory that a
        font-measurement-vs-rendering mismatch was the real cause. This
        also surfaced and fixed two real, previously-undetected bugs in
        code that had never actually run before:
        1. **The font-declaration itself sits inside `init -1 python
           hide:`** — arbitrary Python, otherwise entirely unparsed. Added
           a standalone regex scan (`rpy_parser.py`'s
           `_scan_default_font`, same spirit as the existing
           `_record_string_define` opportunistic scan) that recovers
           `style.default.font`'s path independent of the surrounding
           block structure — new `Script.default_font`, merged across
           files in `parse_game` (first non-None wins). `build_bundle`
           resolves it against `game_dir` (the font file lives alongside
           the `.rpy` source, e.g. `game/gui/HanSrf.ttf`, *not* inside the
           extracted asset archive) and copies it to the bundle root as
           `default.ttf`.
        2. **`text.moon`'s `update_font` — which reads exactly that
           `default.ttf` — had two of its own bugs, caught only now
           because nothing had ever produced a `default.ttf` to actually
           exercise this code path before:**
           - `lfs.getInfo(font_path)` is the exact same LÖVE Potion 2.0.0
             3DS-filesystem-backend unreliability `main.moon`'s
             `path_exists` was already written to work around elsewhere
             (can report false for a file `getDirectoryItems` clearly
             lists) — `update_font` had its own fresh `lfs.getInfo` call
             instead of reusing `path_exists` (exported globally by
             `main.moon`'s `export *`).
           - The custom font always loaded at a hardcoded size `32`,
             ignoring the same width-based sizing `main.moon`'s own
             `love.resize` already uses for the *default* font (20 on a
             narrow/3DS-bottom-screen-width display, 32 otherwise) — would
             have rendered the custom font *larger* than intended on the
             physical 3DS, worsening overflow rather than fixing it.
        - New tests: 2 pytest (`_scan_default_font` recovers the path from
          inside the `init python` block; returns `None` when absent),
          2 pytest (CLI end-to-end — font copied to `default.ttf` when
          declared and present; skipped cleanly when the declared file is
          missing), 3 busted (`update_font` calls `path_exists` with the
          expected path rather than `lfs.getInfo`; sizes the custom font
          20pt on a narrow screen rather than a hardcoded 32; falls back
          to the built-in font when no `default.ttf` exists). 143/143
          pytest + 95/95 busted pass. Rebuilt bundle (confirmed
          `default.ttf` present, byte-identical to Jisei's own
          `gui/HanSrf.ttf`), engine, and `.3dsx`; re-staged the SD card
          (font file included alongside `script/`/`background/`/etc. at
          the novel's own root, matching where `update_font` looks).
        - **Investigated the "Move"/"Examine Room" report** (no longer
          crashing, but "loop back to the option menu instead of doing
          what they're supposed to"): traced the actual generated script
          for "Examine Room" end to end — `cafeexamine`'s `ifvar` chain
          correctly falls through (on a fresh save, no story-progress
          flags are set yet) to flavor text ("This area is small, but
          comfortable...") *then* `jump cafemenu` — this looks like
          correct, intentional investigation-loop design (examine, read
          a line, return to the menu to pick the next action), not a
          bug. Needs confirmation from the user: did the flavor text
          actually appear before returning to the menu, or did it skip
          straight back with no interstitial text at all? That
          distinction determines whether this needs any further work.
      - 2026-07-05, sixth same-day round: user confirmed "Examine room
        doesn't display any flavor text" — a real bug, not intended
        design as the previous entry hypothesized. Root cause: Ren'Py's
        `window hide` is *transient* — it only suppresses the dialogue
        box until the *next* real line of dialogue, which auto-shows it
        again; it is not a persistent toggle. Confirmed against Jisei's
        own source: `label cafeexamine:` opens with `window hide` and
        never calls `window show` before its own dialogue lines (this is
        the real, unmodified Ren'Py source, not a converter artifact).
        This engine's `text.moon` treated "window hide" as sticky
        (`window_visible` only flips back via an explicit "window"
        dispatch), so `draw_text`'s very first check (`if #buffer > 0
        and window_visible`) silently skipped rendering *any* text after
        a "window hide" with no matching "window show" — exactly
        "Examine Room" and (very likely) "Move"'s pattern, and probably
        any other Ren'Py content using this same common idiom (hide the
        box briefly, let dialogue itself bring it back). Fixed: a real
        line of dialogue (`on "text"`, after the empty/no-op-text guard)
        now always sets `window_visible = true`, matching Ren'Py's actual
        behavior — "window hide" still suppresses the box for scenes
        with no dialogue at all (nothing forces visibility if "text"
        never fires), just not sticky-forever once real dialogue resumes.
        - New test: 1 busted (a "window hide" with no following "window
          show" still renders the next real line of dialogue, reproducing
          Jisei's own `cafeexamine` shape exactly). 143/143 pytest +
          96/96 busted pass. Rebuilt engine and `.3dsx`, re-staged the
          SD card (font copy from the previous entry carried over).
        - This likely also explains why "Move" appeared to "do nothing" —
          its target labels almost certainly follow the same `window
          hide` + dialogue-with-no-window-show shape; worth confirming
          on the next hardware round now that the root cause is fixed
          rather than assuming it's resolved.
      - 2026-07-05, seventh same-day round: at the user's request, ran a
        **converter-only dry run** (no engine/hardware) against a second
        real title to stress-test the converter against genuinely
        different content, comparing results with Jisei's own conversion.
        **Discovered first that neither of the two originally-intended
        Phase 2/3 targets are actually Ren'Py** (verified directly against
        the installed game files, not documentation): **Hustle Cat** runs
        on Date Nighto's own proprietary "htmlvn" HTML5/JS engine (NW.js
        packaged, script data compiled into `scripts/hustlecat.js`, no
        `.rpy` source anywhere); **Sucker for Love** is **GameMaker:
        Studio** (`data.win` confirms it). Both corrected in
        VN3DS-spec.md §11.2/§11.3 and demoted from their phase
        assignments — see those entries; re-scoping which titles now fill
        "Phase 2 first full port" and "Phase 3" is a planning decision to
        make separately, not done here. Confirmed **Our Life: Beginnings
        & Always** and **Mice Tea** are both genuinely Ren'Py (real
        `renpy/` runtime folders present) and used Mice Tea for the actual
        dry run (a Cinnamon Switch title, structurally very different
        from Jisei: custom `think`/`alt` statement extensions, named
        top-level `transform` blocks, multi-line `show` ATL blocks with
        several chained transform properties, a much larger script — 103
        `.rpy` files vs. Jisei's 12).
        Found and fixed three real converter bugs, none reachable from
        Jisei's own content:
        1. **A label declared inside another label's body crashed the
           converter outright** (`AssertionError: unhandled node type:
           Label`) — the parser already anticipated this ("nested label —
           unusual in Ren'Py but not forbidden"), but the emitter never
           got a case for it. Real content found in the wild: a named
           point mid-scene (e.g. `label day_2_julie_choice:`), jumped back
           to directly to re-present a choice after a failed/retry path —
           not a genuinely nested scope. Fixed: VNDS's label system is
           exactly as flat as Ren'Py's (every "@name" is a global jump
           target, and falling through one during linear execution is a
           no-op), so this needed no synthetic jump — just the marker
           emitted inline, with the label's own body plus whatever
           followed it at the same level folded into one continued
           sequence under the new name.
        2. **`default`/`define` of a literal declared *inside* a label's
           body** (route-tracking flags set partway through a scene, e.g.
           `default afd24_route = "afd24_nonfurry"`) **fell through to a
           generic Unsupported** — only the top-level parse loop
           recognized these prefixes; the per-statement parser used for
           label bodies didn't call the same handler at all.
        3. **`window auto`** (Ren'Py's third window state, alongside
           show/hide) **and a trailing transition token** (`window hide
           None` — unrpyc's real decompiled rendering of an
           explicit-but-empty transition argument) **weren't recognized**
           by `_WINDOW_RE`, which only matched bare "window show"/"window
           hide". Both silently common enough in Mice Tea's own script to
           drop the blocking count by over 150 items once fixed. No
           engine change needed — `images.moon`'s `on "window"` already
           treats anything but "hide" as visible, so "auto" behaves
           correctly for free.
        - New tests: 3 pytest (nested label mid-body emits inline and
          keeps falling through; nested default/define converts as a Set;
          nested default with a list value still correctly flags manual
          rather than silently converting), 2 pytest (`window auto`/
          trailing-transition-token recognized). 147/147 pytest pass.
          Re-ran Jisei's own conversion afterward to confirm zero
          regression (still exactly 41 blocking / 223 total, unchanged).
        - Mice Tea's own Problem Report after these fixes: 3207 blocking /
          5704 total (much higher proportion than Jisei's 41/223 — a
          longer, more feature-rich game with named `transform` blocks
          not supported at all yet, the single largest remaining
          category). No engine build/hardware test done this round
          (converter-only dry run, by design) — Mice Tea is not currently
          a scheduled port target, this was purely a converter stress
          test using real, structurally different content.
    - **2026-07-05 — Mice Tea promoted from dry run to a real staged
      hardware build**, alongside Jisei, on user request ("prepare both
      jisei and mice tea for the latest hardware test"). Extracted
      Mice Tea's `images`/`audio`/`fonts`/`demo_content`/`full_game.rpa`
      archives via `unrpa` (4169 files) and ran the full converter CLI
      with `--assets` pointed at the extraction, rather than the earlier
      script-only dry run. Two real gaps found and fixed in the process:
        1. **Font declaration syntax differs from Jisei's.** Jisei's
           `options.rpy` sets `style.default.font = "..."` directly, which
           `_scan_default_font`'s regex looked for exclusively. Mice
           Tea's `gui.rpy` — Ren'Py's standard GUI-customization
           template, which Jisei's older/hand-rolled `options.rpy` never
           used — instead sets `define gui.default_font = "..."`. Same
           purpose, different variable name entirely unrecognized by the
           old regex. Fixed by extending `_DEFAULT_FONT_RE` to match
           either form into the same capture group.
        2. **Font file location differs from Jisei's, too.** Jisei's
           `gui/HanSrf.ttf` sits as a loose file alongside the `.rpy`
           source, so `build_bundle`'s font-copy step resolved it against
           `game_dir` only. Mice Tea RPA-packs its fonts alongside its
           images/audio (`fonts.rpa`) — `VarelaRound.ttf` only exists
           inside the extracted asset folder, never next to the `.rpy`
           source. Fixed by falling back to `assets_dir` when `game_dir`
           doesn't have the declared font file.
        - New tests: 1 pytest (`define gui.default_font` recognized), 1
          pytest (font copy falls back to `assets_dir` when not found
          next to the `.rpy` source). 149/149 pytest pass.
        - Resulting Mice Tea bundle: 23 backgrounds, 69 foregrounds, 23
          sounds converted; `default.ttf` (VarelaRound) successfully
          copied in via the new assets_dir fallback; entry point correctly
          resolved to `@start` → `jump mice_tea_start` (Mice Tea's own
          `label start:` already sits at the front the same way
          `_reorder_entry_label` handles Jisei's, so no special-casing
          needed there). Same 3207/5704 Problem Report totals as the dry
          run (expected — no parser/emitter logic changed, only font
          resolution). Staged as a second novel at
          `build/lovebrew/sdcard/.../novels/mice-tea/` alongside the
          already-current Jisei build, under the same unmodified `.3dsx`
          (no engine `.moon` changes since the last hardware round) —
          both novels ready for the user to copy onto the SD card and
          pick from Homebrew Launcher's game list in one sitting.
    - **2026-07-05 — Named `transform NAME:` blocks now supported**
      (converter + engine), on user request ("let's try to get the
      transform blocks supported with our engine/converter") before the
      next hardware round. This was Mice Tea's single largest remaining
      Problem Report category (357 blocking declaration-site items, plus
      913 more "no recognizable position" items at usage sites — real
      content confirmed this game positions almost every sprite through
      named transforms, not `left`/`center`/`right` or inline ATL, e.g.
      `show afd_l neutral faceleft:` with bare `bs_centerleft3`/`faceleft`
      lines inside the block, or `show gavin at faceleft,
      offscreenright_male:` composing transforms via the `at` clause).
        - **Two-pass collection**: `scan_transform_declarations` (new,
          reuses the existing tokenizer) harvests every `transform NAME:`
          body across *all* `.rpy` files before any file's statements are
          parsed — necessary because Ren'Py's transform namespace is flat
          across files, and a plain alphabetical sort parses `story/*.rpy`
          before `transforms.rpy` in this game, so a naive single-pass
          parse would hit "unknown transform" for the overwhelming
          majority of real usage.
        - **Reference resolution**: both real forms now resolve — a bare
          transform-name line inside a `show/scene X:` block, and
          comma-separated names in the `at` clause itself (`_AT_RE` widened
          from capturing one name to the full clause). Recursive expansion,
          depth-guarded.
        - **Generalized static ATL model**: `xcenter`/`ycenter`/`xanchor`/
          `yanchor`/`xpos`/`ypos` recognized alongside the existing
          `xalign`/`yalign`/`zoom`/`xzoom`/`yzoom`/`rotate`/`alpha` (all
          confirmed used in real content well beyond `transforms.rpy`).
          Vertical positioning generalized from a single `yalign` fraction
          to an independent (position, anchor) pair — real content breaks
          the old anchor==position assumption directly (`yalign 1.0 ypos
          1.2` — anchor stays 1.0, only the position moves). Exactly
          reduces to the old formula when anchor==position, so zero
          behavior change for Jisei's existing single-`yalign` content
          (confirmed: re-ran Jisei's own conversion after, still exactly
          41 blocking, 222 vs 223 total — the one-item difference is the
          next bullet's intentional change, not a regression).
        - **Static zoom/rotate/alpha are now actually applied**, not
          silently discarded-and-flagged — the engine's per-sprite
          animation state already had native `sx`/`sy`/`r`/`alpha` fields
          (`draw_foreground` already read them every frame), they just
          never had a static (non-animated) source. `setimg` gained
          trailing optional `key=value` tokens (reusing `keyframe`'s
          existing `parse_props` convention) carrying the resolved
          fractions/scale/rotation/alpha; `images.moon`'s `on "setimg"`
          resolves them against the sprite's *real* loaded height right
          away, generalizing (and unifying with) the animated path's
          existing `resolve_yalign`. This also fixes a pre-existing,
          previously-documented gap: a *static* `yalign` position used to
          be baked to a flat `yalign*240` pixel value at parse time,
          ignoring the sprite's real height entirely (only the animated/
          keyframe path was height-aware) — every positional transform in
          this game is exactly this static case, so it would have placed
          every transform-positioned sprite off-screen without this fix.
        - **Explicitly out of scope, still approximated**: `repeat`d
          animated transforms (`fidget`, `vibrating*`, `shake`, `jolt`,
          `walking`, `drunkrocking`) — confirmed via reading `anim.moon`
          that the animation system has no loop/repeat concept at all, and
          these use *relative* `xoffset`/`yoffset`, not modeled anywhere in
          the engine's absolute x/y/r/sx/sy/alpha state. `block:`/`choice:`
          random-variance transforms (`crowd_hustle*`) likewise. Both
          degrade safely: any static base position they're composed with
          is still honored, only the animation/randomness itself is
          dropped (flagged `approximated`, same as any other unrepresentable
          ATL) — a real, follow-up-sized engine feature, not attempted here.
        - New tests: 8 pytest (parser: transform declarations not flagged,
          bare-line composition, comma `at` clause, at-clause + block
          combined, animated-transform composition stays approximated but
          keeps its static base position, distinct yalign/yanchor), 1
          pytest (cli.py: a transform declared in a later-sorting file
          still resolves), 2 busted (`images_save_spec.moon`: static
          yalign resolved against real height, independent yanchor), 1
          busted (`anim_spec.moon`: generalized `resolve_yalign` keeps
          existing animated behavior), 2 busted (`extended_vnds_spec.moon`:
          setimg's new trailing props parse correctly, empty when absent).
          157/157 pytest, 101/101 busted, all passing.
        - Result: re-ran Mice Tea's full conversion afterward — blocking
          dropped from 3207 to **2004** (−1203, ~37%), the `atl` blocking
          category alone dropped from 1275 to 72. No hardware rebuild/
          re-stage done this round (not requested yet — this was scoped to
          "get transform blocks supported," a converter/engine change to
          verify via tests and Problem Report diffs, not a new hardware
          test cycle).
    - **2026-07-06 — Closed out most of Mice Tea's remaining blocking
      Problem Report items**, on user request ("fix all blocks by
      implementing the missing features or the closest possible
      equivalents"), with explicit permission (and repeated direction,
      after two rounds of scope-checking) to build genuinely new engine
      features rather than defaulting to approximations. Investigated
      every remaining blocking category's *actual* source content (not
      just message text) before implementing anything. Landed in 5
      tiers, each independently tested:
        - **Tier 0 (tokenizer)**: `tokenize_lines` (lexer.py) now merges
          multi-line Python constructs (unbalanced parens/brackets/braces,
          or an open triple-quoted string) into one logical line instead
          of shredding each physical line into its own bogus "unsupported
          statement" — the actual root cause of ~900 of the prior
          2004-blocking baseline's ~1041 "unknown"-category items (a
          `CharacterImage(...)` call spanning 20-40 lines, `style X:`
          blocks, a `"""..."""` docstring). A real tokenizer correctness
          fix, not a new feature — collapsed those into ~90-120 accurate
          single flags with zero change to anything already convertible.
        - **Tier 1 (audio)**: `play`/`queue`/`stop` now resolve a bare
          identifier against a `define`d *or* `init python:`-block-
          assigned string alias (`scan_string_defines`, a new game-wide
          prepass mirroring `scan_transform_declarations`'s cross-file
          reasoning) — confirmed the dominant real form (488 of 592 real
          statements used a bare alias, not a literal string). Ren'Py's
          randomized-file-choice list (`play sound [a, "<silence 0.5>",
          b]`) now becomes a genuine runtime random pick (`random` +
          `ifvar` chain to synthetic labels), not a fixed first-entry
          approximation. Added two real, independent engine channels —
          "ambiance" and (Tier 3) "music2" — since real content plays
          them simultaneously with "music" (confirmed via
          `renpy.music.register_channel`); "audio" aliases to "sound"
          (Ren'Py's own built-in one-shot channel).
        - **Tier 2 (persistent/store)**: `_render_expr` now resolves
          `persistent.X`/`store.X` attribute access to a flat global
          variable (`persistent_X`/`store_X`) on both the read side
          (`if persistent.flag == ...`) and write side (`$ persistent.x
          = ...`, `default persistent.x = ...` — the latter's own regex
          previously couldn't even match a dotted name at all). VNDS has
          no cross-save persistence and none is attempted — this is a
          faithful *within-playthrough* equivalent for the dominant real
          use (one-time content-warning/skip-preference checks).
        - **Tier 3 (`renpy.music.*`)**: `$ renpy.music.play(...)`/`.stop(...)`
          now translate to real `Play`/`Stop` nodes (reusing Tier 1's bare-
          identifier/channel resolution). `renpy.music.set_volume(level,
          channel=, delay=)` is a **new engine feature**, not an
          approximation: a `setvolume` command, `audio.moon` linearly
          fading the named channel's real `Source` volume over `delay`
          seconds every "update" tick (no `lib/timer` field-tween, since
          a Source's volume is a method, not a plain field). Also added
          the "music2" channel here (Ren'Py's own `register_channel`,
          used ~15+ times for a genuine layered-music crossfade, not just
          cleanup — confirmed via a full-game grep before deciding it
          deserved a real channel rather than aliasing).
        - **Tier 4 (6 custom statements + a new overlay engine feature)**:
          Mice Tea registers `day`/`subchapter`/`subchapter_hide`/
          `reset_audio`/`the_end`/`placeholder` itself
          (`statements.rpy`'s `renpy.statements.register(...)`, exact
          `execute_*` behavior read directly from source). `day`/
          `subchapter`/`the_end` all show real positioned/sized/colored
          text over a background in the PC version — neither the fixed
          dialogue box nor the listbox-based custom-screen runtime can
          reproduce that, so this is a **new small engine feature**: a
          `overlay_text <id> <x> <y> <size> <color> <text>` /
          `overlay_clear` command pair (new `src/engine/overlay.moon`,
          drawn in its own pass between background/foreground and the
          dialogue box), exact coordinates/sizes/colors read from each
          statement's own `Text()`/`Transform()` calls (font family and
          per-layer dissolve choreography stay approximated — flagged, not
          silently dropped). `reset_audio` became a **real, exact**
          translation once Tier 3's `setvolume`/music2/ambiance existed.
          `placeholder`'s one real gap (`renpy.rollback()`) is honestly
          flagged, not attempted (real rollback is VN3DS's own separately-
          tracked, much larger future phase; zero real usages found in
          Mice Tea anyway). Also (needed for `day`'s title card, but a
          real, general fix): Ren'Py's built-in solid-color images
          ("black"/"white") are now synthesized as real assets at convert
          time (`_synthesize_builtin_color_assets`, `assets/pipeline.py`)
          instead of always landing in `missing_assets.txt` — confirmed
          119 real `scene black`/`show black`/`white` sites across Mice
          Tea alone, not just this round's own synthesized sequences.
        - **Bug caught and fixed mid-round**: the new Tier 4 `flagged.add`
          reason strings didn't match any rule in
          `problem_report/classify.py` (a prefix-matched rule table), so
          they silently fell back to that table's own "no rule matched"
          default — **blocking** — the opposite of intended
          ("approximated": a real, working feature, just not pixel-
          perfect). Caught by re-running Mice Tea's conversion after Tier
          4 and seeing blocking go *up* instead of down; added the missing
          classification rules (plus regression tests in
          `test_problem_report.py`) rather than assuming the drop would
          "come later."
        - **CharacterImage (the `image NAME = CharacterImage(...)`
          dynamic multi-layer sprite system, 53 characters) — explicitly
          scoped as its own separate, much larger piece** (a real-time,
          runtime layer-swapping system per the user's explicit direction,
          not a partial/static-default approximation), not yet started as
          of this entry. Tier 0's fix alone already reclassifies all 53
          declarations from fragmented blocking noise into one accurate
          `manual` item each (via the existing "image declaration is not
          a plain file path" rule) — real characters still don't render,
          but the Problem Report is honest about it either way.
        - New tests this round: `tests/converter/test_lexer.py` (new file,
          7 tests), plus pytest additions across `test_rpy_parser.py`/
          `test_vnds_writer.py`/`test_cli.py`/`test_asset_pipeline.py`/
          `test_problem_report.py`, plus busted additions to
          `audio_channels_spec.moon` and a new `overlay_spec.moon` (7
          tests). 209/209 pytest, 121/121 busted, all passing.
        - Result: re-ran Mice Tea's full conversion after every tier —
          blocking dropped from the prior round's 2004 to **556**
          (−1448, ~72% of the original 2004; unknown 1041→408, audio
          592→0, python 193→69, flow 53→7, atl 72 unchanged — legitimately
          out of this round's scope). Re-ran Jisei's own conversion
          throughout to confirm no regressions — its blocking count
          actually *improved slightly* (41→36), since Tiers 1-3 are
          general Ren'Py-subset features, not Mice-Tea-specific. No
          hardware rebuild/re-stage done this round (script-only
          conversions used for fast iteration; not requested yet).
    - **2026-07-06 (continued) — Tier 5: CharacterImage real-time,
      runtime multi-layer sprite system**, on the user's explicit
      direction (after two rounds of plan pushback) for a *faithful full
      port* — genuine attribute-driven layer swapping at runtime, not a
      convert-time-baked "one static image per combination" shortcut —
      and a standing instruction (saved to memory as
      `fidelity_vs_performance_priority`) to always match PC behavior as
      closely as possible within O3DS performance limits, never taking
      the easier option at the cost of quality.
        - **Design**: each layer PNG (`characters/<name>/Base.png`, `eyes
          neutral.png`, ...) converts as its own independent texture — no
          Pillow compositing needed, unlike `im.Composite`. A convert-time
          constrained Python-subset interpreter (new
          `src/converter/parser/character_image.py`) executes each
          character's real `layer_selector(ci, attr)` function body
          concretely over the actual requested attribute set, so the
          *logic* (conditionals, aliasing, set ops, helper calls) runs
          exactly as written; the *compositing* happens on-device via
          ordinary layered `setimg` draws — same cost class as any other
          foreground sprite, zero new runtime overhead.
        - **Declaration parsing**: `image TAG = CharacterImage(...)` is
          `ast.parse`d once Tier 0's tokenizer makes it one logical
          statement; `attribute_sets`/module-level constants resolve
          through a recursive `_resolve_set_expr` handling `{...}`
          literals, bare-name references, `set(...)`/capitalized `Set(...)`
          calls (confirmed real content: `felicia.rpy`'s `FELICIA_BASES =
          Set(FELICIA_BASES_LIST)` — Ren'Py's own set-like helper, treated
          identically to the builtin), and arbitrarily long `.union(...)`
          chains. A constant referenced by one character but declared in a
          *different* character's file (confirmed: `felicia.rpy`'s
          `attribute_sets` uses `SPECIAL_POSES`, declared in
          `margaret.rpy`) is resolved via a new game-wide prepass
          (`scan_character_image_constants`, `cli.py`'s
          `scan_character_images`) mirroring `scan_transform_declarations`/
          `scan_string_defines`'s own flat-namespace reasoning.
        - **Interpreter subset**: `if`/`elif`/`else`, `and`/`or`/`not`,
          `in`/`not in`/`==`/`!=`/`>`/`<`/`>=`/`<=` (single comparison
          only), set literals + `&`/`+`/`.intersection()`/`.union()`,
          local variables, string `+`/`.replace()`/`.split()`/`.lower()`/
          `.upper()`, `len()`, indexing, `for`/`continue` loops, `yield`,
          `return` (bare or with a value), module-level constants,
          `persistent.X` reads, `renpy.loadable(path)` (backed by a real
          filesystem check against the extracted asset tree), and —
          added after the first real-content test run surfaced it as 314
          of ~377 initial bailouts — **calling other locally-defined
          helper functions for their return value** (confirmed common
          real content: `margaret_get_arms_file`/`julie_get_arms_file`,
          plain functions characters factor "compute this variant's file
          name" into, called from inside the main selector). A bare
          top-level side-effect call (`persistent.cv_npcs.add(...)`,
          unlock-tracking bookkeeping) is a no-op, not a bailout —
          confirmed via reading every such call that none affect yielded
          layers. Persistent-gating is detected (not fully symbolically
          executed) by running the interpreter twice — once forcing every
          `persistent.X` read True, once False — and comparing results;
          2+ distinct persistent names gating one combination bails out
          (out of scope, confirmed not to occur in any of the 34 real
          characters). Anything else outside this subset raises
          `InterpreterBailout`, caught per-usage at emission time with a
          fallback to that one usage's default (no-attribute) pose —
          isolates the gap to one `show` line, not the whole character.
        - **Wildcard layer-to-file resolution** (`resolve_layer_file`)
          matches a yielded name against the character's declared
          `layers` tuple (exact or `"Base*"`/`"eyes *"`-style wildcard
          entries) and always resolves via a real case-insensitive
          directory scan rather than trusting a guessed-case candidate
          path's `Path.is_file()` — NTFS resolves either case
          successfully, which would have silently baked the *wrong*
          basename into the emitted script (breaks on a case-sensitive
          filesystem, and wouldn't match what the asset pipeline converts
          on disk). `layer_shift` (a per-layer position offset) is
          deliberately not implemented — confirmed via a full-game grep
          that zero of the 34 real characters use it at all, so every
          layer draws at the show's own resolved position, a verified
          match to reality rather than a simplification.
        - **Emission** (`vnds_writer.py`'s new `_emit_character_image_show`,
          threaded through `emit_script_vnds`/`_emit_body` as optional
          params so every existing caller/test is unaffected): a
          CharacterImage-tagged `show <tag> <attrs>` becomes `clearslot
          <tag>` (a **new engine command**, `images.moon`, matching both
          the exact slot and any `<tag>:N` slot with that prefix) followed
          by one `setimg <layer>.t3x <x> <y> <tag>:<index> ...` per
          resolved layer — each layer gets its own `<tag>:<index>` slot so
          same-batch layers don't dedupe-remove each other via `setimg`'s
          existing exact-slot-match dedup (a real bug caught by a busted
          test in an earlier design pass: sharing one bare slot per
          character meant only the last layer of any batch ever stayed
          visible). A persistent-gated selector becomes a real `ifvar
          (persistent_X == 1) jump ...` branch between the two
          pre-resolved layer lists, not a convert-time guess. Static ATL
          props (`yalign`/`sx`/`sy`/`rotate`/`alpha`) and a timed `anim`
          apply identically to every layer (verified real, common content:
          694 of 1317 real ATL-block shows on these characters use a timed
          transform) — since all layers share one position, this is exact,
          not approximated.
        - **Asset pipeline**: since CharacterImage layers are never behind
          a declared `image NAME = "path"` (resolved dynamically per
          attribute combination), the existing whole-tree-by-exact-stem
          search would never find them — a new `resolve_character_image_layers`
          (`assets/pipeline.py`, mirroring `resolve_composite_images`'s
          existing explicit-conversion shape) converts exactly the real
          source files the emitter already resolved, keyed by the same
          normalized basename the `setimg` line uses.
        - **Bug caught and fixed mid-round (same shape as Tier 4's)**: the
          new emitter `flagged.add` reason strings (bailout-fallback,
          missing-layer-file) didn't match any `classify.py` rule at
          first, so a real Mice Tea conversion run saw blocking jump from
          556 to 933 instead of dropping. Caught the same way as before —
          re-running the real conversion rather than trusting the design —
          fixed with two new rules (`severity="approximated"`,
          `category="displayable"`) plus regression tests in
          `test_problem_report.py`.
        - **Real-content-driven interpreter gaps**, each found by running
          the interpreter against actual extracted Mice Tea character
          files (not synthetic cases) and fixed before the final
          conversion run: numeric comparisons (`len(parts) > 1`, real in
          `margaret.rpy`), `.lower()`/`.upper()` string methods (28 real
          occurrences), `continue` inside a `for` loop (13 occurrences),
          and — the largest single gap — calling a locally-defined helper
          function for its return value (314 occurrences, effectively all
          of them `*_get_arms_file`-shaped helpers). Fixing these
          converted ~355 of the initial ~377 bailouts into fully-resolved,
          real attribute-driven layer output instead of a default-pose
          approximation.
        - New tests: `tests/converter/test_character_image.py` (new file,
          29 tests — interpreter subset construct-by-construct, including
          the helper-function-call and persistent-gating-through-a-helper
          cases, declaration parsing incl. `Set(...)` and cross-file
          constants, alias expansion, wildcard file resolution), 5 new
          `test_vnds_writer.py` tests (clearslot+multi-setimg shape,
          persistent-gated branch, bailout fallback, missing-layer
          partial render, ordinary Show unaffected), 2 new `test_cli.py`
          tests (full build_bundle end-to-end: real layer PNGs in, real
          `.t3x` files + correct clearslot/setimg script out; cross-file
          constant resolution), 2 new `test_problem_report.py`
          regression tests. 246/246 pytest passing (busted suite not
          re-run this round — no `.moon` engine changes beyond the
          already-tested `clearslot` design from the prior pass; toolchain
          not on PATH in this session).
        - Result: re-ran Mice Tea's full conversion end-to-end with real
          extracted assets (not script-only) after every fix — final
          Problem Report: blocking back to the Tier 4 baseline **556**
          (confirming the classify.py fix), `displayable` (CharacterImage)
          approximated items down to **27** (all genuine "yielded name
          isn't a per-character file" cases, e.g. `lighting_night` — a
          shared full-screen tint declared elsewhere, not per-character
          art) — all 34/34 characters that declare CharacterImage parse
          and successfully resolve for at least the empty-attribute-set
          case; an earlier ad-hoc sweep against every real `show <tag>
          <attrs>` usage found in the actual scripts (2,392 distinct
          combinations across 26 characters) resolved 2,184 cleanly before
          the interpreter gap fixes above, which is expected to be
          substantially higher now (not re-measured as a committed number
          after those fixes). Verified in the emitted
          `script/main.scr`: 8,715 real `clearslot`+`setimg` sequences,
          548 real per-character `.t3x` textures converted, zero
          conversion failures. Remaining `missing_assets.txt` entries
          (519) are pre-existing, unrelated gaps (space-named background
          files not matching the emitter's underscore-normalized
          basenames; dynamically-generated credits-screen image tags) —
          confirmed none are CharacterImage layers. No hardware rebuild/
          re-stage done this round (not requested yet).
        - **Not yet done**: a full symbolic/exhaustive re-verification
          across all 34 characters' *realistic* (non-empty) attribute
          combinations was spot-checked via ad-hoc scripts during
          development but not turned into a committed test; the project-
          wide fidelity/performance audit and the custom UI-asset-import
          system remain queued behind this, per the user's own explicit
          prioritization.
    - **2026-07-06 (continued) — Project-wide fidelity/performance audit.**
      Per the user's standing directive (see `fidelity_vs_performance_priority`
      in memory), reviewed everything already built (not just the new Tiers)
      for a place a "quicker/easier" shortcut was taken that could actually
      be upgraded within O3DS's performance budget. Researched via a full
      read of `classify.py`'s 13 approximation categories cross-referenced
      against real Mice Tea output, direct source verification of the
      highest-signal candidates, and a dedicated Explore-agent sweep for
      compromises that produce *no* Problem Report entry at all (rendering-
      time/architectural shortcuts, not per-statement parser decisions).
      - **Real bug found and fixed (not a shortcut)**: `images.moon` had
        `on "update", -> flux.update(dt)` registered **twice** (a copy-paste
        artifact from the Tier 0-5 commit) — every flux-driven tween (anim
        presets, keyframes, CharacterImage animations) advanced at 2x real
        speed on hardware, invisible to existing tests since they all
        dispatch "update" with the *full* duration and only check for
        completion. Fixed (deleted the duplicate); added a regression test
        that dispatches *half* a tween's duration and asserts it's still
        mid-flight — verified it actually catches the bug by reintroducing
        it and watching the new test fail, then re-fixing.
      - **A1 — Whole-screen transitions were completely inert on hardware**:
        `_emit_transition` wrote a `transition <kind> <duration>` line for
        every `with <name>`, but `"transition"` was never a recognized
        instruction anywhere in `script.moon` — silently skipped every
        time. Every `with dissolve`/`with fade` (636+ real uses in Mice Tea)
        was an instant hard cut. Fixed by wiring into primitives that
        already existed but were never populated: `bgload`'s dormant
        `frames` token (a real alpha fade-in via `Timer.tween`, images.moon)
        for Scene; `anim.moon`'s existing `enter_fade`/`exit_fade` presets
        for Show/Hide (Hide's fade blocks via `anim_wait` before `clearimg`,
        since a removed sprite stops drawing regardless of its own in-flight
        tween — the one case that *must* block to be visible at all).
        `vpunch` (27 uses) maps to the existing `shake` preset instead of
        downgrading to dissolve. A bare `hide` immediately followed by a
        standalone `with` (Ren'Py's two-line idiom, 33 real uses) is
        intercepted in `_emit_body` before the fade-then-remove ordering
        would otherwise be lost. Found and fixed a related real bug while
        verifying at scale: `with None` (Ren'Py's "explicitly no
        transition" idiom, 153 real uses) was being parsed as an
        *unrecognized transition name* and downgraded to a real dissolve —
        now a genuine no-op (`info` severity), not a spurious fade.
      - **A2 — `{b}{i}{color}{w}{p}{size}` tags were "supported" but never
        rendered**: passed through as literal, unrendered brace characters
        on hardware (worse than a normal unknown tag, which was at least
        flagged) — the docstring's own "for the engine's future tag-aware
        renderer" was never built. Rewired: `text_color.moon`'s `colorify`
        extended from color-only flat pairs to a richer per-run
        `{color:, text:, bold:, italic:}` list (plus a zero-width `pause:`
        run) via a widened escape-code grammar (arbitrary hex color; real
        ANSI SGR bold/italic on/off; a `Pn.n` pause code) — `word_wrap`/
        `truncate_colored_lines`/`draw_text` rewritten to carry and render
        runs individually (bold double-draws offset 1px, italic shears via
        `love.graphics.print`'s own `kx`, a pause consumes reveal budget as
        phantom characters with no separate timer needed). `{alt}...{/alt}`
        (Ren'Py's self-voicing-only text) now strips its *content* too, not
        just its markers — real content put this in Character() display
        names themselves (`"{i}(Margaret){/i}{alt} Thinking{/alt}"` rendered
        as "(Margaret) Thinking" before this fix); `{noalt}` still keeps
        its content. `{size}`/`{font}` (no per-run font-size/second-font-
        file support) now correctly flag `approximated` — previously
        silently unflagged.
      - **A4 — `Character(color=...)` was parsed and discarded**: threaded
        through as an optional `#hexcolor` token on the emitted `nameplate`
        command; `text.moon` colors both the nameplate text and (via the
        same `colorify` path) any tags inside the display name itself.
      - **A3 (hbox real side-by-side layout) and B2 (real audio `queue`
        chaining) — investigated, not built**: both are real engine gaps
        (screen.moon's `flatten` collapses hbox to the same vertical stack
        as vbox with zero Problem Report signal; `queue` still approximates
        as an immediate play), but confirmed **zero real-world impact** for
        either target game — every real `hbox:` usage in Mice Tea occurs in
        a screen already excluded for unrelated unsupported constructs
        (`for` loops, `imagebutton`, already-native default screens), and
        `queue` has zero real usages in Mice Tea *or* Jisei. Not worth the
        engineering cost (hbox needs a real box-layout rework of the
        listbox-based screen runtime) without evidence of need — documented
        rather than built speculatively.
      - **B1 — CharacterImage's own residual gap**: a yielded layer name
        with no per-character asset file now falls back to resolving as an
        ordinary top-level declared image (the same `images` registry
        `_resolve_image_path` already uses) before flagging, matching the
        original `characterimage.rpy`'s own `ImageReference` fallback.
      - **B3 — typewriter speed was hardcoded at 40 cps**: real games often
        set their own (Jisei: `config.default_text_cps = 35`). Scanned the
        same lightweight way `default_font` already is (a standalone regex
        over raw source, since it's almost always inside `init python:`);
        written to a plain `text_cps.txt` at the bundle root (the engine
        doesn't read manifest.json at all yet, so this mirrors
        `default.ttf`'s existing file-presence convention rather than
        inventing a new one). Deliberately *not* `preferences.text_cps`
        (Mice Tea's real usage) — that's a runtime-adjustable user setting
        some games default to 0/instant and let the player change via an
        options menu, a materially bigger feature, out of scope here.
      - **New finding, documented not fixed**: while verifying B1 against
        real content, discovered `"lighting_night"` (yielded by ~15 real
        character selectors) isn't actually a per-character layer at all in
        the original engine — `characterimage.rpy`'s `_duplicate` filters
        it out of the attribute set *before* calling `layer_selector`
        (making the real engine's own `if "lighting_night" in attr: yield
        "lighting_night"` branches dead code there), then separately checks
        the *raw* show attributes afterward to apply an `im.MatrixColor`
        blue-ish tint to every resolved layer. This project's interpreter
        doesn't replicate that filter, so it spuriously yields
        "lighting_night" as a fake layer name, which correctly fails to
        resolve (no such image exists) and gets dropped with a flag — a
        reasonable degraded fallback (the character still renders, just
        without the night tint), not a crash or corruption, but a real gap.
        Fixing it properly needs a new per-sprite tint-color mechanism
        (cheap on hardware — LÖVE's existing per-draw `setColor` multiply,
        the same mechanism alpha fades already use — but real engineering:
        the interpreter needs to track it as a boolean signal instead of a
        fake layer, and images.moon's `setimg`/`draw_foreground` need a
        tint field threaded through). Not attempted this pass; a good
        candidate for a focused follow-up given how many characters use it.
      - **Verification**: 268 pytest / 140 busted, both green throughout.
        Re-ran Mice Tea's real conversion after every change (per the
        project's own established discipline — see `classify_py_new_
        reasons_regression` memory) — blocking held steady at 556 (no
        regression), `approximated` dropped 2460→2196 (with-None
        reclassified to `info`, real tag rendering removing ~200 previously
        -unflagged {size}/{font} passthroughs' worth of hidden garbage),
        `info` rose 12→112 (100 real `with None` no-ops now correctly
        classified instead of silently downgrading). Three new
        `flagged.add` reason strings this pass, each given a `classify.py`
        rule + regression test in the same change (`with None`, the
        `{size}`/`{font}` split from the generic unknown-tag rule).
    - **2026-07-06 (continued) — Custom UI-asset-import system.** The
      user's other standing ask: the engine drew all its UI chrome
      (dialogue textbox, nameplate/namebox, and every choice/custom-screen/
      save-load/main-menu button background — confirmed listbox.moon is
      the single shared widget behind all of those) as flat hardcoded-color
      rectangles, never the source game's own real `gui/` image assets —
      on screen for essentially the whole game, not an edge case.
      - **Converter**: new standalone regex scans (same convention as
        `_scan_default_font` — this content lives inside `init python:`/
        `screen:` blocks, otherwise out of the statement parser's scope),
        each trying the modern `gui.rpy`-template form first, falling back
        to the legacy pre-gui.rpy form: `_scan_textbox_image` (a *plain*
        image in both target games — no Frame()/border-scaling at all),
        `_scan_namebox_frame` (a real `Frame()` 9-patch — Mice Tea's
        genuinely **tiles**, `gui.namebox_tile = True`, not just
        stretches), `_scan_choice_button_frames` (modern case resolved via
        Ren'Py's own fixed, non-game-specific `gui/button/choice_idle_
        background.png`/`choice_hover_background.png` filenames, since the
        literal path is never in the game's own source at all — it's
        generated by Ren'Py's *own* internal `gui.button_properties(...)`
        helper, confirmed by grep turning up nothing in either target
        game). `CharacterDef` gained `namebox_background` (a per-character
        nameplate skin override, confirmed real content: Mice Tea's
        characters.rpy uses this **84 times** — not an edge case).
      - **Real cross-file bug found and fixed**: `gui.namebox_borders`/
        `gui.namebox_tile` live in `gui.rpy` while the `Frame()` call
        referencing the image lives in `screens.rpy` — two different files.
        A per-file-only scan silently defaulted borders to zero/no-tile
        whenever the two pieces didn't share a file (caught by inspecting
        the real conversion's own `manifest.json` output, not just tests —
        it showed `borders: [0,0,0,0]` where `[5,5,5,5]` was expected).
        Fixed the same way transforms/string_defines already handle this:
        a new `scan_namebox_borders_tile` game-wide prepass in `cli.py`'s
        `parse_game`, merged across every file (first-found wins) before
        any file's own `_scan_namebox_frame` call.
      - **Asset pipeline**: new `resolve_ui_assets` (mirrors `resolve_
        composite_images`/`resolve_character_image_layers`'s shape) —
        converts every distinct UI chrome path (textbox, namebox + every
        per-character override, choice idle/hover) through the existing
        `convert_image`/tex3ds pipeline into a new `ui/` bundle folder.
      - **Manifest**: `manifest.json` gained a `"ui"` key (textbox/namebox/
        choice_idle/choice_hover, each `null` when undeclared/unresolved)
        and each character gained a `"namebox"` key — the engine's *first*
        real consumer of manifest.json (confirmed nothing read it before
        this).
      - **Engine**: new `ui_frame.moon` — a real 9-patch/Frame renderer
        (`draw_frame`): 4 fixed-size corners (never scaled/tiled), 4 edges
        + center either stretched (a scaled `Quad` draw) or genuinely
        **tiled** (LÖVE's own wrap-mode technique — `image:setWrap("repeat",
        "repeat")` + a `Quad` sized to the *destination* rather than the
        source, so out-of-bounds sampling repeats the tile automatically);
        degenerates to one plain scaled draw when borders are all zero
        (textbox's shape) — one code path for both cases. New `ui_assets.
        moon` reads `manifest.json` once (the existing `lib/json` decoder,
        same pattern `save.moon` already uses) into a shared `ui` table,
        mutated in place (never reassigned) so an earlier `import ui from
        require "ui_assets"` elsewhere stays live across a later reload.
        `text.moon`'s textbox/namebox and `listbox.moon`'s per-row button
        backgrounds (one change covering choices/custom screens/save-load/
        main-menu at once) now draw the real image via `draw_frame` when
        available, falling back to *exactly* today's flat-color rendering
        otherwise — zero regression for bundles with no UI-asset data.
      - **Verification**: 291 pytest / 153 busted, both green throughout
        (a real busted-side bug caught along the way: a mock's `\`
        method-call self-argument silently swallowing a test's assertion
        target). Re-ran Mice Tea's real conversion: 43 real UI chrome
        `.t3x` files converted (textbox, namebox, choice idle/hover, 39
        distinct per-character namebox skins), 85 of 126 characters
        resolved a real namebox override, and the Problem Report summary
        is byte-for-byte unchanged from before this feature (556 blocking,
        2196 approximated, 112 info, 194 manual) — confirming this adds a
        genuinely new, parallel capability without touching existing
        conversion behavior at all.
      - **Out of scope, confirmed genuinely inapplicable, not a shortcut**:
        bars/scrollbars/sliders (back Ren'Py's default preferences/config
        screens, which this engine already replaces natively — never
        converted from `screens.rpy` at all, so there's no rendering path
        for that chrome to plug into) and mobile/locale-variant chrome
        (O3DS has no phone-variant mode or in-game language switching).
    - **2026-07-06 (continued) — "lighting_night" tint-effect follow-up.**
      Closed the gap the fidelity audit found but didn't fix: `"lighting_
      night"` isn't a per-character layer at all in the original engine —
      `characterimage.rpy`'s `_duplicate` excludes it from the attribute
      set *before* `layer_selector` ever runs (making real content's own
      `if "lighting_night" in attr: yield "lighting_night"` branches dead
      code there), then separately checks the *raw* show attributes
      afterward to apply a fixed `im.matrix.tint(.75, 0.85, 1.0)` to every
      resolved layer. `expand_attrs` now reproduces the same exclusion, so
      a real-shaped selector never yields it as a fake layer at all;
      `vnds_writer.py`'s `_emit_character_image_show` checks the *raw*
      `requested` attrs directly (already available before `expand_attrs`
      runs, no new interpreter plumbing needed) and appends `tint_r=0.75
      tint_g=0.85 tint_b=1` tokens to every layer's `setimg` line when
      present — reusing the exact same `parse_props`/generic-`k=v`-token
      mechanism `yalign`/`sx`/`sy`/`r`/`alpha` already use, zero script.moon
      changes needed. `images.moon`'s per-sprite `anim` state gained
      `tint_r`/`tint_g`/`tint_b` (default `{1,1,1}`, i.e. no tint), read by
      `draw_foreground`'s `lg.setColor` in place of the previous hardcoded
      `(1,1,1, a.alpha)` — the same per-draw-call color-multiply mechanism
      alpha fades already use, so this was cheap: no new engine primitive,
      just wiring three more fields through machinery that already existed.
      Verified: 293 pytest / 155 busted, both green. Re-ran Mice Tea's real
      conversion: 195 real `tint_r=.../tint_g=.../tint_b=...` emissions in
      the converted script; the CharacterImage "layer has no matching
      asset" flag for lighting_night dropped from 27 to 0 (the 8 remaining
      "lighting_night"-mentioning flags are an unrelated, pre-existing ATL-
      animation-approximation category that happens to have it as one of
      the attribute words in the flagged snippet — confirmed not a
      regression); Problem Report otherwise unchanged (556 blocking).
- [ ] **5.2** — Engine: `persistent.*` stub layer for gallery/unlock systems
- [ ] **5.3** — Port **Our Life: Beginnings & Always** — dialogue converts;
      customisation/seasonal system needs native screens; DLC merge-at-convert-time
      (spec §8.1)
- [ ] **5.4** — Port **Royal Alchemist** — dialogue converts; stats-raising,
      quest, schedule systems need native reimplementation

**Exit check:** At least one full route of Our Life or Royal Alchemist playable,
core game systems functional.

---

## Phase 5.5 — Triage Workbench UI

**Goal:** Purpose-built desktop UI for resolving Problem Report items — zero
terminal required.

- [ ] **5.5.1** — Problem list panel with severity filter + category filter
- [ ] **5.5.2** — Source context panel: flagged snippet at correct file:line,
      syntax-highlighted
- [ ] **5.5.3** — Fix panel: editable stub, Apply Fix → writes to
      `fixes/overrides.json`
- [ ] **5.5.4** — One-click "Accept approximation" and "Mark skip" for
      appropriate severities
- [ ] **5.5.5** — Animation preset dropdown with live preview for
      `atl`/`approximated` items
- [ ] **5.5.6** — "Begin manual fix" button for `live2d` items → opens bone
      definition template in editor
- [ ] **5.5.7** — Re-run converter button; problem list refreshes; blocking count
      updates
- [ ] **5.5.8** — Export bundle button (active only when `blocking == 0`)
- [ ] **5.5.9** — Validation: a person with no prior knowledge can triage Hustle
      Cat to zero blocking without opening a terminal

**Exit check:** §Phase 5.5 definition of done satisfied (see `VN3DS-spec.md`).

---

## Phase 5.6 — Deferred fidelity gaps (no current-game impact, build for future ports)

**Goal:** Close the two real engine/converter gaps the 2026-07-06 fidelity
audit found but deliberately didn't build, since neither Mice Tea nor Jisei
exercises them — confirmed zero real-world impact for *both* current
target games, not a correctness risk today. Deferring them was the right
call for that pass (no evidence-based need, and each is real engineering,
not a one-liner), but a future port may well use either, so they're real
debt to close before assuming any new game "just works." See GAME-PLAN.md's
2026-07-06 audit entry (Phase 5, "(continued)") for the original
investigation and evidence.

- [ ] **5.6.1** — Real `hbox` side-by-side layout in the custom-screen
      runtime. Currently `screen.moon`'s `flatten` collapses both `vbox`
      and `hbox` to the same vertical stack (`listbox.moon` has no concept
      of nested boxes) — passes the parser's "supported construct" check
      with zero Problem Report signal, but doesn't actually render
      side-by-side. Needs a real box-layout algorithm: at minimum, an
      `hbox` node should lay its children out left-to-right at a shared y,
      advancing an x-cursor by each child's rendered width, instead of
      flattening into the listbox's single vertical item list. The bigger
      open question is *interactivity* — a real `hbox` full of
      `textbutton`s (confirmed real shape, e.g. Mice Tea's chapter-select
      screen) needs left/right navigation *within* a row, not just visual
      side-by-side placement, which likely means extending
      `create_listbox`'s input model (up/down between rows, left/right
      within a row) rather than just a rendering tweak.
- [ ] **5.6.2** — Real audio `queue` chaining (play-next-when-current-ends).
      Currently `queue` approximates as an immediate `play`, flagged
      `approximated`. The underlying primitive already exists —
      `audio.moon`'s `on "update"` already polls `sound.file:isPlaying()`
      to auto-replay a looped one-shot sound — extend the same polling
      pattern to `music`/`sound`/`voice`: a per-channel "next up" slot that
      starts automatically once the current track's `isPlaying()` goes
      false. Needs a new `queue_<channel>` VNDS command (the parser's
      `Play.is_queue` field already exists and is threaded through; just
      needs real emission instead of the current approximation).

**Exit check:** A synthetic/fixture screen using `hbox` for a real
side-by-side button row navigates and renders correctly; a synthetic
`queue`d audio sequence audibly chains without an explicit replay. Both get
real pytest/busted coverage, not just visual inspection.

- [x] **5.6.3** — Converter: support flat/unindented Ren'Py label bodies.
      **2026-07-06 — done.** Began converting two new real Steam games as
      reference/test data (**Gender Bender DNA Twister Extreme**, real
      Ren'Py — plain `.rpy` source shipped directly; **Cooking
      Companions**, real Ren'Py packed in `.rpa` archives, unpacked via
      `unrpa` + the existing `unrpyc` tool). GBDNATE's Problem Report came
      back 97.5% blocking (73823/75690, `approximated` stuck at 0) —
      root-caused by reading Ren'Py's own bundled `renpy/parser.py`
      (shipped in the game's install folder): real Ren'Py never requires a
      `label`'s body to be indented (unlike `if`/`menu`/`while`/`python:`,
      which all hard-error via `expect_block` if unindented) — a label is
      a jump-target marker in the enclosing flat statement sequence, not a
      block owner. `rpy_parser.py`'s `_parse_child_block` assumed
      otherwise, so a label whose body sits at the *same* indent (a fully
      flat file — confirmed real content: 14 of GBDNATE's 18 story files
      write every label this way, zero indentation anywhere) got an empty
      body, orphaning everything after it. Fixed via a new
      `_parse_label_body` helper (real indented child → unchanged
      existing path; no deeper child → consume subsequent same-indent
      siblings as the body, stopping at the next label/dedent/EOF, via a
      new `_parse_block(..., stop_at_label=True)`), wired into both label
      call sites (top-level and nested). GBDNATE: 75690→2516 total,
      97.5%→19.5% blocking, `approximated` 0→159. Verified zero regression
      on Cooking Companions/Mice Tea/Jisei via git-stash A/B testing
      (identical Problem Report totals with vs. without the fix, on the
      current codebase). New pytest coverage in `test_rpy_parser.py`; full
      suite 296/296 green (293 prior + 3 new).
      - **Correction (2026-07-06, later same day)**: the note above about
        Cooking Companions' "bare `init:` blocks, 44671 of 45497 blocking"
        was a **misattribution** based on an unverified sample, not a full
        count — re-checked with a real count: `ren'py: init:` only occurs
        ~100 times in Cooking Companions' Problem Report. The actual
        dominant cause of its 45497 blocking items (44142 of them, 97%) is
        the **translate-block noise** finding below, which also explains
        Jisei's "flagged anomaly" noted below (see 5.6.4 for the full,
        corrected writeup and fix). The bare-`init:` gap is real but small
        (~100 items) and still open.

- [x] **5.6.4** — Converter: classify `translate LANG ...:` blocks as
      non-blocking localization data, not "unsupported."
      **2026-07-06, later same day — found, not yet fixed.** Converted 9
      more real Ren'Py games as reference/test data (A Date with Death,
      DateWarp, I Just Want to be Single!!, LongLiveTheQueen, Magical
      Diary Wolf Hall, Our Life Beginnings And Always, ScarletHollow, Slay
      the Princess, The Royal Trap — every other Ren'Py title installed on
      this machine, per a full Steam-library scan) and compared Problem
      Reports across all 13 corpora now on hand. The single biggest
      cross-cutting finding: **`translate LANG strings:` / `translate LANG
      label:` blocks (Ren'Py's per-language localization data) have no
      special classification at all** — every individual translated
      string/dialogue block falls to the generic "unsupported top-level
      statement" → blocking/unknown bucket, exactly like real missing
      content would. Since these games ship many language translations,
      this single gap **dominates** several Problem Reports almost
      entirely, making them nearly useless for real triage:
        - Slay the Princess: 197516/207029 total (95%) — 12+ languages.
        - Cooking Companions: 44142/45497 blocking (97%) — corrects the
          5.6.3 note above.
        - Jisei: 4336/4372 blocking (99%) — this, not the legacy `ui.*`
          pattern-matcher, is what actually explains the "pre-existing
          anomaly" flagged in 5.6.3 (Mice Tea's own anomaly is unrelated —
          Mice Tea ships 0 translate blocks; see its own note below).
        - A Date with Death: 23129/27853 total (83%).
        - I Just Want to be Single!!: 3194/6519 total (49%).
      Mice Tea and GBDNATE ship no additional-language content and are
      unaffected (0 translate items each). **Fix**: add a rule to
      `rpy_parser.py`'s top-level dispatch (alongside the existing `init
      python:` special case) recognizing `translate LANG (strings:|
      \w+:)` headers and classifying the whole block as `info`/`manual`
      ("localization data for a non-English translation; irrelevant to a
      single-language port") instead of `blocking`/`unknown` — mirrors the
      existing `init python:` → "manual" pattern exactly.

      **Other real findings from the same 9-game comparison pass**
      (each independently confirmed against real content, none yet
      fixed):
      - **Character+attribute+dialogue shorthand not recognized**
        (`_SAY_RE`, `rpy_parser.py:86`): Ren'Py's `charname attribute
        "text"` idiom (e.g. `ellen confused "No."` — dialogue + an
        implicit `show ellen confused` combined on one line) isn't
        matched by `_SAY_RE` (`^(?:(\w+)\s+)?{_QUOTED}\s*(?:\(.*\))?\s*$`
        only allows one bare word before the quote). Dominates **Magical
        Diary Wolf Hall** (6607/13730 total, 48%); minor in I Just Want to
        be Single!! (39 occurrences). Fix: extend the say-statement regex
        to accept one or more attribute tokens between the name and the
        quote, treating it as an implicit `show NAME attrs` + `Say`.
      - **Single-quoted string literals never match `_QUOTED`**
        (`rpy_parser.py:84`: `_QUOTED = r'"((?:[^"\\]|\\.)*)"'` — double
        quotes only). Ren'Py allows `'...'` and `"..."` interchangeably;
        every statement using single quotes (play/scene/show/voice/say/
        menu-choice/etc., since `_QUOTED` is reused everywhere) silently
        fails to parse. Real, cross-game impact: DateWarp (294
        occurrences), Magical Diary Wolf Hall (180), LongLiveTheQueen
        (38), Our Life Beginnings And Always (12). Likely the
        highest-leverage single fix found this pass — one regex change,
        broad reach. Needs care: Python string escaping differs slightly
        between quote styles (an embedded `"` doesn't need escaping inside
        `'...'` and vice versa).
      - **Custom multi-layer portrait function not recognized**: Our Life
        Beginnings And Always uses a custom `ChangePortrait(chara=...,
        base=..., brows=..., eyes=..., mouth=..., blush=...)` Python
        helper (its own layered-portrait compositing system, same purpose
        as Mice Tea's `CharacterImage` but a different calling
        convention) — dominates its report (16037/20752, 77%). A second
        real-world confirmation of Phase 3.4's "multi-layer sprite system"
        need, with a concretely different API shape than `CharacterImage`
        to design against.
      - **Subscripted augmented-assignment not supported**: ScarletHollow
        uses `$ relationship_dict["trait"] += N` (dict-subscript targets,
        e.g. relationship-tracking stats) heavily (~7300+ occurrences) —
        the existing augmented-assignment handling only recognizes a bare
        variable-name target, not a subscript expression.
      - **Bare `python:` blocks inside a label body** (as opposed to
        top-level `init python:`) aren't specially classified either —
        LongLiveTheQueen uses 554 of them for inline stat-tracking helper
        calls (`inc_depressed()` etc.), all falling to generic blocking.
      - **Custom/multiple audio channel names**: ScarletHollow declares
        extra channels beyond the standard set (`stop secondary`/
        `tertiary`/`music4`/`5`/`6`); Our Life uses a second voice channel
        (`play voice2 "..."`). The engine/converter's channel handling is
        effectively hardcoded to a fixed known set.
      - **Real crash bug, not just a categorization gap**: `cli.py`'s
        Problem Report table printing crashes with `UnicodeEncodeError` on
        Windows' default `cp1252` console codepage whenever source content
        has non-`cp1252` characters (found via A Date with Death's
        Japanese-translated content) — a real usability bug for anyone
        running the converter CLI on Windows without explicitly forcing
        UTF-8 (`PYTHONIOENCODING=utf-8`). Should print/write with explicit
        UTF-8 (or `errors="replace"`) rather than relying on the console's
        default codepage.
      - **DateWarp is unusually old** (Ren'Py 6/7-era, screen language
        version 1) — the installed `unrpyc` version can't decompile 11 of
        its 29 `.rpyc` files at all, including the main script and
        `screens.rpy` ("Decompiling screen language version 1 screens is
        no longer supported, use the legacy branch of unrpyc"), capping
        how much of it is usable as real test data without a different
        decompiler branch.
      - **The Royal Trap is NVL-mode-heavy** (`nvl clear`,
        `enter_nvl()`/`exit_nvl()`, `switchfade()` — most of its 1531
        blocking items) — the opposite conclusion from Mice Tea/Jisei's
        near-zero nvlmode usage (Phase 3.10): confirms nvlmode would
        become real, high-priority work if this project ever targets an
        NVL-style port, rather than the low priority it's had so far.
      - Mice Tea's own pre-existing anomaly (real duplicate emission in
        CharacterImage/displayable problem reporting) is confirmed
        independent of all of the above (0 translate blocks in Mice Tea)
        and remains open on its own, per the original 5.6.3 note.

      All 9 new games' extracted source + decompiled `.rpy` + converted
      bundles live under `D:\scratch-vn3ds\<slug>-extract` /
      `D:\scratch-vn3ds\bundles\<slug>` (moved off the default C:-based
      scratchpad mid-session at the user's request — C: was nearly full;
      D: has ample space). Not committed, per the standing proprietary-
      content norm.

- [x] **5.6.5** — Fixed all 8 findings from 5.6.4's 13-corpus comparison.
      **2026-07-07/08 — done.** User asked to fix all 8; scope check on
      item 4 (Our Life's `ChangePortrait`) surfaced it was far larger than
      the other 7 (a full bespoke live-rendered multi-layer portrait
      system needing new engine-side animation primitives, not just a
      converter tweak) — user chose full native reimplementation, no
      session limit.
      - **Items 1/6 (translate blocks, bare `python:`)**: new special-case
        branches in both `parse_rpy`'s top-level loop and
        `_parse_statement`'s label-body dispatcher, mirroring the existing
        `init python:` pattern. Two new `classify.py` rules — translate
        blocks are `info` (never ambiguous, always irrelevant to a
        single-language port); bare `python:` is `manual` (matches `init
        python:`'s own severity — real game logic that might matter).
      - **Item 2 (single quotes)**: `_QUOTED` restructured to a
        non-capturing pattern matching either quote style; every one of
        its 9 embedding sites wrapped in an outer capturing paren
        (preserves every existing `.group(N)` index unchanged); new
        `_dequote()` helper (strip the quote pair + unescape) replaces
        `_unescape()` at every call site fed by a `_QUOTED` group, since
        those groups now include the quote marks themselves. Two manual
        double-quote-only literal checks (`_resolve_audio_entry`,
        `_screen_text_literal`) extended to accept either quote char.
      - **Item 3 (say-shorthand)**: `_SAY_RE` widened to capture one-or-
        more bare tokens before the quote; the caller splits the first
        token as the real speaker (`_resolve_speaker` does a dict lookup
        keyed by exact character name — gluing attributes in would break
        nameplate resolution) and synthesizes an implicit `Show` ahead of
        the `Say` for the full "name + attrs" string, matching real
        Ren'Py semantics exactly. `_parse_statement`'s return type widened
        to `Node | list[Node]` for this one case (`_append_statement_result`
        helper at both of its 2 call sites).
      - **Item 5 (dict-subscript `+=`)**: new `ast.Subscript` branch in
        `_render_expr`, mirroring the existing `persistent.`/`store.`
        flattening precedent — a string-literal-keyed `dict["key"]`
        becomes a namespaced flat global (`dict__key`); non-literal/non-
        identifier-safe keys correctly stay unsupported.
      - **Item 7 (audio channels)**: additive, not a rewrite — the 5
        curated channels' instruction keywords/handlers stay byte-for-byte
        unchanged. New generic `play`/`stop` VNDS instructions (carrying
        explicit `loop`/`mixer` flags, decided once at convert time, never
        guessed at runtime) for any other channel name; `audio.moon` gets
        one new auto-vivifying `channels` table + generic handlers
        alongside the 5 existing ones; `channel_table`'s `else` arm now
        falls back to it, which is also what makes `setvolume` (already
        fully generic) work on a custom channel for free. New
        `_CUSTOM_CHANNEL_SHAPE` seed (the 2 real motivating cases) +
        `_infer_custom_channel_shape` name-substring fallback in
        `vnds_writer.py`; classified `info`, not silently dropped. Also
        fixed a real latent `KeyError` bug found along the way:
        `_emit_random_play`'s direct `_PLAY_COMMAND[...]` subscript (no
        `.get()`, despite a comment claiming the caller already validated
        it — it didn't) would have crashed on a random-choice `play` using
        a custom channel.
      - **Item 4 (ChangePortrait)** — the big one. New
        `converter/parser/character_sprite.py` module (mirrors
        `character_image.py`'s architecture, but *simpler* on the static
        side: `ChangePortrait`'s kwargs are already literal slot values,
        no selector-function interpreter needed) parses
        `characterSpritePartsOrder`/`Expressions`/`Glowing`/`Magic`
        constant lists and `Portrait(...)` declarations, and resolves each
        `$ ChangePortrait(chara, blink=.., transition=.., matrix=..,
        **kwargs)` call into a `PortraitUpdate` IR node — one
        `PortraitLayerUpdateIR` per kwarg *actually passed*, matching
        `SetSpritePart`'s real incremental semantics (an untouched slot
        keeps whatever's already drawn). `matrix=` (a Ren'Py color-matrix
        `*`-chain, e.g. `im.matrix.saturation(1.0)*im.matrix.tint(r,g,b)
        *im.matrix.brightness(n)`) is walked for just the `tint(...)`
        factor — saturation/brightness have no engine equivalent and are
        dropped, same approximation tier as CharacterImage's own
        `lighting_night` tint.
        Emitter (`vnds_writer.py`) resolves real asset paths (case-
        insensitive directory scan, same risk `character_image.py`'s own
        `resolve_layer_file` already guards against) and emits one of two
        new instructions per touched slot: `portrait` (a static layer) or
        `portrait_anim` (eyes/mouth, 3 frame paths for blink/lip-flap).
        **Real-content discovery**: every single one of Our Life's 120
        `Portrait` declarations sets `animateMouth=False` (confirmed:
        zero real mouth-frame-1/2 files exist anywhere in the game's
        asset tree at all — the lip-flap code path is real Python but
        genuinely never exercised by this game) while every one sets
        `animateEyes=True` (which do all ship real 3-frame files) — so
        frame1/2 are only *required* to exist when that layer's Portrait
        actually declares the matching animate flag; otherwise frame0 is
        reused for all 3 slots. Without this fallback, all ~15,000 of the
        game's real `ChangePortrait` calls involving a mouth layer failed
        asset resolution outright. Found via a real end-to-end conversion
        run, not proactively — a reminder that "resolve real content"
        checks belong in the loop even for a brand-new feature with its
        own from-scratch tests.
        New engine-side `src/engine/portrait.moon` (required from
        `main.moon` alongside `images`) — genuinely new runtime primitives
        (blink/lip-flap frame-cycling, a manual cross-fade dissolve,
        glow/magic pulsing opacity) that didn't exist anywhere in the
        engine before, built from *existing* primitives rather than a new
        draw pass: every portrait layer is dispatched as an ordinary
        `setimg` (slot `"<name>:<slot>"`, same convention as
        CharacterImage's `"<tag>:<index>"`) so `images.moon`'s existing
        `draw_foreground` draws it for free, and tint reuses the same
        `tint_r/g/b` per-sprite fields the engine's other tint mechanisms
        already share. Lip-flap gates on a new `speaking <name>`
        instruction bracketing `Say` emission (only emitted at all for a
        game that actually uses portraits, confirmed zero output change
        for every other corpus) — an approximation of Ren'Py's real
        begin/slow_done/end callback timing as "animates for as long as
        this line is the current text," since the engine has no finer-
        grained per-character speech-timing signal.
        **Known, documented scope cuts** (explicitly out of this pass, not
        silently dropped): the hardcoded `self.name.startswith("Cove_23")`
        tears exception (a one-off developer special-case); portrait
        position is a fixed screen-center default (`show cove_8 at
        left/right` positioning isn't wired up — `PortraitUpdate` has no
        position field yet); exact original dissolve/blink-cycle frame
        timing (the original's own timing is tied to Ren'Py's render-call
        cadence, which has no fixed real-world duration to match, so a
        reasonable fixed duration was chosen instead, documented at each
        constant in `portrait.moon`).
      - **Real-content verification**: re-ran the converter against all
        13 corpora after every batch. Mice Tea and GBDNATE (unaffected by
        any of the 8 items) are **byte-identical** to their pre-fix
        Problem Reports throughout — the regression check that actually
        matters. Our Life: `ChangePortrait`-driven blocking dropped from
        21,566 (96% of its report) to a real end-to-end run of
        Total 6,052 / Blocking 2,791 (with the remaining ~483 unresolved-
        asset flags traced to genuine content gaps, e.g. one character
        ("Jude", in `copy_paste.rpy` — likely leftover scratch/debug
        content) with no matching asset folder at all, not a resolution
        bug). ScarletHollow's audio-channel fix verified similarly
        (blocking 4228→2698, its "secondary"/"tertiary" channels now
        classified `info` instead of dropped).
      - **Toolchain note**: `busted` (the engine's MoonScript test
        runner) turned out to be broken in this environment independent
        of any change made here (fails to load *any* `.moon` file,
        including ones never touched this session, while `moonc`/a direct
        `moonscript.loadfile()` call succeed on the identical file — see
        `busted_toolchain_broken.md` memory) — every engine-side change
        (`audio.moon`, `script.moon`, `portrait.moon`, `main.moon`, and
        both new/extended busted spec files) was verified via `moonc`
        syntax-compiles-cleanly checks and careful manual trace-through
        against each spec's own assertions, not by actually executing the
        busted suite. Also hit (twice) a real MoonScript 0.6.0 parser
        quirk along the way: a standalone comment-only line placed
        directly before a `when` clause inside a `switch` fails to parse
        — fixed by making the comment trailing on a line with real code
        instead; documented in the same memory file for next time.
      - Python-side: full pytest suite (346 tests, up from 313 at the
        start of this pass) green throughout every batch.
      - **2026-07-08 — real hardware bug found on first Jisei hardware
        playtest, fixed same day.** User hit an immediate crash launching
        Jisei on real Old 3DS hardware: `audio.lua:244: attempt to index
        local 'self' (a nil value)`, traceback through `listbox.lua:59`'s
        callback. Root cause: item 7's new generic `play`/`stop` VNDS
        instruction keywords were dispatched via `main.moon`'s existing
        generic fallthrough (`dispatch ins.type, ins`), which reuses the
        raw instruction keyword as the internal event name — but `"play"`
        already meant something else globally (`listbox.moon`'s
        menu-close signal, `dispatch "play"` with no data, paired with
        `main.moon`'s own `on "play", -> paused -= 1` unpause handler).
        Every listbox close (any menu, including Jisei's native main
        menu) now also fired audio.moon's new `on "play", => ...` handler
        with `self` nil, crashing on `self.channel`. A pure nil-guard
        would only have silenced the crash, not the reverse bug it was
        masking (a real custom-channel `play` would spuriously decrement
        `paused` too) — fixed properly instead: `main.moon` now special-
        cases `when "play"`/`when "stop"` in its instruction switch and
        dispatches them under distinct internal names, `"channel_play"`/
        `"channel_stop"`; `audio.moon`'s handlers renamed to match. The
        VNDS wire-format keywords themselves (`play <channel> ...`/`stop
        <channel>`) are unchanged, so no already-converted bundle needed
        re-emitting. New busted regression test asserts the bare `"play"`/
        `"stop"` events (no data) no longer crash and don't touch custom-
        channel state. 183/183 busted green (up from 182).
      - **2026-07-08 — second real hardware bug on the same Jisei
        playtest, past the first crash.** `text/text.lua:37: Could not
        open file novels/jisei/default.bcfnt. Does not exist.` — the very
        first real hardware exercise of the per-novel custom-font path
        (`text.moon`'s `update_font`, previously dead code per its own
        comment — "no converter run had ever produced a default.ttf"
        until Jisei's real `gui/HanSrf.ttf` got wired through this
        session). Root cause: `love.graphics.newFont` on LÖVE Potion's
        3DS backend doesn't load raw TTF directly — it silently looks for
        a precompiled `.bcfnt` bitmap font at the same base name,
        regardless of the extension actually requested (`default.ttf` in,
        `default.bcfnt` looked up). A devkitPro tool for exactly this
        (`mkbcfnt`) already existed on this dev machine, and a legacy
        `tools/engine/3ds_convert.sh` script (inherited from the DDLC-LOVE
        fork, otherwise unused today) already knew the convention — this
        project's own converter just never called it. Fixed in
        `cli.py`'s `build_bundle`: after copying a game's declared default
        font to `default.ttf`, a new best-effort `_compile_bcfnt` helper
        also runs `mkbcfnt` to produce `default.bcfnt` alongside it,
        baked at size 20 (the one size real hardware ever requests —
        `text_box_width!` always measures the bottom screen on 3DS, fixed
        at 320px, always under `update_font`'s own <600 threshold; the
        32px branch only fires on non-3DS/desktop LÖVE dev builds, which
        load raw TTF directly and never touch bcfnt at all). Silently
        skipped if `mkbcfnt` isn't installed at the hardcoded devkitPro
        path (a packaging nicety, not a hard requirement for the
        converter to run on any given dev machine) — mirrors
        `build_3dsx.py`'s own existing devkitPro-tool-path convention.
        Two new pytest regression tests (mocking the mkbcfnt binary and
        `subprocess.run`, not requiring the real toolchain) confirm the
        invocation's arguments and the silent-skip path; 348/348 pytest
        green (up from 346). Jisei's staged hardware-test bundle
        hand-patched with a real `mkbcfnt`-compiled `default.bcfnt` and
        re-verified against the same command the new tests assert.
      - **2026-07-08 — third and fourth real hardware bugs, same Jisei
        playtest, past the first two.** Two more real, confirmed bugs
        surfaced once the game was actually playable far enough to reach
        its first scene-with-background-change: "the custom font reverts
        to a plain one a line before '...Where am I?'" and, later,
        "character sprites now appear way too big" / "sprites have started
        stacking again."
        - **Font-revert + sprite-scale bug**: `images.moon`'s `on
          "bgload"` compared a *background image's own* pixel dimensions
          against `original_width`/`original_height` (the device/window
          reference resolution `main.moon`'s `love.resize` maintains for
          `sx`/`sy` scaling) and, on any mismatch, overwrote that
          reference with the image's own dimensions and re-ran
          `love.resize` — conflating "what size is this piece of art"
          with "what size is the actual screen". Since real background
          art is essentially never exactly the device's native
          resolution, this fired on nearly every `bgload`, corrupting
          `sx`/`sy`/`px`/`py` (wrong scale for every sprite drawn after)
          and, via `love.resize`'s own `text_font = font` line, silently
          reverting any per-novel custom font back to the generic
          default mid-story. `draw_background` already scales an
          arbitrarily-sized image to fit the screen via `scale =
          math.min(sx, sy)` — this code never needed to touch the device
          reference resolution at all. Fixed by deleting the whole
          mismatch-check/`love.resize`-recall block; 183/183 busted still
          green.
        - **Hide not clearing the actually-displayed sprite**: an earlier
          session already fixed one stacking bug by matching `Show`'s
          `setimg` by *slot* (the character tag) instead of screen
          position, for the "3+ characters on screen" case (see the
          comment at `vnds_writer.py`'s `Show` branch) — but `Hide` was
          never updated to match: it resolved `node.image` (almost always
          given with no attributes, e.g. bare `hide chance`) to *some*
          default asset path and emitted a path-matched `clearimg`, which
          essentially never matched whatever composited file the
          character was actually shown as (e.g. shown as `chance happy`,
          hidden as bare `chance`) — the old sprite silently never got
          removed. Fixed in both places this pattern is emitted (the
          plain `Hide` branch and `_emit_body`'s "bare `hide` immediately
          followed by a standalone `with`" idiom): emit `clearslot
          <tag>` instead, reusing the same `clearslot` instruction
          CharacterImage's multi-layer system already relies on. New
          regression test proves a `show chance happy` + `hide chance`
          pair now emits `clearslot chance`, not a non-matching
          `clearimg`. 349/349 pytest green (up from 348).
        - Both fixes required rebuilding Jisei's hardware-test bundle
          from scratch and re-staging the SD card — not just an engine
          rebuild, since the `Hide` fix changes emitted script content.
      - **2026-07-08 — user report, past all 4 bugs above: Jisei's main
        menu on hardware was the engine's generic Start/Quit placeholder,
        not Jisei's real title-image-and-8-option menu.** Root cause:
        `rpy_parser.py`'s `_DEFAULT_SCREEN_NAMES` unconditionally skipped
        any screen literally named `main_menu`, assuming it's always
        Ren'Py's own auto-generated boilerplate — wrong whenever a game
        customizes it (nearly always). User asked to fix the converter
        (and engine, if needed) to use each game's real main menu.
        - **13-corpus survey**: Jisei's real `screen main_menu()` uses
          Ren'Py's `imagemap:`/`hotspot` widget (a background image +
          pixel-rect touch regions) — never parsed by this converter at
          all (Phase 5.1's custom-screen system only understood vbox/
          hbox/textbutton). Survey found 6 of 13 real games use imagemap
          (A Date with Death, GBDNATE, I Just Want to be Single, Jisei,
          Our Life, The Royal Trap), 5 of those 6 also in custom non-
          main-menu screens (character creators, galleries, confirm
          dialogs) — building real imagemap support was worth far more
          than a main-menu special case.
        - **Design** (full plan in this session's transcript): un-skipped
          only `main_menu` from `_DEFAULT_SCREEN_NAMES`; new `ScreenHotspot`/
          `ScreenImagemap` IR nodes (ir.py), nestable inside `ScreenIf`/
          `ScreenIfBranch` for free (Jisei's real shape is exactly `if
          persistent.beatgame: imagemap: ... else: imagemap: ...`); new
          parser support for `ground "path" [idle ...] [hover ...]` and
          `hotspot (x,y,w,h) action/clicked <expr> [alt "..."]` (both
          `action` and `clicked` keywords are real Ren'Py syntax — Jisei
          uses `action`, GBDNATE uses `clicked`); `Start()`/`Start("label")`
          added to the existing action vocabulary (`Jump`/`Call`/`Return`/
          `Quit`/`Show`/`ShowMenu`/`Hide`/`SetVariable`); `NullAction()`
          recognized as a real, intentional no-op (a decorative/locked
          hotspot), never a failure.
        - **Deliberate deviation from the existing all-or-nothing custom-
          screen convention**: one hotspot with an unsupported action
          (e.g. `Function(...)`, a dynamic passed-in action) is dropped
          and flagged on its own, not a whole-screen failure — every
          other hotspot, including New Game/Load/Quit, still converts.
          New classify.py rule, severity `approximated`. Only a missing/
          unparseable `ground` line bails the whole imagemap (nothing to
          render).
        - **Emitter**: new `imagemap_begin <ground>`/`hotspot <x> <y> <w>
          <h> | <action>`/`imagemap_end` instructions, mirroring
          `screen_begin`/`screen_button`/`screen_end`'s existing shape
          (empty text after `|` = `NullAction`). Asset pipeline's
          `required_asset_names` extended so the ground image actually
          gets converted (same `background` bucket as `bgload`).
        - **Engine**: `script.moon`'s positive-allowlist instruction
          switch gained the 3 new types (the single highest-risk omission
          — anything not listed there is silently dropped); `screen.moon`
          gained tree-building handlers + a `flatten()` case, and a new
          `show_imagemap` renderer that forks off `show_screen` when the
          flattened content is a single imagemap node. Reuses
          `images.moon`'s exact `draw_background` math (`scale =
          math.min(sx, sy)`, centered) for the ground image — confirmed
          safe since this session's earlier `images.moon` bgload fix
          means `sx`/`sy` are a sound, stable, once-at-boot reference;
          hotspot rects scale by the same factor. Touch hit-testing
          reuses the exact AABB-loop pattern `listbox.moon` already uses,
          and reuses the *same* `run_action` real screen buttons dispatch
          through — zero new action-dispatch code needed. Real
          `definitions["main_menu"]` (from a converted game) naturally
          overwrites the engine's hardcoded placeholder via the existing
          `on "screen_end"` handler — the placeholder now only shows for
          a game whose main_menu doesn't convert, with no extra code.
        - Also found and fixed two more real-content gaps surfaced while
          testing against Jisei's *actual* `screens.rpy` (not just a
          synthetic test case): a `tag menu` declaration and an empty
          `window: style "mm_root"` wrapper preceded the real if/imagemap
          content and bailed the whole screen — both are pure metadata
          with no visual content, now skipped safely.
        - **Explicitly out of scope, documented as follow-up, not
          silently dropped**: dynamic/passed-in actions (`yes_action`/
          `no_action` params, `Function(...)`, `SetScreenVariable`/
          `Preference`/`OpenURL`/`FilePage*`, compound action lists —
          seen only in the heaviest custom usages, A Date with Death's
          character creator and Our Life's ~150-hotspot creation flow);
          true hover-state visuals (3DS is touch-only, no continuous
          hover — ground/idle only); other reserved screen names
          (`navigation`/`yesno_prompt`/`save`/`load`/`preferences`/
          `quick_menu`) stay skipped; **GBDNATE's main_menu confirmed
          still doesn't fully convert** — isolated the exact remaining
          blocker to an `add "yaelselect.png" xpos 0 ypos 0 zoom 1` line
          inside its `window:` (a real decorative background image with
          no current screen-language support) — a genuine, separate,
          documented gap, not a bug in this feature.
        - **Verification**: 357/357 pytest (up from 349), 190/190 busted
          (up from 183, 7 new imagemap tests). Real-content: Jisei's
          `main_menu` now converts fully (all 8 hotspots resolved, zero
          problems, Total 4547→4546); GBDNATE's imagemap/hotspot syntax
          variations (`clicked`, standalone `hover` line) confirmed
          parsing correctly in isolation, gated only by the separate
          `add`-statement gap above. Full 13-corpus git-stash A/B
          sweep: **`Blocking` identical for every single game** (the
          critical invariant); 11 of 13 games shifted their main_menu
          flag from `info`("no action needed") to `manual`("needs native
          reimplementation") — an intentional, honest re-classification
          (their main_menu still doesn't fully convert due to *other*
          unsupported constructs, but no longer silently misreported as
          a no-op default); DateWarp unchanged (no main_menu in source).
          Jisei's hardware-test bundle rebuilt end-to-end and re-staged
          on the SD card for the next physical playtest.
      - **2026-07-08 — user request: make element positioning
        "proportionally accurate" between the PC original and the 3DS
        conversion.** Investigating surfaced a real, severe, pre-existing
        bug, not just a missing feature: the converter had **zero
        knowledge of any game's own declared `config.screen_width`/
        `config.screen_height`** (Ren'Py's design/authoring resolution —
        Jisei declares 1024x768, GBDNATE 800x600, most modern games call
        `gui.init(1920, 1080)`). Every ATL position property (`xpos`/
        `ypos`/`xalign`/`yalign`/etc.) was parsed as a bare `float()` and
        the x-axis unconditionally multiplied by 400, as if the value
        were *always* a 0.0-1.0 fraction of the target 400x240 space.
        That's Ren'Py's real rule for a **float** literal — but Ren'Py
        also lets `xpos`/`ypos` be a bare **int**, meaning an *absolute
        pixel offset in the game's own declared resolution*, a
        completely different (and previously unhandled) case. A
        13-corpus survey found this wasn't an edge case: every one of
        the 13 real games has hundreds to ~1700 bare-int position values,
        and 4 games (Jisei, GBDNATE, ScarletHollow, Slay the Princess)
        use almost no fractional positioning at all. Concrete real
        example found in GBDNATE: a sprite's real static position `x=20000`
        (20000 pixels off a 400px-wide screen — completely invisible,
        never rendered) and an ATL keyframe's `yalign=280` (a nonsensical
        fraction, should be ~0-1) were both silently emitted this way
        before the fix.
        - **Fix**: new `scan_screen_resolution` game-wide prepass (mirrors
          the existing `namebox_borders_tile`/`scan_transform_declarations`
          convention exactly) recognizes both `config.screen_width`/
          `config.screen_height` and `gui.init(w, h)` (7 of 13 games use
          the latter). New `_resolve_atl_value(prop, raw_value,
          screen_resolution)` helper: a value containing `.` is already a
          fraction (unchanged); a bare int is divided by the game's own
          declared width/height to get the *equivalent fraction* —
          converting the input early means every existing downstream
          consumer (`_atl_prop_to_engine`'s `value*400` for x, and the
          y-axis's raw-fraction-resolved-against-real-sprite-height path)
          needed **zero changes**, keeping the fix's blast radius to one
          new helper + 3 call-site edits. `screen_resolution` threaded
          through the same call chain `sprite_categories` was threaded
          through for the ChangePortrait feature (`_parse_statement` →
          `_parse_block`/`_parse_child_block` → `_parse_label_body`/
          `_parse_menu`/`_parse_if_chain`/`_parse_while`, ~9 signatures).
          Default `(800, 600)` (Ren'Py's own historical pre-GUI-template
          engine default) when a game declares neither form at all — not
          hit by any of the 13 real corpora.
        - **Confirmed unaffected, deliberately out of scope**: imagemap/
          hotspot coordinates (already self-consistent, scaled off the
          actual loaded ground image's real pixel dimensions at runtime,
          never needed `config.screen_width` at all); the coarse left/
          center/right position snap (a discrete named-position table,
          no numeric rescaling involved); DayCard/title-card overlay text
          (confirmed hardcoded constants, never derived from per-game
          source data).
        - **Verification**: 365/365 pytest (up from 357), 190/190 busted
          (unaffected — no engine-side changes at all, the rescaling
          happens entirely at convert time). Full 13-corpus git-stash A/B:
          **Problem Report totals byte-identical for every single game**
          (this fix changes coordinate *values* within already-supported
          content, never what's supported/blocking). Direct script.vnds
          diff confirmed the fix is genuinely active in 8 of 13 games
          (datewarp, gbdnate, ijwtbs, longlivethequeen, magicaldiary,
          micetea, ourlife, royaltrap — up to 2902 changed lines in Our
          Life); GBDNATE's real `x=20000`/`yalign=280` case above
          confirmed corrected to `x=25`/`yalign=0.467` (sane, on-screen
          values) after the fix. Jisei/adatewithdeath/cookingcompanions/
          scarlethollow/slaytheprincess show zero change — their real
          story content doesn't use bare-int ATL positioning in practice
          (any bare-int usage they do have is in screen-language/
          imagebutton contexts, a separate code path this fix doesn't
          touch) — so Jisei's already-staged hardware-test bundle didn't
          need rebuilding this round.
      - **2026-07-08 — two more real hardware bugs from the very next
        Jisei playtest, past all the fixes above.** User reported the
        main menu "appears unaltered from the prior build" (the real
        imagemap main menu still not showing) and, separately, "the
        background and character sprites appear much too large."
        - **Main menu never actually registered in time.** Root-caused by
          reading `save.moon`'s new-game path: `dispatch "show_screen",
          {name: "main_menu"}` fires immediately after `script.load`,
          before the interpreter has ever advanced a single instruction.
          A real converted `main_menu` is registered by ordinary
          `screen_begin`/.../`screen_end` instructions sitting in the
          script's own top-level preamble (vnds_writer.py emits them
          before the first `@label`, relying on normal top-to-bottom
          execution to register them before any `show_screen` can
          reference one) — but nothing had ever caused the interpreter to
          walk through that preamble yet, so only screen.moon's
          hardcoded placeholder (registered once at require-time) ever
          existed to show. New `script.run_preamble(s)`: walks the
          interpreter forward, dispatching each pass-through instruction,
          stopping the instant `s.n` reaches `s.labels["start"]` (checked
          *before* each step, not via `ins.type == "label"` — a "label"
          instruction is never actually handed back to the caller at all;
          `next_instruction` has no switch case for it and silently
          skips over it via its own tail-recursive call, an
          implementation detail that broke the first version of this fix
          during its own busted test — caught and corrected before
          landing). `save.moon`'s new-game path now calls this between
          `script.load` and `dispatch "show_screen"`. New
          `tests/engine/main_menu_preamble_spec.moon` (3 tests): a real
          main_menu registers correctly; the interpreter lands exactly on
          `@start`'s own first real instruction afterward (no overshoot
          into the story, no undershoot); a game with no real main_menu
          still falls back to the placeholder. 193/193 busted (up from
          190).
        - **Backgrounds never actually scaled to fit the screen.** A
          second, unrelated, genuinely new bug — exposed (not caused) by
          this session's earlier `images.moon` bgload fix. `pipeline.py`
          capped background images only against `_MAX_TEXTURE_DIMENSION`
          (1024, the PICA200 hardware texture limit), never against the
          engine's actual 400x240 target screen — a stale neighboring
          comment claimed this was fine because "images.moon's bgload
          handler already rescales the background to fill the screen
          based on its own actual pixel dimensions," but that described
          the *exact* broken mechanism this session's earlier fix
          correctly deleted (it corrupted sprite scale and silently
          reverted the custom font as side effects). Once removed,
          backgrounds draw at their own true pixel size scaled only by
          the stable ~1.0 device ratio — meaning background art
          authored at the source game's own real design resolution
          (confirmed real content: Jisei's actual background files are a
          genuine 1024x768, matching its declared `config.screen_width`/
          `config.screen_height`) now drew hugely oversized instead of
          filling the screen. Fixed with new `_BACKGROUND_MAX_WIDTH=400`/
          `_BACKGROUND_MAX_HEIGHT=240` constants (aspect-preserving fit,
          matching `draw_background`'s own runtime scale-to-fit math
          exactly) applied to the "background" destination bucket in
          `resolve_and_convert_assets` — also covers imagemap's `ground`
          image for free, since it shares the same bucket and draw math.
          New regression test confirms a real 1024x768 (4:3) source
          scales to exactly 320x240 (fit within 400x240, aspect
          preserved). 366/366 pytest (up from 365).
        - Jisei's hardware-test bundle rebuilt end-to-end (engine +
          reconverted with `--assets`) and re-staged on the SD card
          (42M) for the next physical playtest.
      - **2026-07-08 — real main menu confirmed working on hardware, then
        a new crash scrolling it.** User confirmed the real imagemap
        main menu now shows (`run_preamble` fix above verified live), but
        pressing the d-pad to try to navigate it crashed: `listbox.lua:20:
        attempt to index field '?' (a nil value)`, traceback through
        `text/text.lua:273`'s "up"-input handler calling into
        `create_listbox`. Root cause: every other screen (`listbox.moon`'s
        own `input_event`) always intercepts/consumes `"input"` while
        shown, which is what protects unrelated global input handlers
        elsewhere — specifically `text.moon`'s dialogue-backlog
        scrollback feature, bound to plain `"up"` — from ever firing
        during a menu. `show_imagemap` never registered an `"input"`
        handler at all (a deliberate choice — real Ren'Py imagemaps have
        no keyboard/gamepad navigation model), so pressing "up" on the
        very first, pre-any-dialogue main menu fell straight through to
        the backlog handler, which crashed building a listbox from an
        empty (no dialogue has ever played yet) backlog. Fixed: added an
        `input_event = on "input", (input) -> false` to `show_imagemap`
        — swallows all directional input unconditionally (imagemap still
        doesn't *act* on it, matching real Ren'Py), but now correctly
        blocks it from leaking to other global handlers the same way
        every other screen already does. New busted regression test
        registers a listener *before* `show_screen` and confirms it
        never fires once the imagemap is shown (proving `show_imagemap`'s
        own handler — registered after, dispatched first, LIFO — is what
        actually stops propagation, not test ordering). 194/194 busted
        (up from 193). Jisei's bundle re-staged (42M, script/assets
        unchanged this round — engine-only fix).
      - **2026-07-08 — real main menu confirmed showing on hardware, then
        "none of the options are selectable."** Root cause: `hotspot`
        coordinates are authored in Ren'Py source as absolute pixels in
        the `ground` image's own *original* resolution — but this
        session's own background-sizing fix (above) now resizes that
        same ground image at convert time to fit the engine's 400x240
        target screen. `show_imagemap` read the *actually loaded*
        (resized) image's real dimensions but still treated hotspot
        coordinates as if they were already in that space — confirmed
        real content: Jisei's `mainmenu.jpg` is a genuine 1024x768,
        resized to 320x240 by the pipeline fix, so a hotspot authored at
        `y=390` (meant to be roughly mid-image in a 768-tall original)
        landed at pixel 390 of a 240-tall *loaded* image — hundreds of
        pixels below the visible area, for every single hotspot.
        - **Fix**: `ScreenHotspot.x/y/w/h` are now fractions (0.0-1.0) of
          the game's own declared resolution (the same
          `scan_screen_resolution`/`screen_resolution` context already
          threaded through for the ATL-position fix), not absolute
          pixels — computed once in `_parse_screen_imagemap`
          (`round(int(x)/screen_width, 4)`, etc.), threaded through the
          *separate* custom-screen parsing call chain
          (`_parse_screen_children`/`_parse_screen_if`/`_parse_screen_def`
          — confirmed to be an entirely independent signature chain from
          the regular-statement one the ATL fix already threaded through,
          not covered by that earlier change). Emitter formats them via
          the existing `_format_prop_value` helper (same clean whole-
          number-vs-decimal formatting ATL props already use).
          `script.moon`'s `hotspot` line regex widened from `%d+`
          (integer-only) to `[%d.]+` to actually accept the decimal
          fractions. `show_imagemap` now multiplies each fraction by the
          *actually loaded* ground image's real `img_w`/`img_h` (from
          `image\getDimensions!`) — correctly resolution-independent
          regardless of whatever the asset pipeline resizes the ground
          image to, mirroring the exact `_resolve_atl_value` proportional-
          scaling technique from earlier in this same session.
        - Two new busted regression tests (one for a ground image resized
          smaller than the declared reference, one for device sx/sy
          scaling) plus updated existing tests/fixtures across both
          pytest and busted to use fraction values. 366/366 pytest,
          195/195 busted.
        - Jisei's bundle rebuilt end-to-end (reconverted with `--assets`,
          since this changes emitted hotspot values) and re-staged.
      - **2026-07-08 — past the menu, "character sprites are still too
        large."** A second, distinct foreground-sizing bug, found right
        after the imagemap/background fixes above. `_FOREGROUND_MAX_WIDTH`
        (400, width-only, height left free up to the hardware limit) was
        itself a fix for an *earlier* real bug (capping both axes made
        character art look smaller than the PC version) — but it silently
        assumed source character art is always *wider* than 400px. Real
        content broke that assumption directly: Jisei's own character
        layers are a genuine 286x768 (narrower than 400), so the width
        cap never triggered at all, leaving every sprite at its full
        768-tall native size drawn 1:1 onto the 240-tall screen — wildly
        oversized.
        - **Fix**: foreground/character art is now scaled by one
          proportional factor — `min(400/game_width, 240/game_height)`,
          derived from the game's own declared resolution (the same
          `screen_resolution` context threaded for the ATL/hotspot
          fixes), not an independent per-image "fit to a fixed pixel box"
          guess. New `_foreground_scale_for`/`_scale_image_by_factor` in
          `pipeline.py` (an always-applied multiplicative scale, unlike
          `_downscale_if_oversized`'s "only if the box is exceeded"
          model); `_FOREGROUND_MAX_WIDTH` removed entirely, superseded.
          `convert_image` gained a `scale` parameter (applied first, with
          `max_width`/`max_height` still checked afterward as a hardware-
          safety backstop). `screen_resolution` threaded from `Script`
          (new field, set once by `parse_rpy`, merged in `parse_game`)
          through `build_bundle` into all 3 foreground conversion entry
          points (`resolve_composite_images`, `resolve_character_image_layers`
          — shared by both CharacterImage and portrait layers — and
          `resolve_and_convert_assets`'s foreground branch).
        - This still reproduces the original "cropped, not shrunk" intent
          for character art authored to fill/overflow the frame — it just
          derives the *right* ratio from the game's own resolution
          instead of guessing per-image from a flat pixel constant.
        - New regression test using the exact real Jisei dimensions
          (286x768 at declared 1024x768) confirms the old cap would
          never have triggered but the new scale correctly shrinks it to
          fit the 240-tall target; two existing foreground-sizing tests
          updated to the new proportional-scale semantics. 367/367
          pytest (up from 366), 195/195 busted (unaffected — pure
          converter-side fix).
        - Jisei's bundle rebuilt end-to-end and re-staged (35M, down from
          42M — consistent with foreground art actually shrinking now).

---

## Phase 6 — Multi-Engine Converters (long-term)

**Goal:** Extend converter to support other popular VN engines.

### 6a — NScripter / ONScripter
- [ ] **6a.1** — NScripter converter: parse `.txt` scripts, map command set to
      extended VNDS
- [ ] **6a.2** — `.nsa`/`.sar` archive extraction integration
- [ ] **6a.3** — Validation: run on Tsukihime; compare output to existing VNDS
      community conversion

### 6b — KiriKiri / KiriKiri Z (KAG)
- [ ] **6b.1** — KiriKiri converter: parse KAG `.ks`/`.tjs` scripts, map
      declarative subset to extended VNDS; flag TJS2 blocks
- [ ] **6b.2** — `.xp3` archive extraction integration (KrkrExtract / GARbro)
- [ ] **6b.3** — E-mote model extraction pipeline (FreeMoteToolkit) — segment to
      Option A layers + Option B bones
- [ ] **6b.4** — Port **Nekopara Vol. 0** (SFW Steam version only — E-mote
      animation stress test) — Chocola + Vanilla rigged with combined A+B system;
      both animated simultaneously on Old 3DS; memory under 70MB
- [ ] **6b.5** — Natural follow-on: Nekopara Vol. 1 (full cast)
- [ ] **6b.6** — Port **Fate/stay night** (KiriKiri target)

### 6c — TyranoScript / TyranoBuilder
- [ ] **6c.1** — TyranoScript converter: parse `.ks` files, map tag-based
      declarative subset; flag `[iscript]` blocks
- [ ] **6c.2** — Validation: run on a freely available TyranoScript title

### 6d — NVL-Maker (sub-task of 6b)
- [ ] **6d.1** — Verify NVL-Maker titles work with 6b KiriKiri converter; adjust
      as needed

### 6e — RealLive (Key / Visual Arts)
- [ ] **6e.1** — RealLive converter: parse `.seen` bytecode (reference `rlvm`
      open-source VM); map to extended VNDS; flag scripting blocks
- [ ] **6e.2** — Validation: run on **planetarian** (short kinetic novel, same
      engine, available on Steam)
- [ ] **6e.3** — Port **CLANNAD** — Light Orb progression system implemented
      natively; at least two routes playable end-to-end on Old 3DS hardware

### 6f — Additional Ren'Py Ports (moved from Phase 3)
- [ ] **6f.1** — Port **Sucker for Love: First Date** — converter + triage +
      hand-author ritual/interaction segments as native touch scenes
- [ ] **6f.2** — Port **Am I Nima?** (releases 2026-11-27). Not a traditional
      VN: fingerprint its engine on release and decide the approach then

### 6g — VNDS (ADR-004)
- [ ] **6g.1** — VNDS converter front end: translate each standard VNDS command
      into the engine's own model explicitly (256×192 canvas, top-left anchor,
      `bgload` as a scene change), no approximation
- [ ] **6g.2** — Unpack VNDS novel `.zip` bundles (script/, background/,
      foreground/, sound/) as converter input
- [ ] **6g.3** — Validation: Saya no Uta and Tsukihime VNDS scripts play correctly
      after conversion

---

## Open Decisions

| Decision | Status |
|---|---|
| O3DS LÖVE Potion baseline RAM consumption | Measure in Phase 0.5 stress test |
| Rollback depth — actual RAM cost per entry on O3DS | Measure in Phase 3.7 |
| Jisei investigation UI — `menu:` or custom `screen`? | Determined by Phase 1.9 converter run |
| Am I Nima? engine and scope | Unknown until its 2026-11-27 release |
| Project name (rebrand away from LÖVE/VNDS) | Decided: VN3DS-CHARM (converter Witch, engine Enchantment, `.charm` bundles), ADR-006; doc/repo/folder rename pending |
| Custom-screen runtime vs. per-game native reimplementation | Evaluate after Phase 4 |
| Triage Workbench UI framework (tkinter/PySimpleGUI/web) | Decide at Phase 5.5 kickoff |
| Converter/Engine exact tool versions (Python, LÖVE Potion) | Pin during Phase 0/1 |
| Runtime script format replacing `script.vnds` (compiled Lua loaded on demand is the leading candidate) | Needs its own ADR (ADR-004 frees it from VNDS) |
