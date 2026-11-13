"""Parses the supported Ren'Py subset (VN3DS-spec.md §6) into the IR.

Supported: label/jump/call/return, scene/show/hide (+ "at left/center/right",
trailing "with <transition>" ignored for now), say statements, top-level
`define x = Character(...)`, and menu: blocks.

Anything else becomes an Unsupported node and parsing continues — the
converter must always terminate with a Problem Report, never a crash.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from .ir import (
    AnimSpec,
    Call,
    CharacterDef,
    DayCard,
    FrameAsset,
    Hide,
    If,
    IfBranch,
    Jump,
    Label,
    Menu,
    MenuChoice,
    Node,
    Pause,
    Placeholder,
    Play,
    PortraitLayerUpdateIR,
    PortraitUpdate,
    Random,
    ResetAudio,
    Return,
    Say,
    Scene,
    Script,
    ScreenBox,
    ScreenButton,
    ScreenDef,
    ScreenHotspot,
    ScreenIf,
    ScreenIfBranch,
    ScreenImagemap,
    ScreenText,
    Set,
    SetVolume,
    Show,
    SourceLocation,
    Stop,
    SubchapterCard,
    SubchapterHide,
    TheEndCard,
    Transition,
    Unsupported,
    While,
    Window,
)
from .character_sprite import PortraitUpdateCall, SpriteLayerCategories, parse_change_portrait_call
from .lexer import Cursor, RawLine, tokenize_lines

_LIST_MUTATION_METHODS = {"insert", "append", "remove", "pop", "extend"}

# Ren'Py's built-in transition-constructor classes, as seen in
# `define wipedown = CropMove(0.5, "wipedown")`-style custom transition
# aliases. Not exhaustive -- just the ones observed in real content plus
# the most common built-ins.
_TRANSITION_CONSTRUCTOR_NAMES = {
    "CropMove", "Dissolve", "Fade", "Pixellate", "MoveTransition",
    "ImageDissolve", "PushMove",
}

# Ren'Py's own default screens (auto-generated into every fresh project's
# screens.rpy, not custom content) — VN3DS-spec.md §6 already says custom
# screens are `manual` *because* "default screens are provided natively":
# the engine ships its own dialogue box, choice buttons, and save/load UI
# that fully replace these, so they're safe to skip entirely rather than
# flag as needing native reimplementation.
#
# "main_menu" deliberately excluded from this set (real-hardware finding):
# unlike the rest, games essentially always customize their main menu (a
# title image + New Game/Load/Options/... options), so treating it as
# always-default-boilerplate silently threw away real, game-specific
# content in favor of the engine's own generic Start/Quit placeholder. It
# now goes through the same real parsing pipeline as any other custom
# screen (see the "imagemap:" support this enabled) and only falls back to
# the placeholder if that parsing genuinely fails to find anything usable.
_DEFAULT_SCREEN_NAMES = {
    "say", "choice", "input", "nvl", "navigation",
    "file_picker", "file_picker_old", "save", "load",
    "preferences", "old_preferences", "yesno_prompt", "quick_menu",
}
_SCREEN_HEADER_RE = re.compile(r"^screen\s+(\w+)")

# Matches either quote style as one contiguous, non-capturing span (Ren'Py/
# Python treat "..." and '...' as fully interchangeable). Deliberately
# captures nothing itself -- every call site wraps it in its own outer
# `({_QUOTED})` to get the quoted literal *including* its quote marks, then
# calls `_dequote` (not `_unescape`) to strip the quote pair and unescape
# the interior. This keeps every existing regex's group count/position
# unchanged (no renumbering needed anywhere `_QUOTED` is embedded more than
# once, e.g. _SAY_NAMED_RE/_DAY_RE).
_QUOTED = r'(?:"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'
_SAY_NAMED_RE = re.compile(rf"^({_QUOTED})\s+({_QUOTED})\s*$")
_SAY_RE = re.compile(rf'^(?:(\w+(?:\s+\w+)*)\s+)?({_QUOTED})\s*(?:\(.*\))?\s*$')
_MENU_CHOICE_RE = re.compile(rf"^({_QUOTED})\s*(?:if\s+.+)?:\s*$")
_DEFINE_RE = re.compile(r"^define\s+(\w+)\s*=\s*(.+)$")
# The captured name allows one optional `namespace.` prefix (real content:
# `default persistent.skip_sex = "prompt"`) -- resolved the same way
# `_render_expr`'s own persistent.X/store.X handling does, in
# `_parse_default_define` below. Any other dotted name (not persistent/
# store) is rejected there, same as before this widening.
_DEFAULT_DEFINE_RE = re.compile(r"^(?:default|define)\s+(\w+(?:\.\w+)?)\s*=\s*(.+)$")
_IMAGE_DEF_RE = re.compile(r"^image\s+([\w ]+?)\s*=\s*(.+)$")
_AT_RE = re.compile(r"\bat\s+(.+)$")
_WITH_RE = re.compile(r"\bwith\b")
_STANDALONE_WITH_RE = re.compile(r"^with\s+(\w+)\s*$")
# Channel name is intentionally *not* a fixed alternation -- real content
# uses channels beyond the original music/sound/voice set (confirmed:
# Mice Tea's "audio" -- Ren'Py's own built-in one-shot channel -- and
# "ambiance", a custom channel registered via
# `renpy.music.register_channel`, both real and frequently used). Which
# names are actually recognized (and what they map onto) is an emission-
# time concern -- see vnds_writer.py's `_PLAY_COMMAND`/`_STOP_COMMAND`.
# The file/list portion is deliberately just captured whole and parsed
# separately (`_parse_play_file_spec`) rather than baked into this regex,
# since it can be a literal string, a bare `define`d alias, or a
# bracketed random-choice list.
_PLAY_QUEUE_RE = re.compile(r"^(play|queue)\s+(\w+)\s+(.+)$")
# Ren'Py's bare `voice "audio/v/line.ogg"` form (no "play"/"queue" prefix) is
# the common idiom for voiced dialogue lines, placed right before the `say`
# statement it accompanies. Without this, it fell through to _SAY_RE, which
# happily matches `voice "path.ogg"` as character "voice" saying the literal
# file path as dialogue text -- confirmed on real hardware with Jisei.
_VOICE_RE = re.compile(rf"^voice\s+({_QUOTED})\s*$")
_STOP_RE = re.compile(r"^stop\s+(\w+)\b")
_SILENCE_ENTRY_RE = re.compile(r'^"<silence[^"]*>"$', re.IGNORECASE)
_PAUSE_RE = re.compile(r"^pause(?:\s+([\d.]+))?\s*$")
# "auto" (Ren'Py's third window state, alongside show/hide -- the engine's
# own `on "window"` treats anything but "hide" as visible, so "auto"
# already behaves correctly with no engine change) and an optional
# trailing transition token (e.g. `window hide None` -- unrpyc's real
# decompiled rendering of an explicit-but-empty transition argument) were
# both found via a second real game (Mice Tea); the trailing token is
# ignored, same fidelity level as the already-untracked plain show/hide.
_WINDOW_RE = re.compile(r"^window\s+(show|hide|auto)(?:\s+\S+)?\s*$")
# Mice Tea's 6 custom Ren'Py statements (statements.rpy's
# `renpy.statements.register(...)` calls) -- exact argument grammar read
# directly from each one's own `parse_*` function there: `day` takes
# string/string/[string], `subchapter` takes one string, `subchapter_hide`/
# `reset_audio` take no args (reset_audio's own `parse_reset_audio` allows
# an optional bare word, but `execute_reset_audio` never reads it), `the_end`
# takes one string, `placeholder` takes an optional bare word.
_DAY_RE = re.compile(rf"^day\s+({_QUOTED})\s+({_QUOTED})(?:\s+({_QUOTED}))?\s*$")
_SUBCHAPTER_RE = re.compile(rf"^subchapter\s+({_QUOTED})\s*$")
_SUBCHAPTER_HIDE_RE = re.compile(r"^subchapter_hide\b")
_RESET_AUDIO_RE = re.compile(r"^reset_audio\b")
_THE_END_RE = re.compile(rf"^the_end\s+({_QUOTED})\s*$")
_PLACEHOLDER_RE = re.compile(r"^placeholder\b")
_TEXT_TAG_RE = re.compile(r"\{(/?)(\w+)(?:=([^}]*))?\}")

# Ren'Py's legacy imperative `ui.*` API (predates the declarative `menu:`/
# `screen:` languages, but still fully supported) — some real-world games
# build their entire choice UI with `ui.vbox`/`ui.textbutton`/`ui.close` +
# `ui.interact()` + an `if result == N:` chain instead. See
# _try_convert_ui_menu below.
_UI_NOISE_RE = re.compile(r'^\$\s+ui\.(?:vbox|hbox|close)\(.*\)\s*$')
_UI_TEXTBUTTON_RE = re.compile(
    rf'^\$\s+ui\.textbutton\(\s*({_QUOTED})\s*,\s*clicked\s*=\s*(?:ui\.returns\((\d+)\)|None)'
)
_UI_INTERACT_RE = re.compile(r'^\$\s+(\w+)\s*=\s*ui\.interact\(\s*\)\s*$')

# Ren'Py's `style.default.font = "path/to/font.ttf"` — almost always sits
# inside an `init python:` block (arbitrary Python, otherwise entirely
# unparsed by this module), so it's recovered by a standalone regex scan
# over the raw source rather than the statement-by-statement parser. Not
# tied to any indentation/block context deliberately -- it's one of the
# few `init python:` statements worth digging out on its own, since it's
# the game's actual intended dialogue font (see ir.py's `Script.default_font`).
#
# `define gui.default_font = "..."` is the alternate form used by any game
# built off Ren'Py's standard `gui.rpy` template (confirmed against Mice
# Tea, which has no `style.default.font` line at all) -- same purpose,
# different variable name, so both forms feed the same capture group.
_DEFAULT_FONT_RE = re.compile(
    r'^\s*(?:style\.default\.font|define\s+gui\.default_font)\s*=\s*"([^"]+)"\s*$',
    re.MULTILINE,
)


def _scan_default_font(source: str) -> str | None:
    match = _DEFAULT_FONT_RE.search(source)
    return match.group(1) if match else None


# A static, game-wide typewriter speed -- deliberately *not*
# `preferences.text_cps` (a runtime-adjustable user setting, out of scope,
# see ir.py's Script.default_text_cps docstring).
_DEFAULT_TEXT_CPS_RE = re.compile(
    r'^\s*config\.(?:default_text_cps|text_cps)\s*=\s*(\d+(?:\.\d+)?)\s*$',
    re.MULTILINE,
)


def _scan_default_text_cps(source: str) -> float | None:
    match = _DEFAULT_TEXT_CPS_RE.search(source)
    return float(match.group(1)) if match else None


# --- Custom UI-asset-import system (VN3DS-spec.md §6) ---------------------
# The dialogue textbox is a *plain* background image in both target games
# (confirmed real content: no Frame()/border-scaling, just a fixed-size
# `Image("gui/textbox.png", ...)`, or the legacy `style.window.background =
# "..."` form) -- unlike namebox/choice buttons below, which are real
# Frame() 9-patches. Matches on "textbox" in the filename, since Ren'Py's
# standard generated screens.rpy template always uses exactly this literal
# path for any game built off the modern gui.rpy generator.
_TEXTBOX_IMAGE_RE = re.compile(r'Image\("(gui/[^"]*textbox[^"]*\.(?:png|jpg|webp))"', re.IGNORECASE)
_TEXTBOX_LEGACY_RE = re.compile(r'^\s*style\.window\.background\s*=\s*"([^"]+)"\s*$', re.MULTILINE)


def _scan_textbox_image(source: str) -> str | None:
    match = _TEXTBOX_IMAGE_RE.search(source)
    if match:
        return match.group(1)
    match = _TEXTBOX_LEGACY_RE.search(source)
    return match.group(1) if match else None


# The namebox (nameplate background) is a real Frame() 9-patch in both
# target games -- its borders/tile flag are almost always a reference to a
# separate `define gui.namebox_borders = Borders(l, t, r, b)` /
# `define gui.namebox_tile = True/False` pair (Ren'Py's standard gui.rpy
# template) declared in a *different file* from the one that actually
# calls `Frame("gui/namebox/namebox.png", gui.namebox_borders, ...)`
# (confirmed real content: Mice Tea declares the constants in gui.rpy but
# makes the Frame() call in screens.rpy) -- so, like transforms/string
# defines, this needs a game-wide prepass (`scan_namebox_borders_tile`,
# called once per file and merged in cli.py's parse_game, first-found
# wins) rather than a plain per-file scan, which would silently default
# borders to zero whenever the two pieces don't happen to share a file.
# Falls back to the legacy `style.say_who_window.background = Frame(
# "path", xborder, yborder)` form (a single, self-contained call, uniform
# x/y border, tile defaults False -- Ren'Py's own classic-API default) for
# games with no gui.rpy at all.
_NAMEBOX_IMAGE_RE = re.compile(r'Frame\("(gui/[^"]*namebox[^"]*\.(?:png|jpg|webp))"', re.IGNORECASE)
_NAMEBOX_BORDERS_RE = re.compile(
    r'^\s*define\s+gui\.namebox_borders\s*=\s*Borders\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)\s*$', re.MULTILINE
)
_NAMEBOX_TILE_RE = re.compile(r'^\s*define\s+gui\.namebox_tile\s*=\s*(True|False)\s*$', re.MULTILINE)
_NAMEBOX_LEGACY_FRAME_RE = re.compile(
    r'^\s*style\.say_who_window\.background\s*=\s*Frame\("([^"]+)"\s*,\s*(\d+)\s*,\s*(\d+)\)\s*$', re.MULTILINE
)
# Confirmed real content: Jisei's namebox is a *bare* image path with no
# Frame() wrapper at all (`style.say_who_window.background =
# "gui/namebox.png"`) -- a plain image, same treatment as textbox (borders
# all-zero degenerates draw_frame to one plain scaled draw).
_NAMEBOX_LEGACY_PLAIN_RE = re.compile(
    r'^\s*style\.say_who_window\.background\s*=\s*"([^"]+)"\s*$', re.MULTILINE
)


def scan_namebox_borders_tile(source: str) -> "tuple[tuple[int, int, int, int], bool] | None":
    """Game-wide prepass (mirrors scan_transform_declarations/scan_string_
    defines): recovers just the `gui.namebox_borders`/`gui.namebox_tile`
    pair from one file's raw source, for cli.py's parse_game to merge
    across every file (first-found wins) before any file's `_scan_namebox_
    frame` call -- these constants and the Frame() call using them are
    frequently declared in different files (see module comment above)."""
    borders_match = _NAMEBOX_BORDERS_RE.search(source)
    if not borders_match:
        return None
    borders = tuple(int(g) for g in borders_match.groups())
    tile_match = _NAMEBOX_TILE_RE.search(source)
    tile = tile_match.group(1) == "True" if tile_match else False
    return borders, tile


def _scan_namebox_frame(
    source: str, namebox_borders_tile: "tuple[tuple[int, int, int, int], bool] | None" = None
) -> "FrameAsset | None":
    # Checked before the "modern" path-only pattern below: a Frame() call
    # with *literal numeric* border args is unambiguously the legacy form
    # (the modern form always references gui.namebox_borders/tile as
    # variables, never inline numbers) -- the modern pattern alone would
    # otherwise also match this call's path and silently default its
    # borders to zero, since gui.namebox_borders/tile genuinely aren't
    # declared anywhere in legacy-style content.
    legacy_frame_match = _NAMEBOX_LEGACY_FRAME_RE.search(source)
    if legacy_frame_match:
        path, xb, yb = legacy_frame_match.groups()
        xb, yb = int(xb), int(yb)
        return FrameAsset(image=path, borders=(xb, yb, xb, yb), tile=False)
    image_match = _NAMEBOX_IMAGE_RE.search(source)
    if image_match:
        if namebox_borders_tile is not None:
            borders, tile = namebox_borders_tile
        else:
            # This file's own text is the only fallback if the game-wide
            # prepass somehow missed it (e.g. a direct/standalone call to
            # this function, as in unit tests) -- still correct for the
            # common case where both pieces share one file.
            borders_match = _NAMEBOX_BORDERS_RE.search(source)
            borders = tuple(int(g) for g in borders_match.groups()) if borders_match else (0, 0, 0, 0)
            tile_match = _NAMEBOX_TILE_RE.search(source)
            tile = tile_match.group(1) == "True" if tile_match else False
        return FrameAsset(image=image_match.group(1), borders=borders, tile=tile)
    legacy_plain_match = _NAMEBOX_LEGACY_PLAIN_RE.search(source)
    if legacy_plain_match:
        return FrameAsset(image=legacy_plain_match.group(1), borders=(0, 0, 0, 0), tile=False)
    return None


# In-story choice / custom-screen / save-load / main-menu button
# backgrounds -- listbox.moon's single shared widget, confirmed exactly 2
# real states (idle/hover) in both target games.
_CHOICE_BUTTON_BORDERS_RE = re.compile(
    r'^\s*define\s+gui\.choice_button_borders\s*=\s*Borders\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)\s*$', re.MULTILINE
)
_CHOICE_BUTTON_TILE_RE = re.compile(r'^\s*define\s+gui\.choice_button_tile\s*=\s*(True|False)\s*$', re.MULTILINE)
_LEGACY_BUTTON_BG_RE = re.compile(
    r'^\s*style\.button\.background\s*=\s*Frame\("([^"]+)"\s*,\s*(\d+)\s*,\s*(\d+)\)\s*$', re.MULTILINE
)
_LEGACY_BUTTON_HOVER_BG_RE = re.compile(
    r'^\s*style\.button\.hover_background\s*=\s*Frame\("([^"]+)"\s*,\s*(\d+)\s*,\s*(\d+)\)\s*$', re.MULTILINE
)
# Ren'Py's modern gui.rpy template routes the choice button's actual image
# path through its own internal `gui.button_properties(...)` helper (part
# of Ren'Py's engine, in its own common code -- never the game's own
# source) -- confirmed real content: Mice Tea's `style choice_button is
# button` + `properties gui.button_properties("choice_button")` never
# mentions "choice_idle_background.png" anywhere in its own .rpy source,
# even though that's exactly the file actually used. Unlike namebox/
# textbox (which the game's own screens.rpy always references directly),
# there's no literal text to scan for here -- these are Ren'Py's own
# fixed, non-game-specific filenames for the default choice screen
# specifically, used whenever `gui.choice_button_borders` confirms the
# game uses the standard template. assets/pipeline.py's resolve_ui_assets
# tries these well-known paths against the real asset directory, falling
# back to "missing" (the same graceful degradation every other asset
# reference already gets) if some non-standard game doesn't have them.
_CHOICE_IDLE_WELL_KNOWN_PATH = "gui/button/choice_idle_background.png"
_CHOICE_HOVER_WELL_KNOWN_PATH = "gui/button/choice_hover_background.png"


def _scan_choice_button_frames(source: str) -> "tuple[FrameAsset | None, FrameAsset | None]":
    borders_match = _CHOICE_BUTTON_BORDERS_RE.search(source)
    if borders_match:
        borders = tuple(int(g) for g in borders_match.groups())
        tile_match = _CHOICE_BUTTON_TILE_RE.search(source)
        tile = tile_match.group(1) == "True" if tile_match else False
        idle = FrameAsset(image=_CHOICE_IDLE_WELL_KNOWN_PATH, borders=borders, tile=tile)
        hover = FrameAsset(image=_CHOICE_HOVER_WELL_KNOWN_PATH, borders=borders, tile=tile)
        return idle, hover
    idle = None
    hover = None
    legacy_idle = _LEGACY_BUTTON_BG_RE.search(source)
    if legacy_idle:
        path, xb, yb = legacy_idle.groups()
        xb, yb = int(xb), int(yb)
        idle = FrameAsset(image=path, borders=(xb, yb, xb, yb), tile=False)
    legacy_hover = _LEGACY_BUTTON_HOVER_BG_RE.search(source)
    if legacy_hover:
        path, xb, yb = legacy_hover.groups()
        xb, yb = int(xb), int(yb)
        hover = FrameAsset(image=path, borders=(xb, yb, xb, yb), tile=False)
    return idle, hover


_COMPARE_SYMBOLS: dict[type, str] = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.GtE: ">=",
    ast.LtE: "<=",
    ast.Lt: "<",
    ast.Gt: ">",
}
_BINOP_SYMBOLS: dict[type, str] = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
}


def _unescape(text: str) -> str:
    return text.replace('\\"', '"').replace("\\'", "'")


def _dequote(raw: str) -> str:
    """Strips the surrounding quote pair (either `"..."` or `'...'` --
    _QUOTED matches either) and unescapes the interior."""
    return _unescape(raw[1:-1])


def _resolve_audio_entry(entry: str, string_defines: dict[str, str]) -> str | None:
    """Resolves one `play`/`queue` file entry -- a literal quoted string,
    or a bare identifier referring to a `define`d (or, confirmed against
    real content, an `init python:`-block bare-assigned -- see
    `scan_string_defines`) string alias, the dominant real-world form
    (488 of 592 real `play`/`queue`/`stop` statements in Mice Tea use a
    bare alias, not a literal string). An unresolvable bare name is used
    as-is (a visibly wrong path is a more honest failure than silently
    dropping the cue). Returns None for Ren'Py's `"<silence N>"`
    pseudo-entry (a timing gap, not a real file)."""
    entry = entry.strip()
    if _SILENCE_ENTRY_RE.match(entry):
        return None
    if len(entry) >= 2 and entry[0] == entry[-1] and entry[0] in ('"', "'"):
        return _dequote(entry)
    match = re.match(r"^(\w+)$", entry)
    if match:
        return string_defines.get(match.group(1), match.group(1))
    return None


def _parse_play_file_spec(rest: str, string_defines: dict[str, str]) -> tuple[str | None, list[str] | None]:
    """Extracts the file (or Ren'Py's randomized-file-choice bracket list,
    e.g. `[sfx_camera_fast, "<silence 0.5>", sfx_camera_fast]`) from a
    `play`/`queue` statement's remainder -- tolerating trailing modifier
    tokens (`fadein 2.0`, `loop`, ...) the same way the previous literal-
    string-only regex already did (matched, not fully consumed). Returns
    (single_file, None) for a plain entry, or (None, choices) for a
    bracket list with 2+ real entries after dropping silence pseudo-
    entries -- never both, and (None, None) if nothing resolved at all
    (an empty/all-silence list, or a rest that isn't recognizable as
    either shape)."""
    rest = rest.strip()
    if rest.startswith("["):
        end = rest.find("]")
        if end == -1:
            return None, None
        entries = [e.strip() for e in rest[1:end].split(",")]
        resolved = [r for e in entries if e and (r := _resolve_audio_entry(e, string_defines)) is not None]
        if not resolved:
            return None, None
        if len(resolved) == 1:
            return resolved[0], None
        return None, resolved
    quoted = re.match(_QUOTED, rest)
    if quoted:
        return _dequote(quoted.group(0)), None
    bare = re.match(r"^(\w+)", rest)
    if bare:
        name = bare.group(1)
        return string_defines.get(name, name), None
    return None, None


def parse_rpy(
    source: str,
    filename: str = "<string>",
    transforms: dict[str, list[str]] | None = None,
    string_defines: dict[str, str] | None = None,
    namebox_borders_tile: "tuple[tuple[int, int, int, int], bool] | None" = None,
    sprite_categories: SpriteLayerCategories | None = None,
    screen_resolution: tuple[int, int] | None = None,
) -> tuple[Script, list[Unsupported]]:
    """Parse Ren'Py source. Returns (Script, flagged constructs).

    `transforms` is the game-wide map of named `transform NAME:` bodies
    (see `scan_transform_declarations`) -- collected across *every* file in
    the game before any file's statements are parsed, since Ren'Py's
    transform namespace is flat across files and a transform can easily be
    declared in a file that sorts after the one that uses it. Defaults to
    empty for callers (and most tests) that don't need transform
    resolution at all.

    `string_defines` is the same idea for `NAME = "literal"` bindings (see
    `scan_string_defines`) -- both a top-level `define NAME = "literal"`
    and, confirmed against real content, a bare assignment inside an
    `init python:` block (e.g. Mice Tea's `screens/music.rpy` declaring
    every `sfx_X = "audio/..."` alias this way) -- used to resolve a bare
    identifier wherever a `play`/`queue`/`stop` statement's file argument
    isn't a literal string. Seeds this file's own incremental scan (which
    still runs, so a same-file define with no cross-file prepass still
    resolves for existing/simpler callers and tests)."""
    problems: list[Unsupported] = []
    cursor = Cursor(tokenize_lines(source))
    script = Script()
    script.default_font = _scan_default_font(source)
    script.default_text_cps = _scan_default_text_cps(source)
    script.textbox_image = _scan_textbox_image(source)
    script.namebox = _scan_namebox_frame(source, namebox_borders_tile)
    script.choice_idle, script.choice_hover = _scan_choice_button_frames(source)
    resolved_string_defines = dict(string_defines) if string_defines is not None else {}
    resolved_transforms = transforms if transforms is not None else {}
    resolved_sprite_categories = sprite_categories if sprite_categories is not None else SpriteLayerCategories()
    # Ren'Py's own historical pre-GUI-template engine default -- real-world
    # coverage (13-corpus survey) never actually hits this fallback (every
    # real game declares config.screen_width/height or calls gui.init
    # explicitly), but a game that truly declares neither still needs some
    # denominator for _resolve_atl_value's absolute-pixel rescaling.
    resolved_screen_resolution = screen_resolution if screen_resolution is not None else (800, 600)
    script.screen_resolution = resolved_screen_resolution

    while cursor.peek() is not None:
        line = cursor.peek()
        assert line is not None
        loc = SourceLocation(filename, line.lineno)

        if line.text.startswith("define ") and "Character(" not in line.text:
            _record_string_define(line.text, resolved_string_defines)

        if line.text.startswith("label ") and line.text.endswith(":"):
            cursor.advance()
            name = line.text[len("label"):-1].strip()
            body = _parse_label_body(
                cursor, line.indent, filename, problems, resolved_transforms, resolved_string_defines,
                resolved_sprite_categories, resolved_screen_resolution,
            )
            script.labels.append(Label(name=name, body=body, loc=loc))
        elif line.text.startswith("define ") and "Character(" in line.text:
            cursor.advance()
            cdef = _parse_character_def(line.text, loc, problems, resolved_string_defines)
            if cdef is not None:
                script.characters[cdef.varname] = cdef
        elif line.text.startswith("image ") and not line.text.endswith(":"):
            cursor.advance()
            image_match = _IMAGE_DEF_RE.match(line.text)
            composite_layers = _parse_composite_layers(image_match.group(2)) if image_match else None
            if image_match and composite_layers is not None:
                script.composites[image_match.group(1)] = composite_layers
            else:
                tag, path = _parse_image_def(line.text, loc, problems)
                if tag is not None:
                    script.images[tag] = path
        elif (line.text.startswith("default ") or line.text.startswith("define ")) and not line.text.endswith(":"):
            cursor.advance()
            set_node = _parse_default_define(line.text, loc, problems)
            if set_node is not None:
                script.top_level_sets.append(set_node)
        elif line.text.startswith("screen ") and line.text.endswith(":"):
            cursor.advance()
            header_match = _SCREEN_HEADER_RE.match(line.text)
            screen_name = header_match.group(1) if header_match else None
            if screen_name is not None and screen_name in _DEFAULT_SCREEN_NAMES:
                problems.append(
                    Unsupported(
                        text=line.text,
                        reason="default Ren'Py screen already provided natively by the engine, no action needed",
                        loc=loc,
                    )
                )
                _skip_child_block(cursor, line.indent)
            else:
                screen_def = (
                    _parse_screen_def(
                        screen_name, cursor, line.indent, loc, filename, problems, resolved_screen_resolution
                    )
                    if screen_name else None
                )
                if screen_def is not None:
                    script.screens.append(screen_def)
                else:
                    problems.append(
                        Unsupported(
                            text=line.text,
                            reason="custom screen uses constructs outside the supported subset (vbox/hbox, text, textbutton, if/elif/else) — needs native reimplementation",
                            loc=loc,
                        )
                    )
        elif line.text.startswith("transform ") and line.text.endswith(":"):
            # Declaration only -- already harvested game-wide by
            # scan_transform_declarations before any file's statements were
            # parsed (see parse_rpy's docstring), so there's nothing left
            # to do here but consume it without flagging a problem. Real
            # fidelity/approximation flagging happens at each *usage* site
            # (show/scene's ATL resolution), not the declaration -- a
            # transform that's never actually usable (e.g. a `repeat`d
            # animation) still correctly flags approximated wherever it's
            # referenced, so nothing is silently lost by staying quiet here.
            cursor.advance()
            _skip_child_block(cursor, line.indent)
        elif (line.text.startswith("init") or line.text.startswith("python")) and line.text.endswith(":"):
            # init python:/init -1 python hide:/init -2:/python early: blocks
            # -- arbitrary Python setup, most commonly gallery/music-room
            # extras and desktop window/save-directory config that's
            # irrelevant on 3DS anyway. A real, human-reimplementable (or
            # ignorable) feature, not unknown code.
            cursor.advance()
            problems.append(
                Unsupported(
                    text=line.text,
                    reason="init python block has no VNDS equivalent (needs native reimplementation, if needed at all)",
                    loc=loc,
                )
            )
            _skip_child_block(cursor, line.indent)
        elif line.text.startswith("translate") and line.text.endswith(":"):
            # translate LANG strings:/translate LANG some_label: -- per-
            # language localization data (old/new string pairs, or a
            # fully-translated copy of a label's dialogue). Irrelevant to
            # a single-language port -- unlike init python:, there's no
            # ambiguity about whether this ever needs native
            # reimplementation, so it's classified info, not manual.
            cursor.advance()
            problems.append(
                Unsupported(
                    text=line.text,
                    reason="translate block is localization data, not game content",
                    loc=loc,
                )
            )
            _skip_child_block(cursor, line.indent)
        else:
            cursor.advance()
            problems.append(Unsupported(text=line.text, reason="unsupported top-level statement", loc=loc))
            _skip_child_block(cursor, line.indent)

    return script, problems


def _parse_child_block(
    cursor: Cursor,
    parent_indent: int,
    filename: str,
    problems: list[Unsupported],
    transforms: dict[str, list[str]],
    string_defines: dict[str, str],
    sprite_categories: SpriteLayerCategories,
    screen_resolution: tuple[int, int],
) -> list[Node]:
    """Parse the block indented under a header line, if any."""
    nxt = cursor.peek()
    if nxt is None or nxt.indent <= parent_indent:
        return []
    return _parse_block(cursor, nxt.indent, filename, problems, transforms, string_defines, sprite_categories, screen_resolution)


def _parse_label_body(
    cursor: Cursor,
    label_indent: int,
    filename: str,
    problems: list[Unsupported],
    transforms: dict[str, list[str]],
    string_defines: dict[str, str],
    sprite_categories: SpriteLayerCategories,
    screen_resolution: tuple[int, int],
) -> list[Node]:
    """Parses a label's body -- unlike if/menu/while/python (which real
    Ren'Py's own lexer hard-errors on via `expect_block` if unindented), a
    `label` is a jump-target marker in the enclosing flat statement
    sequence, never a block owner -- it has no indentation requirement at
    all. If there's a real indented child, use it as-is (the common case,
    unchanged). Otherwise the label's real body is every following
    statement at its OWN indent, up to the next label at that indent (or a
    dedent/EOF) -- confirmed real content: 14 of Gender Bender DNA Twister
    Extreme's 18 story files write every label this way, with zero
    indentation anywhere in the file, and it's valid, working Ren'Py."""
    nxt = cursor.peek()
    if nxt is not None and nxt.indent > label_indent:
        return _parse_block(cursor, nxt.indent, filename, problems, transforms, string_defines, sprite_categories, screen_resolution)
    return _parse_block(cursor, label_indent, filename, problems, transforms, string_defines, sprite_categories, screen_resolution, stop_at_label=True)


def _skip_child_block(cursor: Cursor, parent_indent: int) -> None:
    """Consume (without recording) the block indented under an unsupported header,
    so indentation tracking doesn't desync for subsequent sibling statements."""
    nxt = cursor.peek()
    if nxt is None or nxt.indent <= parent_indent:
        return
    child_indent = nxt.indent
    while True:
        line = cursor.peek()
        if line is None or line.indent < child_indent:
            break
        cursor.advance()
        _skip_child_block(cursor, line.indent)


def _collect_indented_lines(cursor: Cursor, parent_indent: int) -> list[str]:
    """Consumes the block indented under a `show/scene X:` ATL header,
    returning its raw text lines (flat — real-world usage is a simple list
    of property-assignment lines, no nested `block:`/`parallel:` clauses)
    for _parse_atl_positioning to scan."""
    lines: list[str] = []
    nxt = cursor.peek()
    if nxt is None or nxt.indent <= parent_indent:
        return lines
    child_indent = nxt.indent
    while True:
        line = cursor.peek()
        if line is None or line.indent < child_indent:
            break
        lines.append(line.text)
        cursor.advance()
    return lines


def scan_transform_declarations(source: str) -> dict[str, list[str]]:
    """Standalone pre-pass collecting every top-level `transform NAME:`
    block's raw body lines, keyed by name -- Ren'Py's transform namespace
    is flat across every `.rpy` file in the game, and (confirmed against
    real content) a plain alphabetical file sort can easily parse a file
    that *uses* a transform before the file that *declares* it (e.g.
    `story/*.rpy` sorts before `transforms.rpy`). `cli.py`'s `parse_game`
    runs this across every file first, merges the results, and only then
    parses any file's statements, so every transform is already known
    regardless of declaration order.

    Reuses the same tokenizer/`_collect_indented_lines` machinery as the
    real parser rather than a from-scratch indentation scan. Parameterized
    transforms (`transform foo(x):`) are skipped -- none observed in real
    content; falls through to the existing "unsupported top-level
    statement" handling in `parse_rpy` if ever encountered. A `block:`/
    `choice:` sub-block's lines are flattened in just like any other
    property line (same documented assumption `_collect_indented_lines`
    already makes) -- harmless here, since the timed lines inside still
    correctly trigger `_atl_needs_approximation`'s flag wherever this
    transform ends up being used."""
    cursor = Cursor(tokenize_lines(source))
    transforms: dict[str, list[str]] = {}
    while cursor.peek() is not None:
        line = cursor.peek()
        assert line is not None
        if line.text.startswith("transform ") and line.text.endswith(":") and "(" not in line.text:
            name = line.text[len("transform "):-1].strip()
            cursor.advance()
            transforms[name] = _collect_indented_lines(cursor, line.indent)
        else:
            cursor.advance()
    return transforms


def scan_string_defines(source: str) -> dict[str, str]:
    """Standalone pre-pass collecting every `NAME = "literal"` binding
    resolvable as a bare-identifier audio filename (or, as
    `_record_string_define` already used this dict for, a `Character()`
    display-name argument) -- both Ren'Py's real top-level `define NAME =
    "literal"` form, and the equally common real-world pattern of a bare
    Python assignment inside an `init .../python:` block. Confirmed
    against Mice Tea: `screens/music.rpy` declares every `sfx_X =
    "audio/sfx/....ogg"` alias this way, not via `define` -- and, same
    reason as `scan_transform_declarations`, in a file that can easily
    sort *after* the files that reference it bare (e.g. `play sound
    sfx_paper`), so this needs the same game-wide, collect-before-parsing
    prepass rather than the parser's own single-file incremental scan."""
    cursor = Cursor(tokenize_lines(source))
    defines: dict[str, str] = {}
    while cursor.peek() is not None:
        line = cursor.peek()
        assert line is not None
        if line.text.startswith("define ") and not line.text.endswith(":"):
            _record_string_define(line.text, defines)
            cursor.advance()
        elif (line.text.startswith("init") or line.text.startswith("python")) and line.text.endswith(":"):
            cursor.advance()
            for body_line in _collect_indented_lines(cursor, line.indent):
                _record_string_define(body_line, defines)
        else:
            cursor.advance()
    return defines


_SCREEN_WIDTH_RE = re.compile(r"config\.screen_width\s*=\s*(\d+)")
_SCREEN_HEIGHT_RE = re.compile(r"config\.screen_height\s*=\s*(\d+)")
_GUI_INIT_RE = re.compile(r"gui\.init\(\s*(\d+)\s*,\s*(\d+)\s*\)")


def scan_screen_resolution(source: str) -> tuple[int, int] | None:
    """Ren'Py's declared design/authoring resolution -- either a direct
    `config.screen_width`/`config.screen_height` pair (older/simpler
    projects, e.g. real content: Jisei declares 1024x768 this way), or
    (the modern default-project-template convention, confirmed real
    content: 7 of 13 surveyed games) `gui.init(width, height)`, which sets
    both internally. Needed to correctly rescale an *absolute-pixel* ATL
    position value (see `_resolve_atl_value`'s docstring for why this
    matters) -- a fractional xalign/yalign is already resolution-
    independent and needs no such context at all."""
    width_match = _SCREEN_WIDTH_RE.search(source)
    height_match = _SCREEN_HEIGHT_RE.search(source)
    if width_match and height_match:
        return int(width_match.group(1)), int(height_match.group(1))
    init_match = _GUI_INIT_RE.search(source)
    if init_match:
        return int(init_match.group(1)), int(init_match.group(2))
    return None


_BARE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_]\w*$")


def _expand_transform_refs(
    lines: list[str], transforms: dict[str, list[str]], _depth: int = 0
) -> list[str]:
    """Splices a named transform's own ATL lines in place of a bare
    identifier line that names it -- Ren'Py's real usage, confirmed against
    Mice Tea, is a bare transform-name line inside a `show/scene X:` block
    (e.g. `bs_centerleft3` on its own line) composing several transforms
    together. Recursive (a transform can itself reference another),
    depth-guarded against accidental self-reference -- no real content
    nests more than one level deep, so 5 is a generous ceiling, not a real
    limit. A name that isn't actually a declared transform (Ren'Py's own
    built-in "left"/"center"/"right", or anything this game never defines)
    passes through unchanged and is simply ignored by the prop scanners."""
    if _depth > 5:
        return lines
    expanded: list[str] = []
    for line in lines:
        name = line.strip()
        if _BARE_IDENTIFIER_RE.match(name) and name in transforms:
            expanded.extend(_expand_transform_refs(transforms[name], transforms, _depth + 1))
        else:
            expanded.append(line)
    return expanded


def _resolve_atl_lines(
    position: str | None, block_lines: list[str], transforms: dict[str, list[str]]
) -> list[str]:
    """Builds the fully expanded ATL line list for a show/scene statement:
    name(s) from the `at` clause (Ren'Py's own "base state, then overrides"
    order -- confirmed against real content combining both, e.g. `show
    gavin at faceleft, offscreenright_male:` followed by its own indented
    override lines) followed by the block's own literal lines, with every
    transform reference (recursively) expanded in place."""
    at_names = [n.strip() for n in position.split(",")] if position else []
    return _expand_transform_refs(at_names + block_lines, transforms)


_ATL_TIMING_LINE_RE = re.compile(r"^(linear|ease|easein|easeout)\s+([\d.]+)\s*(.*)$")
_ATL_PROP_TOKEN_RE = re.compile(
    r"\b(xalign|xcenter|xanchor|xpos|yalign|ycenter|yanchor|ypos|alpha|zoom|xzoom|yzoom|rotate)\s+(-?[\d.]+)"
)
_ATL_PYTHON_TOUCH_RE = re.compile(r"\b(if|for|python|renpy\.)\b")

# Engine property name + fraction/unit -> pixel-space conversion for each
# recognized ATL property (VN3DS-spec.md §9.1's sprite state table is
# x/y/r/sx/sy/alpha in the engine's own 400x240 pixel/radian/scale-factor
# space, not Ren'Py's 0.0-1.0 alignment fractions or degree-based rotate).
# Used only by the *animated* (timed-step) path, `_parse_atl_animation` --
# the static path (`_parse_atl_positioning`) tracks anchor/position pairs
# per-property instead (see its own docstring for why a single mapping
# isn't enough there). xcenter/xanchor/xpos all collapse to the same "x"
# key as xalign (the engine always draws a sprite center-anchored
# horizontally -- see images.moon's draw_foreground -- so a bare xpos with
# no separate anchor concept is already the existing, deliberate
# approximation xalign itself makes); ycenter/yanchor/ypos collapse to
# "yalign" the same way, on the same anchor==position simplification,
# specific to *animated* keyframes only (the static path resolves the two
# independently -- see `_parse_atl_positioning`).
def _atl_prop_to_engine(prop: str, value: float) -> tuple[str, float]:
    if prop in ("xalign", "xcenter", "xanchor", "xpos"): return "x", round(value * 400, 2)
    if prop in ("yalign", "ycenter", "yanchor", "ypos"):
        # Deliberately *not* converted to a pixel "y" here (unlike xalign):
        # that would need the sprite's actual rendered height, which isn't
        # known until the asset pipeline resolves and sizes the real image,
        # long after this parses the .rpy source. Foreground art's height
        # is never capped to the screen (pipeline.py's
        # _FOREGROUND_MAX_WIDTH only fills width, height is left free) --
        # the real symptom on hardware: `yalign 1.0 -> yalign 0.0`
        # pixel-baked as `y=240 -> y=0` panned across only the screen's own
        # height instead of the image's real (often much taller) height,
        # so it started already off-screen and never covered anywhere near
        # its full range. Emitting the raw 0.0-1.0 fraction and resolving
        # it against the real loaded image's height at animation time
        # (images.moon's "anim_end") is correct regardless of how tall any
        # particular sprite ends up being.
        return "yalign", value
    if prop == "zoom": return "sx", value  # caller also mirrors this onto sy
    if prop == "xzoom": return "sx", value
    if prop == "yzoom": return "sy", value
    if prop == "rotate": return "r", round(value * 3.14159265 / 180, 4)
    return "alpha", value  # prop == "alpha"


def _atl_needs_approximation(lines: list[str]) -> bool:
    """True if a show/scene ATL block has a timed step or touches inline
    Python -- the only two things a static position/zoom/rotate/alpha scan
    (`_parse_atl_positioning`) can't already capture and actually apply.
    Static zoom/rotate/alpha values are *not* flagged here (unlike before
    this feature existed): they're now genuinely applied at setimg time via
    the engine's existing sx/sy/r/alpha sprite state, not silently dropped,
    so there's nothing approximate about them anymore."""
    for line in lines:
        if _ATL_TIMING_LINE_RE.match(line) or _ATL_PYTHON_TOUCH_RE.search(line):
            return True
    return False


@dataclass
class _StaticATLProps:
    """The final (last-value-wins) static state of a show/scene ATL block,
    generalizing a single `yalign` fraction into an independent (position,
    anchor) pair -- see `_parse_atl_positioning`'s docstring for why."""

    xalign: float | None = None  # x position fraction (xanchor is not tracked -- see _atl_prop_to_engine)
    yalign: float | None = None  # y position fraction (Ren'Py's ypos, or the position half of yalign/ycenter)
    yanchor: float | None = None  # y anchor fraction (Ren'Py's yanchor, or the anchor half of yalign/ycenter)
    sx: float | None = None
    sy: float | None = None
    rotate: float | None = None
    alpha: float | None = None

    def is_empty(self) -> bool:
        return all(
            v is None for v in (self.xalign, self.yalign, self.yanchor, self.sx, self.sy, self.rotate, self.alpha)
        )


_ATL_POSITION_PROPS_X = {"xalign", "xcenter", "xanchor", "xpos"}
_ATL_POSITION_PROPS_Y = {"yalign", "ycenter", "yanchor", "ypos"}


def _resolve_atl_value(prop: str, raw_value: str, screen_resolution: tuple[int, int]) -> float:
    """Ren'Py's real position semantics, confirmed against real content
    (13-corpus survey -- every game has hundreds to ~1700 real occurrences
    of the bare-int case): a float literal (e.g. "0.5") is already a
    fraction of the container -- unchanged, existing behavior. A bare int
    literal (e.g. "680") is an ABSOLUTE PIXEL offset in the game's own
    declared design resolution (`config.screen_width`/`config.screen_height`,
    or `gui.init(w, h)` -- see `scan_screen_resolution`), not a fraction of
    the engine's fixed 400x240 target space at all. Converting it to the
    *equivalent fraction* here (dividing by the source game's own
    declared width/height) means every existing downstream consumer --
    `_atl_prop_to_engine`'s `value * 400` for x, and the y-axis's raw-
    fraction-resolved-against-the-real-sprite-height path -- keeps working
    completely unchanged; this is the one place that needs to know the
    game's own resolution at all. Confirmed real-hardware-relevant: Jisei
    declares 1024x768 and its own `ypos 651` was previously computed as
    `651 * 240 = 156240` (wildly off-screen) instead of the correct
    `651/768 * 240 ~= 203`."""
    if "." in raw_value:
        return float(raw_value)
    screen_width, screen_height = screen_resolution
    if prop in _ATL_POSITION_PROPS_X:
        return int(raw_value) / screen_width
    if prop in _ATL_POSITION_PROPS_Y:
        return int(raw_value) / screen_height
    return float(raw_value)  # zoom/xzoom/yzoom/rotate/alpha: no absolute-pixel meaning either way


def _parse_atl_positioning(lines: list[str], screen_resolution: tuple[int, int]) -> _StaticATLProps | None:
    """Scans a (possibly transform-expanded) show/scene ATL block for its
    final static properties, taking the *last* value seen for each --
    animation, if any, is separately extracted by `_parse_atl_animation`.

    Ren'Py's real position model is an independent (anchor, position) pair
    per axis: `yalign V` is shorthand for setting *both* `yanchor` and
    `ypos` to `V`; `ycenter V` sets `yanchor 0.5` and `ypos V`; `yanchor`/
    `ypos` alone set only their own half. A single collapsed "yalign
    fraction" (this function's pre-transform-support behavior) is only
    correct when anchor and position happen to coincide -- real content
    breaks that assumption directly (a named transform overriding *just*
    `ypos` after a `yalign 1.0` shorthand, e.g. Mice Tea's transforms.rpy:
    `xcenter 0.15 yalign 1.0 ypos 1.2 zoom 1.0` -- anchor stays 1.0, only
    the position moves to 1.2). `yanchor` defaults to Ren'Py's own real
    default (0.0, top-anchored) when never set by yalign/yanchor/ycenter,
    *not* to the position fraction's own value.

    Horizontal anchor is deliberately not tracked at all -- the engine
    already always draws sprites center-anchored horizontally regardless
    of the source ATL's xanchor (an existing, pre-transform-support
    simplification also made for plain `xalign`) -- so `xpos` is the only
    horizontal value that matters.

    Returns None if the block has no static properties at all (nothing to
    apply -- distinct from merely having no *position*, since a zoom/
    rotate/alpha-only block is now real, applicable content)."""
    xpos: float | None = None
    yanchor: float | None = None
    ypos: float | None = None
    sx: float | None = None
    sy: float | None = None
    rotate: float | None = None
    alpha: float | None = None
    for line in lines:
        for prop, raw_value in _ATL_PROP_TOKEN_RE.findall(line):
            value = _resolve_atl_value(prop, raw_value, screen_resolution)
            if prop == "xalign": xpos = value
            elif prop == "xcenter": xpos = value
            elif prop == "xanchor": pass  # not tracked -- see docstring
            elif prop == "xpos": xpos = value
            elif prop == "yalign": yanchor = value; ypos = value
            elif prop == "ycenter": yanchor = 0.5; ypos = value
            elif prop == "yanchor": yanchor = value
            elif prop == "ypos": ypos = value
            elif prop == "zoom": sx = value; sy = value
            elif prop == "xzoom": sx = value
            elif prop == "yzoom": sy = value
            elif prop == "rotate": rotate = value
            elif prop == "alpha": alpha = value
    result = _StaticATLProps(
        xalign=xpos,
        yalign=ypos,
        yanchor=(yanchor if yanchor is not None else (0.0 if ypos is not None else None)),
        sx=sx, sy=sy, rotate=rotate, alpha=alpha,
    )
    return None if result.is_empty() else result


# Exactly these two property-set shapes get an exact (non-approximated)
# preset match; anything else touched by a timed step (position, zoom,
# rotation, multi-step chains) falls back to the general keyframe form.
def _match_fade_preset(initial: dict[str, float], step_props: dict[str, float]) -> str | None:
    if set(step_props.keys()) != {"alpha"}:
        return None
    from_alpha = initial.get("alpha", 1.0)
    to_alpha = step_props["alpha"]
    if from_alpha <= 0.01 and to_alpha >= 0.99:
        return "enter_fade"
    if from_alpha >= 0.99 and to_alpha <= 0.01:
        return "exit_fade"
    return None


def _parse_atl_animation(lines: list[str], screen_resolution: tuple[int, int]) -> AnimSpec | None:
    """Extracts a VN3DS-spec.md §9.1 animation from a `show X:` ATL block's
    timed (`linear`/`ease*`) steps. Property-only lines (no timing keyword)
    before the first timed step establish the initial state (keyframe at
    t=0); each timed step becomes a subsequent keyframe at its cumulative
    time, converted to the engine's 0.0-1.0 normalised range. A two-step
    alpha-only fade matches `enter_fade`/`exit_fade` exactly (spec's own
    called-out case); anything else (position, zoom, rotation, 3+ steps,
    or a block that touches `if`/`for`/inline Python) falls back to the
    general keyframe form, which the caller flags `approximated` — a real,
    working animation either way, never silently dropped.

    Returns None if the block has no timed step at all (nothing to
    animate — `_parse_atl_positioning` already covers a pure static
    position)."""
    initial: dict[str, float] = {}
    steps: list[tuple[float, dict[str, float]]] = []  # (duration, engine-space props)
    touched_python = False
    for line in lines:
        if _ATL_PYTHON_TOUCH_RE.search(line):
            touched_python = True
        timing_match = _ATL_TIMING_LINE_RE.match(line)
        if timing_match:
            duration = float(timing_match.group(2))
            props = {}
            for prop, value in _ATL_PROP_TOKEN_RE.findall(timing_match.group(3)):
                engine_prop, engine_value = _atl_prop_to_engine(prop, _resolve_atl_value(prop, value, screen_resolution))
                props[engine_prop] = engine_value
                if prop == "zoom":
                    props["sy"] = engine_value
            steps.append((duration, props))
        elif not steps:
            for prop, value in _ATL_PROP_TOKEN_RE.findall(line):
                engine_prop, engine_value = _atl_prop_to_engine(prop, _resolve_atl_value(prop, value, screen_resolution))
                initial[engine_prop] = engine_value
                if prop == "zoom":
                    initial["sy"] = engine_value
    if not steps:
        return None

    total_duration = sum(duration for duration, _ in steps)
    if total_duration <= 0:
        return None

    if len(steps) == 1 and not touched_python:
        only_duration, only_props = steps[0]
        preset = _match_fade_preset(initial, only_props)
        if preset is not None:
            return AnimSpec(duration=only_duration, preset=preset)

    keyframes: list[tuple[float, dict[str, float]]] = [(0.0, initial)] if initial else []
    cumulative = 0.0
    for duration, props in steps:
        cumulative += duration
        keyframes.append((round(cumulative / total_duration, 4), props))
    return AnimSpec(duration=total_duration, keyframes=keyframes)


def _parse_block(
    cursor: Cursor,
    indent: int,
    filename: str,
    problems: list[Unsupported],
    transforms: dict[str, list[str]],
    string_defines: dict[str, str],
    sprite_categories: SpriteLayerCategories,
    screen_resolution: tuple[int, int],
    stop_at_label: bool = False,
) -> list[Node]:
    nodes: list[Node] = []
    while True:
        line = cursor.peek()
        if line is None or line.indent < indent:
            break
        if stop_at_label and line.indent == indent and line.text.startswith("label ") and line.text.endswith(":"):
            break
        cursor.advance()
        _append_statement_result(nodes, _parse_statement(line, cursor, filename, problems, transforms, string_defines, sprite_categories, screen_resolution))
    return _try_convert_ui_menus(nodes, problems)


def _match_ui_menu(nodes: list[Node], start: int) -> tuple[Menu, int, list[Unsupported]] | None:
    """Tries to match Ren'Py's legacy `ui.vbox`/`ui.textbutton`/`ui.close` +
    `ui.interact()` + `if result == N:` idiom starting at `nodes[start]`,
    converting it into an ordinary Menu (same disposition as a real
    `menu:`). Returns (menu, nodes_consumed, unsupported_nodes_to_drop) or
    None if the run doesn't match cleanly — bails out rather than risking
    a partially-wrong conversion, leaving the original nodes (already
    flagged Unsupported) untouched."""
    i = start
    buttons: dict[int, str] = {}
    consumed: list[Unsupported] = []
    result_var: str | None = None

    while i < len(nodes):
        node = nodes[i]
        if not isinstance(node, Unsupported):
            break
        text = node.text.strip()

        if _UI_NOISE_RE.match(text):
            consumed.append(node)
            i += 1
            continue

        button_match = _UI_TEXTBUTTON_RE.match(text)
        if button_match:
            label, index = button_match.groups()
            if index is not None:
                buttons[int(index)] = _dequote(label)
            consumed.append(node)
            i += 1
            continue

        interact_match = _UI_INTERACT_RE.match(text)
        if interact_match:
            result_var = interact_match.group(1)
            consumed.append(node)
            i += 1
            break

        break

    if result_var is None or not buttons:
        return None
    if i >= len(nodes) or not isinstance(nodes[i], If):
        return None

    if_node = nodes[i]
    if any(branch.condition is None for branch in if_node.branches):
        return None  # a trailing `else` can't be safely represented as a menu choice

    choices: list[MenuChoice] = []
    for branch in if_node.branches:
        assert branch.condition is not None
        cond_match = re.fullmatch(rf"\({re.escape(result_var)} == (\d+)\)", branch.condition)
        if not cond_match:
            return None  # a condition we can't correlate to a button -- bail out entirely
        label = buttons.get(int(cond_match.group(1)))
        if label is None:
            return None
        choices.append(MenuChoice(text=label, body=branch.body, loc=if_node.loc))

    return Menu(choices=choices, loc=if_node.loc), (i - start) + 1, consumed


def _try_convert_ui_menus(nodes: list[Node], problems: list[Unsupported]) -> list[Node]:
    result: list[Node] = []
    i = 0
    while i < len(nodes):
        match = _match_ui_menu(nodes, i)
        if match is None:
            result.append(nodes[i])
            i += 1
            continue
        menu, consumed_count, dropped = match
        problems[:] = [p for p in problems if not any(p is d for d in dropped)]
        result.append(menu)
        i += consumed_count
    return result


def _append_statement_result(nodes: list[Node], result: Node | list[Node]) -> None:
    # _parse_statement almost always returns a single Node -- the one
    # exception is the `charname attribute "text"` say-shorthand, which
    # expands into a synthesized [Show, Say] pair.
    if isinstance(result, list):
        nodes.extend(result)
    else:
        nodes.append(result)


def _parse_statement(
    line: RawLine,
    cursor: Cursor,
    filename: str,
    problems: list[Unsupported],
    transforms: dict[str, list[str]],
    string_defines: dict[str, str],
    sprite_categories: SpriteLayerCategories,
    screen_resolution: tuple[int, int],
) -> Node | list[Node]:
    text = line.text
    loc = SourceLocation(filename, line.lineno)

    if text == "return" or text.startswith("return "):
        return Return(loc=loc)
    if text.startswith("jump "):
        return Jump(target=text[len("jump "):].strip(), loc=loc)
    if text.startswith("call "):
        return Call(target=text[len("call "):].strip(), loc=loc)
    if text.startswith("scene "):
        if text.endswith(":"):
            image, position, transition = _parse_image_statement(text[len("scene "):-1])
            raw_lines = _resolve_atl_lines(position, _collect_indented_lines(cursor, line.indent), transforms)
            atl = _parse_atl_positioning(raw_lines, screen_resolution)
            # Scene never applies sx/sy/rotate/alpha (backgrounds are always
            # full-screen, §5.1) -- unlike Show's broader "any static prop at
            # all" check below, a block with e.g. only a timed alpha step and
            # no xalign/yalign/ypos/xcenter/... genuinely has nothing Scene
            # can use, so the bail-out checks position specifically rather
            # than `atl is None` (which a stray alpha/zoom/rotate value alone
            # would satisfy, silently dropping the block's real content).
            if atl is None or (atl.xalign is None and atl.yalign is None):
                node = Unsupported(
                    text=text,
                    reason="ATL block has no recognizable static/final position (xalign/yalign)",
                    loc=loc,
                )
                problems.append(node)
                return node
            return Scene(
                image=image, position=position, transition=transition, loc=loc,
                xalign=atl.xalign, yalign=atl.yalign, yanchor=atl.yanchor,
                approximated_atl=_atl_needs_approximation(raw_lines),
            )
        image, position, transition = _parse_image_statement(text[len("scene "):])
        raw_lines = _resolve_atl_lines(position, [], transforms)
        atl = _parse_atl_positioning(raw_lines, screen_resolution)
        if atl is not None and (atl.xalign is not None or atl.yalign is not None):
            return Scene(
                image=image, position=position, transition=transition, loc=loc,
                xalign=atl.xalign, yalign=atl.yalign, yanchor=atl.yanchor,
                approximated_atl=_atl_needs_approximation(raw_lines),
            )
        return Scene(image=image, position=position, transition=transition, loc=loc)
    if text.startswith("show "):
        if text.endswith(":"):
            image, position, transition = _parse_image_statement(text[len("show "):-1])
            raw_lines = _resolve_atl_lines(position, _collect_indented_lines(cursor, line.indent), transforms)
            atl = _parse_atl_positioning(raw_lines, screen_resolution)
            anim = _parse_atl_animation(raw_lines, screen_resolution)
            if atl is None and anim is None:
                node = Unsupported(
                    text=text,
                    reason="ATL block has no recognizable static/final position (xalign/yalign) or animation",
                    loc=loc,
                )
                problems.append(node)
                return node
            approximated = _atl_needs_approximation(raw_lines) and (anim is None or anim.preset is None)
            return Show(
                image=image, position=position, transition=transition, loc=loc,
                xalign=atl.xalign if atl else None,
                yalign=atl.yalign if atl else None,
                yanchor=atl.yanchor if atl else None,
                sx=atl.sx if atl else None,
                sy=atl.sy if atl else None,
                rotate=atl.rotate if atl else None,
                alpha=atl.alpha if atl else None,
                approximated_atl=approximated, anim=anim,
            )
        image, position, transition = _parse_image_statement(text[len("show "):])
        raw_lines = _resolve_atl_lines(position, [], transforms)
        atl = _parse_atl_positioning(raw_lines, screen_resolution)
        if atl is not None:
            return Show(
                image=image, position=position, transition=transition, loc=loc,
                xalign=atl.xalign, yalign=atl.yalign, yanchor=atl.yanchor,
                sx=atl.sx, sy=atl.sy, rotate=atl.rotate, alpha=atl.alpha,
                approximated_atl=_atl_needs_approximation(raw_lines),
            )
        return Show(image=image, position=position, transition=transition, loc=loc)
    if text.startswith("hide "):
        if text.endswith(":"):
            _collect_indented_lines(cursor, line.indent)  # ATL on hide is rare; consume and ignore
            image, _position, transition = _parse_image_statement(text[len("hide "):-1])
            return Hide(image=image, transition=transition, loc=loc)
        image, _position, transition = _parse_image_statement(text[len("hide "):])
        return Hide(image=image, transition=transition, loc=loc)
    if text == "menu:" or text.startswith("menu "):
        return _parse_menu(cursor, line.indent, filename, loc, problems, transforms, string_defines, sprite_categories, screen_resolution)
    if text.startswith("label ") and text.endswith(":"):
        # nested label — unusual in Ren'Py but not forbidden; handle the same way
        name = text[len("label"):-1].strip()
        body = _parse_label_body(cursor, line.indent, filename, problems, transforms, string_defines, sprite_categories, screen_resolution)
        return Label(name=name, body=body, loc=loc)
    if text.startswith("if ") and text.endswith(":"):
        return _parse_if_chain(text, line.lineno, line.indent, cursor, filename, problems, transforms, string_defines, sprite_categories, screen_resolution)
    if text.startswith("while ") and text.endswith(":"):
        return _parse_while(text, line.lineno, line.indent, cursor, filename, problems, transforms, string_defines, sprite_categories, screen_resolution)
    if text.startswith("$ ChangePortrait("):
        portrait_call = parse_change_portrait_call(text, sprite_categories, loc)
        if portrait_call is not None:
            return PortraitUpdate(
                name=portrait_call.name,
                blink=portrait_call.blink,
                transition=portrait_call.transition,
                updates=tuple(
                    PortraitLayerUpdateIR(
                        slot=u.slot,
                        value=u.value,
                        order_index=u.order_index,
                        category=u.category,
                        is_expression_folder=u.is_expression_folder,
                    )
                    for u in portrait_call.updates
                ),
                tint=portrait_call.tint,
                loc=loc,
            )
        # An unresolvable ChangePortrait call (non-literal chara/slot value)
        # falls through to the generic Unsupported handling below, same as
        # any other unresolvable construct in this converter.
    if text.startswith("$ "):
        special = _parse_special_dollar_statement(text[2:], loc, problems, string_defines)
        if special is not None:
            return special
        set_node = _parse_set_statement(text[2:], loc)
        if set_node is not None:
            return set_node
        # fall through to the generic Unsupported handling below

    if (text.startswith("default ") or text.startswith("define ")) and "Character(" not in text:
        # `default`/`define` of a literal declared *inside* a label's body
        # (not just at the file's top level) -- real content found in the
        # wild (a route-tracking flag set partway through a scene, e.g.
        # `default afd24_route = "afd24_nonfurry"`), previously fell
        # through to the generic Unsupported handling because only the
        # top-level parse loop recognized these prefixes, not this
        # function (used for statements inside a label body). Applied at
        # this exact point in the script as a plain Set -- a minor
        # simplification of "default"'s real "only if not already set"
        # save-compatibility semantics, but VNDS has no such concept
        # either way and this matches how a fresh playthrough behaves.
        set_node = _parse_default_define(text, loc, problems)
        if set_node is not None:
            return set_node
        return Unsupported(text=text, reason=problems[-1].reason if problems else "unsupported statement", loc=loc)

    with_match = _STANDALONE_WITH_RE.match(text)
    if with_match:
        name = with_match.group(1)
        if name == "None":
            # Ren'Py's own idiom for "explicitly no transition" -- a
            # genuine no-op (real content: 153 uses in Mice Tea alone),
            # not an unrecognized transition *name* to downgrade to a real
            # dissolve.
            node = Unsupported(text=text, reason="with None has no effect, treated as a no-op", loc=loc)
            problems.append(node)
            return node
        return Transition(name=name, loc=loc)

    play_match = _PLAY_QUEUE_RE.match(text)
    if play_match:
        verb, channel, rest = play_match.groups()
        file_, choices = _parse_play_file_spec(rest, string_defines)
        if file_ is not None or choices:
            resolved_file = file_ if file_ is not None else choices[0]
            return Play(
                channel=channel, file=resolved_file, is_queue=(verb == "queue"), loc=loc, choices=choices
            )

    voice_match = _VOICE_RE.match(text)
    if voice_match:
        return Play(channel="voice", file=_dequote(voice_match.group(1)), is_queue=False, loc=loc)

    stop_match = _STOP_RE.match(text)
    if stop_match:
        return Stop(channel=stop_match.group(1), loc=loc)

    pause_match = _PAUSE_RE.match(text)
    if pause_match:
        seconds = float(pause_match.group(1)) if pause_match.group(1) else None
        return Pause(seconds=seconds, loc=loc)

    window_match = _WINDOW_RE.match(text)
    if window_match:
        return Window(state=window_match.group(1), loc=loc)

    day_match = _DAY_RE.match(text)
    if day_match:
        day_number, subtitle, mood = day_match.groups()
        return DayCard(
            day_number=_dequote(day_number),
            subtitle=_dequote(subtitle),
            mood=_dequote(mood) if mood else "default",
            loc=loc,
        )

    subchapter_match = _SUBCHAPTER_RE.match(text)
    if subchapter_match:
        return SubchapterCard(message=_dequote(subchapter_match.group(1)), loc=loc)

    if _SUBCHAPTER_HIDE_RE.match(text):
        return SubchapterHide(loc=loc)

    if _RESET_AUDIO_RE.match(text):
        return ResetAudio(loc=loc)

    the_end_match = _THE_END_RE.match(text)
    if the_end_match:
        return TheEndCard(title=_dequote(the_end_match.group(1)), loc=loc)

    if _PLACEHOLDER_RE.match(text):
        return Placeholder(loc=loc)

    say = _parse_say(text)
    if say is not None:
        who, what, attr_splittable = say
        what = _translate_text_tags(what, loc, problems)
        if attr_splittable and who is not None and len(who.split()) > 1:
            # `charname attribute "text"` shorthand -- Ren'Py's combined
            # show+say idiom (e.g. `ellen confused "No."` is `show ellen
            # confused` + `ellen "No."` in one line). Split off the real
            # speaker name (first token) for the Say -- vnds_writer.py's
            # _resolve_speaker does a `who in characters` dict lookup keyed
            # by the exact character variable name, so gluing attributes
            # into `who` would break nameplate/color resolution. The full
            # "name attr1 attr2" string becomes the synthesized Show's
            # image, matching _parse_image_statement's existing convention
            # of treating a name+attributes combo as one opaque string.
            speaker = who.split()[0]
            return [
                Show(image=who, position=None, loc=loc),
                Say(who=speaker, what=what, loc=loc),
            ]
        return Say(who=who, what=what, loc=loc)

    if text.startswith("translate") and text.endswith(":"):
        # Same reasoning as parse_rpy's top-level translate branch -- a
        # translate block can appear nested inside a label body too.
        node = Unsupported(
            text=text,
            reason="translate block is localization data, not game content",
            loc=loc,
        )
        problems.append(node)
        _skip_child_block(cursor, line.indent)
        return node

    if text == "python:" or (text.startswith("python ") and text.endswith(":")):
        # A bare python: block mid-scene (as opposed to top-level init
        # python:/python early:, handled by parse_rpy) -- still arbitrary
        # Python that might matter, so classified manual like init python:
        # rather than falling to the generic unsupported-statement catch-all.
        node = Unsupported(
            text=text,
            reason="python block has no VNDS equivalent (needs native reimplementation, if needed at all)",
            loc=loc,
        )
        problems.append(node)
        _skip_child_block(cursor, line.indent)
        return node

    node = Unsupported(text=text, reason="unsupported statement", loc=loc)
    problems.append(node)
    _skip_child_block(cursor, line.indent)
    return node


def _parse_image_statement(rest: str) -> tuple[str, str | None, str | None]:
    rest = rest.strip()
    transition = None
    with_match = _WITH_RE.search(rest)
    if with_match:
        transition = rest[with_match.end():].strip() or None
        # Ren'Py's own idiom for "explicitly no transition" (real content:
        # 153 uses in Mice Tea alone) -- not an unrecognized transition
        # *name* to downgrade to a dissolve, which would otherwise show a
        # real fade where the source explicitly asked for none at all.
        if transition == "None":
            transition = None
        rest = rest[: with_match.start()].strip()
    at_match = _AT_RE.search(rest)
    position = None
    if at_match:
        position = at_match.group(1)
        rest = rest[: at_match.start()].strip()
    return rest, position, transition


def _parse_say(text: str) -> tuple[str | None, str, bool] | None:
    # The third element marks whether `who` is eligible for the
    # `charname attribute "text"` shorthand split (see its caller in
    # _parse_statement) -- only true for the bare-word-sequence form
    # (_SAY_RE); _SAY_NAMED_RE's `who` is a quoted literal display name
    # (e.g. `"Mysterious Stranger" "Hello."`), where a space is just part
    # of the name, never an attribute separator.
    named = _SAY_NAMED_RE.match(text)
    if named:
        who, what = named.groups()
        return _dequote(who), _dequote(what), False
    plain = _SAY_RE.match(text)
    if plain:
        who, what = plain.groups()
        return who, _dequote(what), True
    return None


_STYLE_OPEN_ESCAPE = {"b": "x1b[1m", "i": "x1b[3m"}
_STYLE_CLOSE_ESCAPE = {"b": "x1b[22m", "i": "x1b[23m"}
_DEFAULT_PAUSE_SECONDS = 1.0  # bare {w}/{p} with no explicit duration


def _parse_pause_duration(value: str | None) -> float:
    if value:
        try:
            return abs(float(value))
        except ValueError:
            pass
    return _DEFAULT_PAUSE_SECONDS


def _strip_alt_spans(text: str) -> str:
    """Removes `{alt}...{/alt}` spans *entirely* (tag markers + content) --
    Ren'Py's self-voicing-only text (read by a screen reader in place of
    the surrounding text) has no visual manifestation without a TTS system
    this engine doesn't have, so both the tag and its content must go,
    unlike every other tag (which only strips the markers, keeping content
    visible). Confirmed real content: `Character("{i}(Margaret){/i}{alt}
    Thinking{/alt}", ...)` -- the name must render as "(Margaret)", not
    "(Margaret) Thinking" (the previous behavior, since only the `{alt}`/
    `{/alt}` markup itself was ever stripped, never its content)."""
    result: list[str] = []
    i = 0
    depth = 0
    while i < len(text):
        match = _TEXT_TAG_RE.match(text, i)
        if match and match.group(2) == "alt":
            depth = depth + 1 if match.group(1) != "/" else max(0, depth - 1)
            i = match.end()
            continue
        if depth == 0:
            result.append(text[i])
        i += 1
    return "".join(result)


def _translate_text_tags(text: str, loc: SourceLocation, problems: list[Unsupported]) -> str:
    """Translates Ren'Py's supported inline text tags (VN3DS-spec.md §6:
    {b}{i}{color}{w}{p}{size}, plus {alt}/{noalt}) into VN3DS's own
    engine-level escape convention (src/engine/text/text_color.moon's
    extended ANSI-style codes) instead of passing the raw `{tag}` markup
    through unchanged -- there was never an engine-side renderer to
    interpret it, so real content showed literal, unrendered brace
    characters on hardware. Real content drove every case:
    - {color=#hex}/{/color}, {b}/{/b}, {i}/{/i} -> colorify's color/bold/
      italic escape codes (arbitrary hex color; real ANSI SGR bold/italic
      on/off, composable with each other and with color).
    - {w}/{w=N}/{p}/{p=N} -> a zero-width pause escape (text.moon models
      it as extra typewriter-reveal budget, no separate timer needed).
    - {alt}/{noalt} have no visual effect without a TTS system this engine
      doesn't have -- {alt}...{/alt} strips its *content* too (see
      _strip_alt_spans), {noalt} strips only its own markers.
    - {size=...}/{font=...} (no per-run font-size or second-font-file
      support) strip to plain text, now correctly flagged -- previously
      silently passed through *unflagged* as literal, unrendered braces
      (worse than a normal unknown tag, which was at least flagged).
    - anything else unrecognized strips to plain text, flagged (unchanged
      from before)."""
    text = _strip_alt_spans(text)

    def replace(match: re.Match[str]) -> str:
        is_close = match.group(1) == "/"
        name = match.group(2)
        value = match.group(3)

        if name == "noalt":
            return ""
        if name == "color":
            if is_close:
                return "x1b[0m"
            hexval = (value or "").lstrip("#")
            return f"x1b[#{hexval.lower()}m" if len(hexval) == 6 else ""
        if name in ("b", "i"):
            return (_STYLE_CLOSE_ESCAPE if is_close else _STYLE_OPEN_ESCAPE)[name]
        if name in ("w", "p"):
            if is_close:
                return ""  # {w}/{p} are self-closing in real content -- no {/w}/{/p} to handle
            return f"x1b[P{_parse_pause_duration(value)}m"
        if name in ("size", "font"):
            if not is_close:
                problems.append(
                    Unsupported(
                        text=match.group(0),
                        reason=(
                            f"unsupported text tag {match.group(0)} stripped "
                            "(no per-run font-size/font-file support)"
                        ),
                        loc=loc,
                    )
                )
            return ""
        problems.append(
            Unsupported(
                text=match.group(0),
                reason=f"unknown text tag {match.group(0)} stripped",
                loc=loc,
            )
        )
        return ""

    return _TEXT_TAG_RE.sub(replace, text)


_SCREEN_TEXTBUTTON_RE = re.compile(rf'^textbutton\s+({_QUOTED})\s+action\s+(.+)$')

# imagemap/hotspot (VN3DS-spec.md's pulled-forward Phase 5.1 slice, extended):
# `ground "path" [idle "path"] [hover "path"]` -- idle/hover are parsed but
# discarded; real 3DS hardware is touch-only, no continuous mouse hover, so
# only `ground` is ever drawn (see ScreenImagemap's own docstring).
_IMAGEMAP_GROUND_RE = re.compile(rf'^ground\s+({_QUOTED})(?:\s+idle\s+{_QUOTED})?(?:\s+hover\s+{_QUOTED})?\s*$')
# `idle`/`hover` can also appear as their own standalone lines rather than
# inline on the `ground` line (confirmed real content: GBDNATE's main_menu
# uses `ground "..."` then a separate `hover "..."` line) -- no true hover
# state exists on touch-only 3DS hardware either way, so both forms are
# just skipped.
_IMAGEMAP_IDLE_OR_HOVER_RE = re.compile(rf'^(?:idle|hover)\s+{_QUOTED}\s*$')
# `hotspot (x, y, w, h) action <expr> [alt "..."]` -- `clicked` is a real,
# equally-valid alias for `action` in Ren'Py's own screen language
# (confirmed real content: GBDNATE's imagemaps use `clicked`, Jisei's use
# `action`). `alt` (the accessibility label) is matched so it doesn't get
# swallowed into the action expression, then discarded; VNDS has no
# screen-reader equivalent.
_HOTSPOT_RE = re.compile(
    rf'^hotspot\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)\s+(?:action|clicked)\s+(.+?)(?:\s+alt\s+{_QUOTED})?$'
)


def _screen_text_literal(rest: str) -> str | None:
    rest = rest.strip()
    if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in ('"', "'"):
        return _dequote(rest)
    return None  # anything beyond a plain literal (interpolation, an expression) is out of scope


def _parse_screen_condition(cond_text: str) -> str | None:
    try:
        node = ast.parse(cond_text, mode="eval").body
    except SyntaxError:
        return None
    return _render_expr(node)


def _parse_screen_action(action_text: str) -> str | None:
    """Maps the common Ren'Py screen-language action calls to a VNDS
    `screen_button` action string (screen.moon's own action vocabulary).
    Composite `[Action1, Action2]` lists and anything not in this list
    (arbitrary function calls, `ShowTransient`, `NullAction`, ...) return
    None, making the whole screen Unsupported rather than a partial
    conversion that silently drops part of a button's behavior."""
    try:
        node = ast.parse(action_text, mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return None
    name = node.func.id
    args = node.args

    def _string_arg(index: int) -> str | None:
        if index >= len(args) or not isinstance(args[index], ast.Constant):
            return None
        value = args[index].value
        return value if isinstance(value, str) else None

    if name == "Jump" and len(args) == 1:
        target = _string_arg(0)
        return f"jump {target}" if target else None
    if name == "Call" and len(args) == 1:
        target = _string_arg(0)
        return f"call {target}" if target else None
    if name == "Return":
        return "hide_screen"  # no caller-return-value threading in this scope
    if name == "Quit":
        return "quit"
    if name in ("Show", "ShowMenu") and len(args) >= 1:
        target = _string_arg(0)
        return f"show_screen {target}" if target else None
    if name == "Hide":
        return "hide_screen"
    if name == "SetVariable" and len(args) == 2:
        var = _string_arg(0)
        value_str = _render_expr(args[1])
        return f"setvar {var} = {value_str}" if var and value_str is not None else None
    if name == "Start":
        # extended: imagemap/hotspot support -- main_menu's "New Game"
        # hotspot. Bare Start() dismisses the (only-ever-shown-once)
        # main menu, which already resumes exactly at the story's first
        # instruction (screen.moon's show_screen has no other caller for
        # main_menu) -- same effect as Return()/Hide() above. Start("label")
        # (a menu offering a specific chapter/epilogue restart point, e.g.
        # Jisei's "Epilogue" hotspot) reuses Jump's handling verbatim.
        if len(args) == 0:
            return "hide_screen"
        target = _string_arg(0)
        return f"jump {target}" if target else None
    return None


def _parse_hotspot_action(action_text: str) -> tuple[str | None, bool]:
    """Like `_parse_screen_action`, but for one `hotspot ... action <expr>`
    line inside an `imagemap:` block. Returns `(action, resolved)`:
    `resolved=False` means the caller should drop just this one hotspot
    (and flag it) rather than failing the whole imagemap, the opposite of
    `_parse_screen_action`'s existing "None bails the whole screen"
    contract used by textbutton/if parsing. `NullAction()` is a real,
    intentional no-op (a decorative/locked hotspot, common in real
    content) and resolves successfully to `(None, True)` — never a
    failure."""
    try:
        node = ast.parse(action_text, mode="eval").body
    except SyntaxError:
        return None, False
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "NullAction":
        return None, True
    action = _parse_screen_action(action_text)
    return action, action is not None


def _parse_screen_button(text: str) -> ScreenButton | None:
    match = _SCREEN_TEXTBUTTON_RE.match(text)
    if match is None:
        return None
    label, action_text = match.groups()
    action = _parse_screen_action(action_text)
    if action is None:
        return None
    return ScreenButton(label=_dequote(label), action=action)


def _parse_screen_imagemap(
    cursor: Cursor, parent_indent: int, filename: str, problems: list, screen_resolution: tuple[int, int]
) -> ScreenImagemap | None:
    """Parses the block indented under an `imagemap:` header: a required
    `ground` line (bails the whole imagemap if missing/unparseable — with
    no image there's nothing to render, matching `_parse_screen_children`'s
    own conservative-bail precedent for unrecognized constructs) followed
    by zero or more `hotspot` lines. Unlike every other construct here,
    each hotspot is resolved *independently*: one hotspot with an
    unsupported action is dropped and flagged, but every other hotspot —
    including the ones that matter most (New Game/Load/Quit) — still
    converts and works, rather than losing an otherwise-90%-working real
    main menu to the placeholder over one bad decorative button.

    Real Ren'Py hotspot coordinates are absolute pixels in the ground
    image's own native resolution -- converted here to fractions of the
    game's declared `screen_resolution` (see ScreenHotspot's own
    docstring for the real-hardware regression this fixes), the same
    resolution-independent convention `_resolve_atl_value` already uses
    for xpos/ypos."""
    nxt = cursor.peek()
    if nxt is None or nxt.indent <= parent_indent:
        return None
    child_indent = nxt.indent
    ground_match = _IMAGEMAP_GROUND_RE.match(nxt.text)
    if ground_match is None:
        return None
    cursor.advance()
    ground = _dequote(ground_match.group(1))
    hotspots: list[ScreenHotspot] = []
    while True:
        line = cursor.peek()
        if line is None or line.indent < child_indent:
            break
        if line.indent > child_indent:
            return None  # unexpected extra indentation -- bail conservatively
        if _IMAGEMAP_IDLE_OR_HOVER_RE.match(line.text):
            cursor.advance()  # standalone idle/hover line (see ground's own inline form) -- skip
            continue
        match = _HOTSPOT_RE.match(line.text)
        if match is None:
            return None  # unrecognized construct inside imagemap -- bail conservatively
        cursor.advance()
        x, y, w, h, action_text = match.groups()
        action, resolved = _parse_hotspot_action(action_text)
        if not resolved:
            problems.append(
                Unsupported(
                    text=line.text,
                    reason="imagemap hotspot uses an unsupported action, this hotspot dropped",
                    loc=SourceLocation(filename, line.lineno),
                )
            )
            continue
        screen_width, screen_height = screen_resolution
        hotspots.append(
            ScreenHotspot(
                x=round(int(x) / screen_width, 4), y=round(int(y) / screen_height, 4),
                w=round(int(w) / screen_width, 4), h=round(int(h) / screen_height, 4),
                action=action,
            )
        )
    return ScreenImagemap(ground=ground, hotspots=hotspots)


def _parse_screen_if(
    text: str, cursor: Cursor, indent: int, filename: str, problems: list, screen_resolution: tuple[int, int]
) -> ScreenIf | None:
    cursor.advance()  # the "if ...:" header line itself
    cond = _parse_screen_condition(text[len("if "):-1])
    if cond is None:
        return None
    body = _parse_screen_children(cursor, indent, filename, problems, screen_resolution)
    if body is None:
        return None
    branches = [ScreenIfBranch(cond=cond, children=body)]
    while True:
        nxt = cursor.peek()
        if nxt is None or nxt.indent != indent:
            break
        if nxt.text.startswith("elif ") and nxt.text.endswith(":"):
            cursor.advance()
            cond = _parse_screen_condition(nxt.text[len("elif "):-1])
            if cond is None:
                return None
            body = _parse_screen_children(cursor, indent, filename, problems, screen_resolution)
            if body is None:
                return None
            branches.append(ScreenIfBranch(cond=cond, children=body))
        elif nxt.text == "else:":
            cursor.advance()
            body = _parse_screen_children(cursor, indent, filename, problems, screen_resolution)
            if body is None:
                return None
            branches.append(ScreenIfBranch(cond=None, children=body))
            break
        else:
            break
    return ScreenIf(branches=branches)


def _parse_screen_children(
    cursor: Cursor, parent_indent: int, filename: str, problems: list, screen_resolution: tuple[int, int]
) -> list | None:
    """Parses the block indented under a screen/vbox/hbox/if header into
    ScreenNode children. Returns None (propagating failure up to
    `_parse_screen_def`, which discards the whole screen) the moment
    anything outside the supported subset is seen — reject conservatively
    rather than guess or partially convert. (imagemap is the one
    exception to "conservative reject" — see `_parse_screen_imagemap`.)"""
    nxt = cursor.peek()
    if nxt is None or nxt.indent <= parent_indent:
        return []
    child_indent = nxt.indent
    children = []
    while True:
        line = cursor.peek()
        if line is None or line.indent < child_indent:
            break
        if line.indent > child_indent:
            return None  # unexpected extra indentation -- bail conservatively
        text = line.text
        if text in ("vbox:", "hbox:", "window:"):
            # "window:" (a screen-language container, e.g. main_menu's
            # `window: style "mm_root"`) has no VNDS equivalent for its own
            # styling, but is otherwise just another transparent container
            # -- treated the same as vbox/hbox (both already collapse to
            # "items in order" at render time, so there's no fidelity loss
            # from erasing the distinction).
            cursor.advance()
            sub = _parse_screen_children(cursor, line.indent, filename, problems, screen_resolution)
            if sub is None:
                return None
            children.append(ScreenBox(children=sub))
        elif text.startswith("tag ") or text.startswith("style "):
            # "tag <name>" (a screen-replacement grouping hint) and a bare
            # "style <name>" property line (e.g. inside `window:`) are pure
            # metadata with no visual content of their own -- real content
            # confirmed via Jisei's actual main_menu (`tag menu` +
            # `window: style "mm_root"` precede its real imagemap content).
            # Safe to skip entirely rather than bail the whole screen.
            cursor.advance()
        elif text.startswith("text "):
            cursor.advance()
            literal = _screen_text_literal(text[len("text "):])
            if literal is None:
                return None
            children.append(ScreenText(text=literal))
        elif text.startswith("textbutton "):
            cursor.advance()
            button = _parse_screen_button(text)
            if button is None:
                return None
            children.append(button)
        elif text == "imagemap:":
            cursor.advance()
            imagemap = _parse_screen_imagemap(cursor, line.indent, filename, problems, screen_resolution)
            if imagemap is None:
                return None
            children.append(imagemap)
        elif text.startswith("if ") and text.endswith(":"):
            if_node = _parse_screen_if(text, cursor, line.indent, filename, problems, screen_resolution)
            if if_node is None:
                return None
            children.append(if_node)
        else:
            return None  # unrecognized construct (for, frame, imagebutton, `$`, ...) -- bail conservatively
    return children


def _parse_screen_def(
    name: str, cursor: Cursor, indent: int, loc: SourceLocation, filename: str, problems: list,
    screen_resolution: tuple[int, int],
) -> ScreenDef | None:
    bookmark = cursor.bookmark()
    children = _parse_screen_children(cursor, indent, filename, problems, screen_resolution)
    if children is None:
        cursor.restore(bookmark)
        _skip_child_block(cursor, indent)
        return None
    return ScreenDef(name=name, root=ScreenBox(children=children), loc=loc)


def _parse_menu(
    cursor: Cursor,
    header_indent: int,
    filename: str,
    loc: SourceLocation,
    problems: list[Unsupported],
    transforms: dict[str, list[str]],
    string_defines: dict[str, str],
    sprite_categories: SpriteLayerCategories,
    screen_resolution: tuple[int, int],
) -> Menu:
    nxt = cursor.peek()
    if nxt is None or nxt.indent <= header_indent:
        return Menu(choices=[], loc=loc)

    choice_indent = nxt.indent
    prompt: list[Node] = []
    choices: list[MenuChoice] = []
    while True:
        line = cursor.peek()
        if line is None or line.indent < choice_indent:
            break
        match = _MENU_CHOICE_RE.match(line.text)
        if match is None:
            # Not a choice line — Ren'Py allows a leading narration/dialogue
            # statement inside a menu: block, posing the question the
            # choices answer. Only valid before any real choice is seen;
            # after that, a non-matching line is a genuine syntax problem.
            if not choices:
                cursor.advance()
                _append_statement_result(
                    prompt, _parse_statement(line, cursor, filename, problems, transforms, string_defines, sprite_categories, screen_resolution)
                )
                continue
            cursor.advance()
            choice_loc = SourceLocation(filename, line.lineno)
            problems.append(
                Unsupported(text=line.text, reason="unrecognized menu choice syntax", loc=choice_loc)
            )
            _skip_child_block(cursor, line.indent)
            continue
        cursor.advance()
        choice_loc = SourceLocation(filename, line.lineno)
        choice_text = _dequote(match.group(1))
        body = _parse_child_block(cursor, line.indent, filename, problems, transforms, string_defines, sprite_categories, screen_resolution)
        choices.append(MenuChoice(text=choice_text, body=body, loc=choice_loc))
    return Menu(choices=choices, loc=loc, prompt=prompt)


def _render_expr(node: ast.expr) -> str | None:
    """Renders a Python expression AST into the text the engine's
    expr.moon evaluator understands (VN3DS-spec.md §6.1: int/bool/string
    literals, +-*/, ==!=<<=>>=, and/or/not, bare variable references), or
    None if the expression uses anything outside that safe subset (a call,
    most attribute/subscript access, a list/dict, chained comparisons,
    ...) -- `persistent.x`/`store.x` and a string-literal-keyed
    `dict_var["key"]` are the two exceptions, both flattened to a
    namespaced flat global rather than rejected.

    Deliberately builds its own rendering rather than using `ast.unparse`:
    unparse defaults to single-quoted strings, which expr.moon's tokenizer
    doesn't recognize (only double-quoted), and explicit parens around
    every subexpression sidesteps any precedence-matching risk between
    Python's grammar and the evaluator's."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return "True" if node.value else "False"
        if isinstance(node.value, (int, float)):
            return str(node.value)
        if isinstance(node.value, str):
            return None if '"' in node.value else f'"{node.value}"'
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in ("persistent", "store"):
        # `persistent.X`/`store.X` -- Ren'Py's real persistent data
        # survives across separate save files, which VNDS has no concept
        # of at all; treated as a flat global variable instead (a
        # faithful equivalent for the dominant real use -- one-time,
        # within-a-playthrough content-warning/skip-preference checks --
        # rather than true cross-save persistence, which isn't attempted).
        # Namespaced so `persistent.foo` and a same-named bare global
        # `foo` can't collide.
        return f"{node.value.id}_{node.attr}"
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
        and re.fullmatch(r"\w+", node.slice.value)
    ):
        # `dict_name["key"]` -- VNDS has no dict type (VN3DS-spec.md §6.1:
        # int/bool/string variables only); a string-literal-keyed
        # subscript is flattened into its own namespaced flat global,
        # mirroring the persistent./store. flattening above (confirmed
        # real content: ScarletHollow's relationship trackers, e.g.
        # `stella_relationship["trust"] += 1`). Double underscore (rather
        # than persistent/store's single underscore) to keep this
        # namespace distinct from an unrelated flat variable literally
        # named "dict_key". A non-identifier-safe key (spaces/punctuation)
        # or a non-literal/dynamic key has no equivalent and correctly
        # falls through to unsupported.
        return f"{node.value.id}__{node.slice.value}"
    if isinstance(node, ast.UnaryOp):
        inner = _render_expr(node.operand)
        if inner is None:
            return None
        if isinstance(node.op, ast.Not):
            return f"not {inner}"
        if isinstance(node.op, ast.USub):
            return f"-{inner}"
        return None
    if isinstance(node, ast.BinOp):
        symbol = _BINOP_SYMBOLS.get(type(node.op))
        left = _render_expr(node.left)
        right = _render_expr(node.right)
        if symbol is None or left is None or right is None:
            return None
        return f"({left} {symbol} {right})"
    if isinstance(node, ast.Compare):
        if len(node.ops) != 1 or len(node.comparators) != 1:
            return None  # chained comparisons (a < b < c) aren't supported
        symbol = _COMPARE_SYMBOLS.get(type(node.ops[0]))
        left = _render_expr(node.left)
        right = _render_expr(node.comparators[0])
        if symbol is None or left is None or right is None:
            return None
        return f"({left} {symbol} {right})"
    if isinstance(node, ast.BoolOp):
        symbol = "and" if isinstance(node.op, ast.And) else "or"
        rendered = [_render_expr(v) for v in node.values]
        if any(part is None for part in rendered):
            return None
        return f" {symbol} ".join(f"({part})" for part in rendered)
    return None


def _parse_condition(cond_text: str) -> str | None:
    """Parses a Ren'Py condition into an expr.moon-compatible expression
    string, for the engine's `ifvar <expr> jump <label>` command. Supports
    the full safe expression subset (§6.1), including compound `and`/`or`
    conditions and cross-variable comparisons — anything referencing a
    call/attribute/subscript, or a chained comparison, is out of scope."""
    try:
        tree = ast.parse(cond_text, mode="eval")
    except SyntaxError:
        return None
    return _render_expr(tree.body)


def _parse_if_chain(
    header_text: str,
    header_lineno: int,
    header_indent: int,
    cursor: Cursor,
    filename: str,
    problems: list[Unsupported],
    transforms: dict[str, list[str]],
    string_defines: dict[str, str],
    sprite_categories: SpriteLayerCategories,
    screen_resolution: tuple[int, int],
) -> Node:
    """Parses `if:`/`elif:`/`else:` siblings at the same indent into a
    single If node. If any non-else branch's condition falls outside the
    supported subset, the whole construct is rejected as Unsupported rather
    than partially flattened — a wrong branch taken silently is worse than
    an honest blocking flag (VN3DS-spec.md §6.1)."""
    loc = SourceLocation(filename, header_lineno)
    conditions: list[str | None] = []
    bodies: list[list[Node]] = []
    has_else = False

    conditions.append(_parse_condition(header_text[len("if "):-1].strip()))
    bodies.append(_parse_child_block(cursor, header_indent, filename, problems, transforms, string_defines, sprite_categories, screen_resolution))

    while True:
        nxt = cursor.peek()
        if nxt is None or nxt.indent != header_indent:
            break
        if nxt.text.startswith("elif ") and nxt.text.endswith(":"):
            cursor.advance()
            conditions.append(_parse_condition(nxt.text[len("elif "):-1].strip()))
            bodies.append(_parse_child_block(cursor, header_indent, filename, problems, transforms, string_defines, sprite_categories, screen_resolution))
        elif nxt.text == "else:":
            cursor.advance()
            conditions.append(None)
            bodies.append(_parse_child_block(cursor, header_indent, filename, problems, transforms, string_defines, sprite_categories, screen_resolution))
            has_else = True
            break
        else:
            break

    testable = conditions[:-1] if has_else else conditions
    if any(cond is None for cond in testable):
        node = Unsupported(
            text=header_text,
            reason="if/elif/else condition too complex for the current expression subset",
            loc=loc,
        )
        problems.append(node)
        return node

    branches = [IfBranch(condition=cond, body=body) for cond, body in zip(conditions, bodies)]
    return If(branches=branches, loc=loc)


def _parse_while(
    header_text: str,
    header_lineno: int,
    header_indent: int,
    cursor: Cursor,
    filename: str,
    problems: list[Unsupported],
    transforms: dict[str, list[str]],
    string_defines: dict[str, str],
    sprite_categories: SpriteLayerCategories,
    screen_resolution: tuple[int, int],
) -> Node:
    """Parses `while <cond>: <body>` — most commonly Ren'Py's
    "repeat a menu until the player picks an exit option" conversation-topic
    loop (`while inconvo: menu: ...`). Same conservative rejection as
    if/elif/else: an unparseable condition rejects the whole construct."""
    loc = SourceLocation(filename, header_lineno)
    condition = _parse_condition(header_text[len("while "):-1].strip())
    body = _parse_child_block(cursor, header_indent, filename, problems, transforms, string_defines, sprite_categories, screen_resolution)
    if condition is None:
        node = Unsupported(
            text=header_text,
            reason="while condition too complex for the current expression subset",
            loc=loc,
        )
        problems.append(node)
        return node
    return While(condition=condition, body=body, loc=loc)


def _is_namespace_attr(node: ast.expr, namespace: str) -> bool:
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == namespace


def _renpy_music_method(func: ast.expr) -> str | None:
    """Detects `renpy.music.METHOD(...)` -- a *nested* attribute
    (renpy -> music -> method), distinct from the single-level `renpy.X(...)`
    shape `_parse_special_dollar_statement`'s own `renpy_attr` handles.
    Real content uses `play`/`stop`/`set_volume` this way to do via Python
    what the declarative `play`/`stop` statements do (dominant real
    example: `$ renpy.music.play(music_from_within, fadein=1.0,
    channel='music2')`)."""
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Attribute)
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "renpy"
        and func.value.attr == "music"
    ):
        return func.attr
    return None


def _call_kwarg(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _resolve_music_file_arg(node: ast.expr, string_defines: dict[str, str]) -> str | None:
    """Resolves `renpy.music.play`'s first argument -- a bare identifier
    (the dominant real form, e.g. `music_from_within`, referring to a
    `define`d/init-python-assigned literal -- same `string_defines`
    resolution as an ordinary `play`/`queue` statement's file) or a
    literal string directly."""
    if isinstance(node, ast.Name):
        return string_defines.get(node.id, node.id)
    return _string_literal(node)


def _resolve_channel_kwarg(call: ast.Call) -> str | None:
    """`channel=` on a `renpy.music.*` call -- Ren'Py's own default when
    omitted is "music", matching the declarative `play`/`stop` statements'
    own implicit channel. Returns None (caller bails to the generic
    unsupported-statement fallback) for anything that isn't a literal
    string, e.g. a dynamically-computed channel name."""
    channel_arg = _call_kwarg(call, "channel")
    if channel_arg is None:
        return "music"
    return _string_literal(channel_arg)


def _constant_number(node: ast.expr | None) -> float | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    return None


def _parse_renpy_music_play(call: ast.Call, loc: SourceLocation, string_defines: dict[str, str]) -> Play | None:
    if not call.args:
        return None
    file_ = _resolve_music_file_arg(call.args[0], string_defines)
    channel = _resolve_channel_kwarg(call)
    if file_ is None or channel is None:
        return None
    return Play(channel=channel, file=file_, is_queue=False, loc=loc)


def _parse_renpy_music_stop(call: ast.Call, loc: SourceLocation) -> Stop | None:
    channel = _resolve_channel_kwarg(call)
    if channel is None:
        return None
    return Stop(channel=channel, loc=loc)


def _parse_renpy_music_set_volume(call: ast.Call, loc: SourceLocation) -> SetVolume | None:
    if not call.args:
        return None
    level = _constant_number(call.args[0])
    channel = _resolve_channel_kwarg(call)
    delay = _constant_number(_call_kwarg(call, "delay")) or 0.0
    if level is None or channel is None:
        return None
    return SetVolume(channel=channel, level=level, delay=delay, loc=loc)


def _parse_special_dollar_statement(
    stmt_text: str, loc: SourceLocation, problems: list[Unsupported], string_defines: dict[str, str]
) -> Node | None:
    """Recognizes a few specific `$ <stmt>` shapes that either have a direct
    VNDS equivalent (`renpy.pause(...)` == the standalone `pause` statement)
    or a well-known disposition per VN3DS-spec.md §6 that differs from the
    generic "unsupported statement" default (`persistent.*`/`achievement.*`
    are explicitly `manual`, not `blocking` — there's a human-reimplementable
    story here, unlike a truly unknown construct)."""
    try:
        tree = ast.parse(stmt_text, mode="exec")
    except SyntaxError:
        return None
    if len(tree.body) != 1:
        return None
    stmt = tree.body[0]

    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Name):
        # a bare variable reference statement (e.g. a leftover debug line)
        # has no side effect in Ren'Py either -- a genuine no-op.
        node = Unsupported(
            text=f"$ {stmt_text}",
            reason="bare variable reference has no effect, treated as a no-op",
            loc=loc,
        )
        problems.append(node)
        return node

    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        call = stmt.value
        renpy_attr = (
            call.func.attr
            if isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "renpy"
            else None
        )
        music_method = _renpy_music_method(call.func)
        if music_method == "play":
            node = _parse_renpy_music_play(call, loc, string_defines)
            if node is not None:
                return node
        elif music_method == "stop":
            node = _parse_renpy_music_stop(call, loc)
            if node is not None:
                return node
        elif music_method == "set_volume":
            node = _parse_renpy_music_set_volume(call, loc)
            if node is not None:
                return node
        if renpy_attr == "pause":
            if not call.args:
                return Pause(seconds=None, loc=loc)
            arg = call.args[0]
            # a pause duration is a plain numeric literal consumed directly
            # at convert time (-> `delay <frames>`), not a runtime
            # expression, so int/float both work here even though float
            # isn't in the safe expr subset _render_expr enforces elsewhere.
            if isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)) and not isinstance(arg.value, bool):
                return Pause(seconds=float(arg.value), loc=loc)
        if renpy_attr == "block_rollback" and not call.args:
            # a genuine no-op today: rollback/history isn't implemented yet
            # (Phase 3.7), so there's nothing for this to disable.
            node = Unsupported(
                text=f"$ {stmt_text}",
                reason="renpy.block_rollback() is a no-op (rollback isn't implemented yet)",
                loc=loc,
            )
            problems.append(node)
            return node
        if renpy_attr in ("movie_cutscene", "show_video"):
            node = Unsupported(
                text=f"$ {stmt_text}",
                reason="movie/video playback has no VNDS equivalent (needs native reimplementation)",
                loc=loc,
            )
            problems.append(node)
            return node
        if _is_namespace_attr(call.func, "achievement"):
            node = Unsupported(
                text=f"$ {stmt_text}",
                reason="persistent/achievement API has no VNDS equivalent (needs native reimplementation)",
                loc=loc,
            )
            problems.append(node)
            return node
        # <list_var>.insert(...)/.append(...)/etc -- a list-backed feature
        # (e.g. a clue/notes journal) with no VNDS list-variable equivalent
        # (vars are int/bool/string only, per §6.1), but a real,
        # human-reimplementable feature rather than truly unknown code.
        if (
            isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.attr in _LIST_MUTATION_METHODS
        ):
            node = Unsupported(
                text=f"$ {stmt_text}",
                reason="list mutation has no VNDS list-variable equivalent (needs native reimplementation)",
                loc=loc,
            )
            problems.append(node)
            return node

    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
        target, rhs = stmt.targets[0], stmt.value
        # $ var = renpy.random.randint(low, high) -> the original VNDS
        # `random` command (already implemented in script.moon, never
        # wired into the converter until now). Only literal int bounds
        # are resolvable, matching the engine's own num()-based parsing.
        if (
            isinstance(rhs, ast.Call)
            and isinstance(rhs.func, ast.Attribute)
            and rhs.func.attr == "randint"
            and isinstance(rhs.func.value, ast.Attribute)
            and rhs.func.value.attr == "random"
            and isinstance(rhs.func.value.value, ast.Name)
            and rhs.func.value.value.id == "renpy"
            and len(rhs.args) == 2
        ):
            low, high = rhs.args
            if (
                isinstance(low, ast.Constant)
                and isinstance(low.value, int)
                and not isinstance(low.value, bool)
                and isinstance(high, ast.Constant)
                and isinstance(high.value, int)
                and not isinstance(high.value, bool)
            ):
                return Random(var=target.id, low=str(low.value), high=str(high.value), loc=loc)

    if isinstance(stmt, ast.Assign) and isinstance(stmt.value, (ast.List, ast.Dict, ast.Tuple)):
        node = Unsupported(
            text=f"$ {stmt_text}",
            reason="list/dict-valued assignment has no VNDS equivalent (data for a feature needing native reimplementation)",
            loc=loc,
        )
        problems.append(node)
        return node

    return None


def _parse_set_statement(stmt_text: str, loc: SourceLocation) -> Set | None:
    """Parses the RHS of a Ren'Py `$ <stmt>` line: `var = <expr>` or
    `var +=/-= <expr>`, where `<expr>` is anything in the safe subset
    (§6.1) — including cross-variable arithmetic and boolean logic now
    that the engine has a real evaluator (Phase 2.4), not just a literal
    or a self-referential accumulation as in the original 2.1 pass.
    Anything referencing a call/subscript/list is left for the caller to
    flag. The assignment *target* is rendered the same way `_render_expr`
    renders any other reference -- a bare name, or `persistent.X`/
    `store.X` (resolved to a flat global the same as a read -- see
    `_render_expr`'s own docstring for why treating persistent data as an
    ordinary global is the right within-playthrough equivalent) -- so
    `$ persistent.flag = True` now sets a real, readable global instead of
    being unconditionally flagged as having no equivalent at all."""
    try:
        tree = ast.parse(stmt_text, mode="exec")
    except SyntaxError:
        return None
    if len(tree.body) != 1:
        return None
    stmt = tree.body[0]

    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
        var = _render_expr(stmt.targets[0])
        rendered = _render_expr(stmt.value) if var is not None else None
        if var is None or rendered is None:
            return None
        return Set(var=var, expr=rendered, loc=loc)

    if isinstance(stmt, ast.AugAssign) and isinstance(stmt.op, (ast.Add, ast.Sub)):
        var = _render_expr(stmt.target)
        rendered = _render_expr(stmt.value) if var is not None else None
        if var is None or rendered is None:
            return None
        symbol = "+" if isinstance(stmt.op, ast.Add) else "-"
        return Set(var=var, expr=f"({var} {symbol} {rendered})", loc=loc)

    return None


def _parse_default_define(text: str, loc: SourceLocation, problems: list[Unsupported]) -> Set | None:
    """Parses top-level `default var = <expr>` / `define var = <expr>`
    (non-Character, non-image) into a Set applied once at script start.
    `var` may carry one `persistent.`/`store.` prefix (real content:
    `default persistent.skip_sex = "prompt"`), resolved the same flat-
    global way `_render_expr`'s own persistent.X/store.X handling does;
    any other dotted name has no equivalent (an attribute on some other
    object entirely, not a namespace this converter understands)."""
    match = _DEFAULT_DEFINE_RE.match(text)
    if not match:
        problems.append(Unsupported(text=text, reason="unsupported top-level statement", loc=loc))
        return None
    varname, rhs = match.groups()
    if "." in varname:
        namespace, _, attr = varname.partition(".")
        if namespace not in ("persistent", "store"):
            problems.append(Unsupported(text=text, reason="unsupported top-level statement", loc=loc))
            return None
        varname = f"{namespace}_{attr}"
    try:
        tree = ast.parse(rhs, mode="eval")
    except SyntaxError:
        problems.append(Unsupported(text=text, reason="unsupported top-level statement", loc=loc))
        return None
    if isinstance(tree.body, (ast.List, ast.Dict, ast.Tuple)):
        # data for a feature that already needs native reimplementation
        # (vars are int/bool/string only, per §6.1) -- not a bug, just not
        # auto-convertible; treat like the feature itself (manual).
        problems.append(
            Unsupported(
                text=text,
                reason="list/dict-valued assignment has no VNDS equivalent (data for a feature needing native reimplementation)",
                loc=loc,
            )
        )
        return None
    if (
        isinstance(tree.body, ast.Call)
        and isinstance(tree.body.func, ast.Name)
        and tree.body.func.id in _TRANSITION_CONSTRUCTOR_NAMES
    ):
        # a custom named transition alias (`define wipedown = CropMove(...)`)
        # -- inert bookkeeping: `with wipedown` already downgrades to a
        # plain dissolve regardless of whether this definition itself
        # converts (2.2's _resolve_transition only checks the *name*
        # against the known dissolve/fade set, never this definition).
        problems.append(
            Unsupported(
                text=text,
                reason="custom transition definition has no VNDS equivalent (any use already downgrades to a plain dissolve)",
                loc=loc,
            )
        )
        return None
    rendered = _render_expr(tree.body)
    if rendered is None:
        problems.append(Unsupported(text=text, reason="unsupported top-level statement", loc=loc))
        return None
    return Set(var=varname, expr=rendered, loc=loc)


def _string_literal(node: ast.expr) -> str | None:
    """Extract a literal string, unwrapping Ren'Py's `_("...")` translation
    wrapper (near-universal in real Ren'Py projects) if present."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_"
        and len(node.args) == 1
    ):
        return _string_literal(node.args[0])
    return None


def _parse_composite_layers(rhs: str) -> list[str] | None:
    """Detect Ren'Py's common `im.Composite(None, (0,0), "layer1.png", (0,0),
    "layer2.png", ...)` pattern — a stack of same-canvas-sized transparent
    PNG layers alpha-composited in order (used pervasively by real Ren'Py
    VNs, Jisei included, for swappable face parts: base/eyebrows/mouth/eyes,
    so a character can mix-and-match expressions without one full sprite
    per combination). Every offset in Jisei's own script is `(0,0)`, so this
    only handles that exact shape; anything else (a non-`(0,0)` offset, a
    non-`None` master/size argument, or a call to anything other than
    `im.Composite`/`Composite`) returns None and falls back to the existing
    "dynamic displayable" Unsupported flag in `_parse_image_def`."""
    try:
        tree = ast.parse(rhs, mode="eval")
    except SyntaxError:
        return None
    call = tree.body
    if not isinstance(call, ast.Call):
        return None
    func = call.func
    is_composite = (isinstance(func, ast.Attribute) and func.attr == "Composite") or (
        isinstance(func, ast.Name) and func.id == "Composite"
    )
    if not is_composite or len(call.args) < 3 or len(call.args) % 2 != 1:
        return None
    master = call.args[0]
    if not (isinstance(master, ast.Constant) and master.value is None):
        return None
    layers: list[str] = []
    for offset_node, path_node in zip(call.args[1::2], call.args[2::2]):
        if not (isinstance(offset_node, ast.Tuple) and len(offset_node.elts) == 2):
            return None
        x, y = offset_node.elts
        if not (
            isinstance(x, ast.Constant)
            and x.value == 0
            and isinstance(y, ast.Constant)
            and y.value == 0
        ):
            return None
        path = _string_literal(path_node)
        if path is None:
            return None
        layers.append(path)
    return layers


def _parse_image_def(
    text: str, loc: SourceLocation, problems: list[Unsupported]
) -> tuple[str | None, str]:
    """Parse `image <tag> = "<path>"`. Only a literal string path is
    resolvable statically; ATL blocks (handled elsewhere, since those end in
    `:` and never reach this function) and displayable-returning calls
    (`anim.Blink(...)`, `renpy.ParameterizedText(...)`, ...) can't be
    resolved to a file at conversion time."""
    match = _IMAGE_DEF_RE.match(text)
    if not match:
        problems.append(Unsupported(text=text, reason="malformed image statement", loc=loc))
        return None, ""
    tag, rhs = match.groups()
    try:
        tree = ast.parse(rhs, mode="eval")
    except SyntaxError:
        problems.append(Unsupported(text=text, reason="could not parse image declaration", loc=loc))
        return None, ""

    path = _string_literal(tree.body)
    if path is None:
        problems.append(
            Unsupported(
                text=text,
                reason="image declaration is not a plain file path (dynamic displayable)",
                loc=loc,
            )
        )
        return None, ""
    return tag, path


def _record_string_define(text: str, string_defines: dict[str, str]) -> None:
    """Opportunistically record `define name = "literal"` bindings (any
    top-level define, not just Character()s) so DynamicCharacter's
    variable-named display argument can be resolved below. Doesn't affect
    whether the line itself gets flagged — that's decided by the caller."""
    match = _DEFINE_RE.match(text)
    if not match:
        _record_bare_string_assign(text, string_defines)
        return
    name, rhs = match.groups()
    try:
        literal = _string_literal(ast.parse(rhs, mode="eval").body)
    except SyntaxError:
        return
    if literal is not None:
        string_defines[name] = literal


_BARE_ASSIGN_RE = re.compile(r"^(\w+)\s*=\s*(.+)$")


def _record_bare_string_assign(text: str, string_defines: dict[str, str]) -> None:
    """Same idea as `_record_string_define`, but for a plain Python
    assignment with no `define` keyword at all -- the real-world form used
    inside an `init python:` block (confirmed against Mice Tea's
    `screens/music.rpy`, which declares every `sfx_X = "audio/..."` alias
    this way). `ast.parse`'s own SyntaxError on anything that merely
    *looks* like `NAME = ...` (a comparison `x == 5`, an attribute/call
    target, ...) safely rejects those without needing to hand-detect them
    first."""
    match = _BARE_ASSIGN_RE.match(text)
    if not match:
        return
    name, rhs = match.groups()
    try:
        literal = _string_literal(ast.parse(rhs, mode="eval").body)
    except SyntaxError:
        return
    if literal is not None:
        string_defines[name] = literal


def _parse_character_def(
    text: str, loc: SourceLocation, problems: list[Unsupported], string_defines: dict[str, str]
) -> CharacterDef | None:
    match = _DEFINE_RE.match(text)
    if not match:
        problems.append(Unsupported(text=text, reason="malformed define statement", loc=loc))
        return None
    varname, rhs = match.groups()
    try:
        tree = ast.parse(rhs, mode="eval")
    except SyntaxError:
        problems.append(Unsupported(text=text, reason="could not parse Character() arguments", loc=loc))
        return None

    call = tree.body
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)):
        problems.append(Unsupported(text=text, reason="define is not a Character() call", loc=loc))
        return None
    if call.func.id not in ("Character", "DynamicCharacter"):
        problems.append(Unsupported(text=text, reason="define is not a Character() call", loc=loc))
        return None
    is_dynamic = call.func.id == "DynamicCharacter"

    display_name: str | None = None
    explicit_none = False
    if call.args:
        if is_dynamic:
            # DynamicCharacter's first arg names a *variable* holding the
            # display name (which can change at runtime, e.g. after a
            # player renames a character) — approximate with whatever
            # literal value that variable currently defines.
            var_name = _string_literal(call.args[0])
            if var_name is not None:
                display_name = string_defines.get(var_name)
        else:
            first_arg = call.args[0]
            if isinstance(first_arg, ast.Constant) and first_arg.value is None:
                # Character(None, ...) is a deliberate, valid Ren'Py idiom
                # for a styled-but-nameless narrator (e.g. ctc/color set,
                # no name shown) -- distinct from a genuinely unresolvable
                # display name.
                explicit_none = True
            else:
                display_name = _string_literal(first_arg)

    color: str | None = None
    namebox_background: str | None = None
    for kw in call.keywords:
        if kw.arg == "color" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            color = kw.value.value
        if kw.arg == "namebox_background" and isinstance(kw.value, ast.Constant) and isinstance(
            kw.value.value, str
        ):
            # A per-character nameplate skin override (VN3DS-spec.md §6,
            # the custom UI-asset-import system) -- confirmed real content:
            # Mice Tea's characters.rpy uses this 84 times.
            namebox_background = kw.value.value

    if display_name is not None:
        # A Character()'s own display name can carry text tags (confirmed
        # real content: `Character("{i}(Margaret){/i}{alt} Thinking{/alt}",
        # ...)`) -- needs the same translation dialogue text gets, not the
        # raw, previously-never-touched literal markup.
        display_name = _translate_text_tags(display_name, loc, problems)

    if display_name is None and not explicit_none:
        reason = (
            "DynamicCharacter's name variable could not be resolved to a literal string"
            if is_dynamic
            else "Character() missing a string display name"
        )
        problems.append(Unsupported(text=text, reason=reason, loc=loc))
        return None

    if is_dynamic:
        problems.append(
            Unsupported(
                text=text,
                reason="DynamicCharacter approximated with its current default display name",
                loc=loc,
            )
        )

    return CharacterDef(
        varname=varname, display_name=display_name, color=color, loc=loc,
        namebox_background=namebox_background,
    )
