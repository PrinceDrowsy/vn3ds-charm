"""Emits script.vnds (ADR-002: plain-text extended VNDS) from the parser IR.

The parser IR mirrors Ren'Py's nested block structure (a `menu:` node holds
each choice's body inline). VNDS has no nested blocks — it's a flat sequence
of labels, and a `choice` command just jumps to other labels. This module
does that flattening: each menu becomes `choice ...` + `jump ...` into
synthetic labels, and if a choice's body doesn't end in its own jump/call/
return, an implicit jump-to-continuation is appended so Ren'Py's "falls
through to whatever comes after the menu" semantics is preserved.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from converter.parser import (
    AnimSpec,
    Call,
    CharacterDef,
    CharacterImageDef,
    DayCard,
    Hide,
    If,
    IfBranch,
    InterpreterBailout,
    Jump,
    Label,
    Menu,
    Node,
    Pause,
    Placeholder,
    Play,
    PortraitDef,
    PortraitUpdate,
    Random,
    ResetAudio,
    Return,
    Say,
    Scene,
    ScreenBox,
    ScreenButton,
    ScreenDef,
    ScreenIf,
    ScreenImagemap,
    ScreenNode,
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
    expand_attrs,
    resolve_layer_file,
    resolve_layers,
    resolve_layers_with_persistent,
)

from .flagged import FlaggedItems

# Anchor coordinates for Ren'Py's left/center/right sprite positions, on
# the 400x240 top screen. `x` is the sprite's horizontal CENTER (matching
# both Ren'Py's own align semantics and images.moon's draw_foreground,
# which anchors sprites by center, not left edge) — so these are exact
# screen-fraction points (100/200/300 out of 400), not sprite-size-aware
# placeholders the way the old top-left-anchor values had to be.
_POSITION_XY: dict[str | None, tuple[int, int]] = {
    "left": (100, 40),
    "center": (200, 40),
    "right": (300, 40),
    None: (200, 40),
}
_DEFAULT_ATL_Y = 40  # matches _POSITION_XY's baseline vertical anchor


def _resolve_show_xy(position: str | None, xalign: float | None, yalign: float | None) -> tuple[int, int]:
    """An ATL block's precise xalign/yalign (0.0-1.0 screen fraction) takes
    priority over the coarser left/center/right snap when present — a real
    fidelity improvement, not an approximation, for the (dominant, in
    real-world content) case of a plain static position with no tween."""
    if xalign is None and yalign is None:
        return _POSITION_XY.get(position, _POSITION_XY[None])
    fallback_x, _fallback_y = _POSITION_XY.get(position, _POSITION_XY[None])
    x = round(xalign * 400) if xalign is not None else fallback_x
    y = round(yalign * 240) if yalign is not None else _DEFAULT_ATL_Y
    return x, y


def _static_prop_tokens(node: Show) -> str:
    """Trailing `key=value` tokens appended to a `setimg` line -- reusing
    the exact convention `keyframe` already uses (script.moon's parse_props
    splits any `k=v` token generically). Carries the raw ATL fractions/
    scale/rotation/alpha a static (non-animated) block resolved to, so the
    engine can resolve `yalign`/`yanchor` against the sprite's *actual*
    loaded height at setimg time (images.moon's `on "setimg"`) instead of
    relying on the positional `y` above, which stays a flat, sprite-height-
    *unaware* fallback exactly as before this feature existed (see
    `_resolve_show_xy`'s docstring -- fixing that fallback for the common
    yalign case is the whole point of threading these through). Only
    emitted when a static ATL block/transform actually set something, so a
    plain show with no ATL still emits the exact same 4-token line as
    always. `yanchor` defaults to `yalign`'s own value when the parser
    didn't resolve one separately (the common case: anchor == position)."""
    tokens: list[str] = []
    if node.yalign is not None:
        yanchor = node.yanchor if node.yanchor is not None else node.yalign
        tokens.append(f"yalign={_format_prop_value(node.yalign)}")
        tokens.append(f"yanchor={_format_prop_value(yanchor)}")
    if node.sx is not None:
        tokens.append(f"sx={_format_prop_value(node.sx)}")
    if node.sy is not None:
        tokens.append(f"sy={_format_prop_value(node.sy)}")
    if node.rotate is not None:
        tokens.append(f"r={_format_prop_value(round(node.rotate * 3.14159265 / 180, 4))}")
    if node.alpha is not None:
        tokens.append(f"alpha={_format_prop_value(node.alpha)}")
    return (" " + " ".join(tokens)) if tokens else ""


# Only these two names have a well-known default duration (matching
# VN3DS-spec.md's own worked example, `transition dissolve 0.5`); any other
# Ren'Py transition name (wipeleft, CropMove(...), custom ATL, ...) is
# downgraded to a plain dissolve rather than left unconverted, since a
# simplified transition is still playable (VN3DS-spec.md §7.1 `approximated`).
# Dissolve/fade both now wire into a *real* fade (see _emit_scene_transition/
# _emit_show_transition/_emit_hide_transition below) -- previously "dissolve"
# was itself a no-op too, since "transition" was never a recognized engine
# instruction at all (confirmed: absent from script.moon's instruction
# list). Named transitions with a direct 1:1 engine preset skip the
# dissolve downgrade entirely -- currently just "vpunch" (real content: 27
# uses in Mice Tea alone) -> anim.moon's existing "shake" preset.
_KNOWN_TRANSITIONS = {"dissolve", "fade"}
_TRANSITION_PRESET = {"vpunch": "shake"}
_DEFAULT_TRANSITION_DURATION = 0.5

# VNDS engine channel commands per Phase 1.7 (already implemented in
# src/engine/audio.moon) that `play`/`stop` map onto. "audio" is Ren'Py's
# own built-in one-shot channel -- functionally the same as "sound", so it
# aliases to the same commands. "ambiance" and "music2" are real,
# independent engine channels (audio.moon), not approximations -- both
# confirmed via real content (`renpy.music.register_channel`) to
# legitimately play simultaneously with "music" (music2 for a genuine
# layered-music crossfade, ambiance for background sound), unlike
# aliasing either onto music/sound which would make one cut the other off.
_PLAY_COMMAND = {
    "music": "music", "sound": "sound", "voice": "voiceover",
    "audio": "sound", "ambiance": "ambiance", "music2": "music2",
}
_STOP_COMMAND = {
    "music": "stopmusic", "sound": "stopsound", "voice": "stopvoice",
    "audio": "stopsound", "ambiance": "stopambiance", "music2": "stopmusic2",
}
_ONE_SHOT_CHANNELS = {"sound", "audio"}  # takes an extra "play count" token (see _PLAY_COMMAND's "sound" shape)
# `setvolume`'s channel argument is the engine's own channel *identity*
# (audio.moon's `channel_table`), not a play/stop *command* name -- "voice"
# stays "voice" here even though Play/Stop's own command name for it is
# "voiceover".
_VOLUME_CHANNEL = {"music": "music", "sound": "sound", "voice": "voice", "audio": "sound", "ambiance": "ambiance", "music2": "music2"}

# Any channel name outside the 5 curated ones above (VN3DS-spec.md §6) --
# real content confirmed using several (ScarletHollow's "secondary"/
# "tertiary"/"music4"/"music5"/"music6", Our Life's second voice channel
# "voice2"). The engine's own audio.moon has a matching generic play/stop
# path for these (its `channels` table); this only decides, once per
# channel *name*, which of the two curated shapes it behaves like --
# looping/"music"-mixer (like music2, for a crossfade-style secondary
# track) or one-shot/"sound"-mixer (like voice, for a single line) -- so
# the engine never has to guess a custom channel's behavior at runtime.
_CUSTOM_CHANNEL_SHAPE: dict[str, tuple[bool, str]] = {
    "secondary": (True, "music"),
    "tertiary": (True, "music"),
    "music4": (True, "music"),
    "music5": (True, "music"),
    "music6": (True, "music"),
    "voice2": (False, "sound"),
}
_CUSTOM_CHANNEL_NAME_RE = re.compile(r"^\w+$")


def _infer_custom_channel_shape(channel: str) -> tuple[bool, str]:
    """Fallback heuristic for any channel name not in _CUSTOM_CHANNEL_SHAPE
    above (a not-yet-seen name in some other game) -- named after what it
    most resembles, same reasoning as the curated table's own entries.
    Defaults to looping/"sound"-mixer (matching Ren'Py's own
    renpy.music.register_channel default) since a wrong "doesn't loop"
    guess would silently truncate background audio -- worse than a wrong
    "loops" guess, which just means a one-shot cue doesn't auto-stop."""
    if "voice" in channel:
        return False, "sound"
    if "music" in channel:
        return True, "music"
    if "ambien" in channel:
        return True, "sound"
    return True, "sound"


def _resolve_custom_channel_shape(channel: str) -> tuple[bool, str] | None:
    """None only when the name itself can't be safely emitted as a VNDS
    instruction token (contains whitespace/punctuation) -- reachable only
    via the Python-API `channel=` kwarg form (renpy.music.play/stop/
    set_volume), never the declarative play/stop syntax, which is already
    \\w+-restricted at parse time."""
    if not _CUSTOM_CHANNEL_NAME_RE.match(channel):
        return None
    return _CUSTOM_CHANNEL_SHAPE.get(channel) or _infer_custom_channel_shape(channel)


class _LabelCounter:
    def __init__(self) -> None:
        self._n = 0

    def fresh(self, base: str) -> str:
        self._n += 1
        return f"__{base}_{self._n}"


def _is_control_transfer(node: Node) -> bool:
    return isinstance(node, (Jump, Call, Return))


def _resolve_speaker(who: str | None, characters: dict[str, CharacterDef]) -> str | None:
    if who is None:
        return None
    if who in characters:
        return characters[who].display_name
    return who  # literal name form, e.g. `"Anonymous Name" "text"`


def _resolve_speaker_color(who: str | None, characters: dict[str, CharacterDef]) -> str | None:
    # Character(color=...)'s per-character nameplate tint (VN3DS-spec.md
    # §6) -- previously parsed and stored on CharacterDef but never read
    # anywhere, so every nameplate rendered in the engine's own hardcoded
    # default color regardless. A literal anonymous name (`who` not in
    # `characters`) has no color to look up.
    if who is not None and who in characters:
        return characters[who].color
    return None


def _image_filename(image_tag: str) -> str:
    # No declared `image <tag> = "path"` for this tag (e.g. an anonymous
    # tag that happens to match a real filename) — join words so the
    # emitted command stays parseable as a single whitespace-delimited
    # token, and hope the tag matches the asset's basename. The engine's
    # own script.moon `parse()` never appends an extension itself (unlike
    # sound/music/voiceover, where main.lua's asset lookup is exact-match)
    # -- confirmed against every hand-written engine fixture
    # (hello-vn/stress-test/vnds-test all write e.g. `bgload bg.t3x`) and
    # on real hardware: images silently never rendered because the emitted
    # `bgload`/`setimg` commands had no extension at all, so `path_exists`
    # never matched the `.t3x` file the asset pipeline actually produced,
    # while `sound`/`music`/`voiceover` (which already appended `.ogg` via
    # `_audio_filename`) worked correctly.
    return image_tag.replace(" ", "_") + ".t3x"


def _resolve_image_path(image_tag: str, images: dict[str, str]) -> str:
    # Resolve through the script's `image <tag> = "path"` declarations so
    # tags that don't match their file's basename (e.g. `image sakev =
    # "gui/logo.jpg"`) still emit the right token; VNDS commands take a
    # single filename with no directory (asset pipeline flattens into
    # background/foreground folders by basename), but *with* the
    # extension the asset pipeline's `.t3x` conversion actually produces.
    declared = images.get(image_tag)
    if declared is None:
        return _image_filename(image_tag)
    basename = declared.replace("\\", "/").rsplit("/", 1)[-1]
    if "." in basename:
        basename = basename.rsplit(".", 1)[0]
    return _image_filename(basename)


def _target_name(image_name: str) -> str:
    # "anim"/"anim_begin"/"anim_wait" target names are basenames with no
    # extension -- images.moon resolves a sprite's target by stripping the
    # folder and extension from its setimg path, matching this exactly.
    return image_name.rsplit(".", 1)[0] if "." in image_name else image_name


def _format_prop_value(value: float) -> str:
    # keyframe props are plain "key=value" tokens (script.moon's parse()
    # splits on whitespace) -- render whole numbers without a trailing
    # ".0" for readability, matching how x/y pixel values usually look.
    return str(int(value)) if value == int(value) else str(value)


def _emit_anim(anim: AnimSpec, target: str, lines: list[str]) -> None:
    if anim.preset is not None:
        lines.append(f"anim {target} {anim.preset} {_format_prop_value(anim.duration)}")
        return
    if not anim.keyframes:
        return
    header = f"anim_begin {target} {_format_prop_value(anim.duration)}"
    if anim.ease:
        header += f" {anim.ease}"
    lines.append(header)
    for t, props in anim.keyframes:
        prop_str = " ".join(f"{k}={_format_prop_value(v)}" for k, v in props.items())
        lines.append(f"keyframe {_format_prop_value(t)} {prop_str}")
    lines.append("anim_end")


def _audio_filename(path: str) -> str:
    # sound/music/voiceover take a bare filename *with* extension (unlike
    # images), and the asset pipeline always re-encodes to .ogg
    # (src/converter/assets/pipeline.py's convert_audio) regardless of the
    # source format (e.g. Ren'Py's own "The Question" ships .opus) — so emit
    # the basename with the .ogg extension the converted asset will actually have.
    basename = path.replace("\\", "/").rsplit("/", 1)[-1]
    if "." in basename:
        basename = basename.rsplit(".", 1)[0]
    return f"{basename}.ogg"


def _resolve_transition(name: str) -> tuple[str, bool]:
    """Returns (canonical_kind, was_downgraded). Only dissolve/fade have a
    known duration; anything else is approximated as a dissolve."""
    if name in _KNOWN_TRANSITIONS:
        return name, False
    return "dissolve", True


def _emit_transition(name: str, loc: SourceLocation, flagged: FlaggedItems, lines: list[str]) -> None:
    # Used only by the day/subchapter/the_end title-card emitters below,
    # whose own internal choreography is a separate, already-accepted
    # approximation (VN3DS-spec.md's title-card visual style gap) -- their
    # calls here aren't immediately preceded by a bgload/setimg line the
    # way an ordinary Scene/Show/Hide is, so there's no real fade target to
    # wire this into. Ordinary scene/show/hide transitions use
    # _emit_scene_transition/_emit_show_transition/_emit_hide_transition/
    # _emit_standalone_transition instead, which are real.
    kind, downgraded = _resolve_transition(name)
    if downgraded:
        flagged.add(
            text=f"with {name}",
            reason=f"transition '{name}' downgraded to a plain dissolve (only dissolve/fade have a known duration)",
            loc=loc,
        )
    lines.append(f"transition {kind} {_DEFAULT_TRANSITION_DURATION}")


def _flag_if_downgraded(name: str, loc: SourceLocation, flagged: FlaggedItems) -> None:
    _, downgraded = _resolve_transition(name)
    if downgraded:
        flagged.add(
            text=f"with {name}",
            reason=f"transition '{name}' downgraded to a plain dissolve (only dissolve/fade have a known duration)",
            loc=loc,
        )


def _emit_scene_transition(name: str, loc: SourceLocation, flagged: FlaggedItems, lines: list[str]) -> None:
    """Applies a transition to the `bgload` line just appended to `lines`
    (`lines[-1]`) by embedding a real alpha fade-in frame count -- `bgload`
    already supports this via its optional 3rd token (images.moon's
    `on "bgload"`, `Timer.tween(@frames/60, ...)`), just never populated by
    the emitter before this fix. Non-blocking (matches how a fade-in never
    blocked anything before either); a following `delay` still works
    exactly as it did previously for anything that needs the pause."""
    _flag_if_downgraded(name, loc, flagged)
    frames = round(_DEFAULT_TRANSITION_DURATION * 60)
    lines[-1] = f"{lines[-1]} {frames}"


def _emit_show_transition(
    name: str, loc: SourceLocation, flagged: FlaggedItems, lines: list[str], target: str
) -> None:
    """Applies a transition to a sprite that was just `setimg`'d. A named
    transition with a direct engine preset (_TRANSITION_PRESET, e.g.
    vpunch->shake) fires as-is; anything else fades in via anim.moon's
    existing `enter_fade` preset -- non-blocking, same reasoning as
    _emit_scene_transition (the sprite's already in images.moon's sprite
    list and draws every frame regardless of its in-flight alpha)."""
    if name in _TRANSITION_PRESET:
        lines.append(f"anim {target} {_TRANSITION_PRESET[name]} {_DEFAULT_TRANSITION_DURATION}")
        return
    _flag_if_downgraded(name, loc, flagged)
    lines.append(f"anim {target} enter_fade {_DEFAULT_TRANSITION_DURATION}")


def _emit_hide_transition(
    name: str, loc: SourceLocation, flagged: FlaggedItems, lines: list[str], target: str
) -> None:
    """Applies a transition to a sprite about to be hidden: fires the
    fade/preset, then blocks (`anim_wait`) until it completes -- unlike
    Scene/Show's fade-in, this one *must* block, since images.moon drops a
    sprite from its list the instant `clearimg` runs (stops drawing
    immediately regardless of its own in-flight alpha tween), so the fade
    would never be visible at all otherwise. The caller emits `clearimg`
    right after this returns."""
    if name in _TRANSITION_PRESET:
        lines.append(f"anim {target} {_TRANSITION_PRESET[name]} {_DEFAULT_TRANSITION_DURATION}")
        lines.append(f"anim_wait {target}")
        return
    _flag_if_downgraded(name, loc, flagged)
    lines.append(f"anim {target} exit_fade {_DEFAULT_TRANSITION_DURATION}")
    lines.append(f"anim_wait {target}")


def _emit_standalone_transition(name: str, loc: SourceLocation, flagged: FlaggedItems, lines: list[str]) -> None:
    """A bare `with <name>` not attached inline to the scene/show that
    produced it (Ren'Py's common two-line idiom, e.g. `scene bg` \\n `with
    dissolve`) applies retroactively to whatever was just emitted --
    inspect the last line to tell which fade mechanism applies. (A `hide`
    immediately followed by a standalone `with` is intercepted earlier, in
    _emit_body, before either node reaches here -- that pairing needs the
    fade to run *before* the sprite's removal, which this function can't
    arrange since by the time a Transition node reaches here the Hide
    already ran.)"""
    if not lines:
        return
    last = lines[-1]
    if last.startswith("bgload "):
        _emit_scene_transition(name, loc, flagged, lines)
    elif last.startswith("setimg "):
        target = _target_name(last.split()[1])
        _emit_show_transition(name, loc, flagged, lines, target)
    else:
        # No recognizable preceding scene/show to fade (e.g. right after a
        # dialogue line, or a menu) -- nothing to apply a real fade to;
        # keep the same downgrade-flag semantics as before.
        _flag_if_downgraded(name, loc, flagged)


def _escape_text(text: str) -> str:
    # script.vnds is line-based; a literal newline would be read as a
    # separate instruction. Collapse to keep the round-trip parseable.
    return text.replace("\n", " ")


def _escape_choice_option(text: str) -> str:
    # `choice` splits on "|"; a literal "|" in the option text would corrupt
    # the split. Rare in practice — replace rather than block conversion.
    return text.replace("\n", " ").replace("|", "/")


def _resolve_literal_image_path(path: str) -> str:
    """Resolves a literal source-relative image path (not a declared `image
    <tag> = ...` alias -- e.g. imagemap's `ground "gui/mainmenu01_idle.jpg"`)
    to the emitted VNDS filename, the same basename-strip-then-`.t3x`
    convention `_resolve_image_path`'s declared-path branch already uses."""
    basename = path.replace("\\", "/").rsplit("/", 1)[-1]
    if "." in basename:
        basename = basename.rsplit(".", 1)[0]
    return _image_filename(basename)


def _emit_screen_node(node: ScreenNode, lines: list[str]) -> None:
    if isinstance(node, ScreenBox):
        lines.append("vbox_begin")
        for child in node.children:
            _emit_screen_node(child, lines)
        lines.append("vbox_end")
    elif isinstance(node, ScreenText):
        lines.append(f"screen_text {_escape_text(node.text)}")
    elif isinstance(node, ScreenButton):
        lines.append(f"screen_button {node.label} | {node.action}")
    elif isinstance(node, ScreenImagemap):
        lines.append(f"imagemap_begin {_resolve_literal_image_path(node.ground)}")
        for hotspot in node.hotspots:
            action = hotspot.action or ""  # empty after "|" = NullAction (intentional no-op)
            # x/y/w/h are fractions (0.0-1.0) of the game's own declared
            # resolution, not absolute pixels (see ScreenHotspot's own
            # docstring) -- the engine multiplies by whatever the actually-
            # loaded ground image's real dimensions turn out to be.
            x, y, w, h = (_format_prop_value(v) for v in (hotspot.x, hotspot.y, hotspot.w, hotspot.h))
            lines.append(f"hotspot {x} {y} {w} {h} | {action}")
        lines.append("imagemap_end")
    elif isinstance(node, ScreenIf):
        for i, branch in enumerate(node.branches):
            if branch.cond is None:
                lines.append("screen_else")
            elif i == 0:
                lines.append(f"screen_if {branch.cond}")
            else:
                lines.append(f"screen_elif {branch.cond}")
            for child in branch.children:
                _emit_screen_node(child, lines)
        lines.append("screen_endif")


def _emit_screen_def(screen: ScreenDef, lines: list[str]) -> None:
    lines.append(f"screen_begin {screen.name}")
    for child in screen.root.children:
        _emit_screen_node(child, lines)
    lines.append("screen_end")


def emit_script_vnds(
    labels: list[tuple[str, list[Node]]],
    characters: dict[str, CharacterDef],
    images: dict[str, str] | None = None,
    top_level_sets: list[Set] | None = None,
    screens: list[ScreenDef] | None = None,
    character_images: dict[str, CharacterImageDef] | None = None,
    assets_dir: Path | None = None,
    character_image_layer_files: dict[str, Path] | None = None,
    portrait_defs: dict[str, PortraitDef] | None = None,
    portrait_layer_files: dict[str, Path] | None = None,
) -> tuple[str, FlaggedItems]:
    """labels: (name, body) pairs, e.g. from Script.labels via `(l.name, l.body)`.
    `character_images`, when given, is a game-wide tag -> CharacterImageDef
    registry (see character_image.py) -- a `show <tag> <attrs>` whose slot
    matches one of these emits real-time multi-layer sprite commands
    instead of the ordinary single-image `setimg`. `character_image_layer_files`,
    when given, is filled in (mutated) as a side effect with every distinct
    normalized-basename -> real source Path actually resolved, so the
    caller (cli.py) knows exactly which per-character layer files need
    converting -- these are never behind an ordinary `image NAME = "path"`
    declaration, so the generic asset-search pipeline would never find
    them on its own."""
    images = images or {}
    character_images = character_images or {}
    flagged = FlaggedItems()
    counter = _LabelCounter()
    worklist: list[tuple[str, list[Node]]] = list(labels)
    lines: list[str] = []

    # Top-level `default`/`define` literals and screen *definitions* both
    # run once, before any label, since VNDS executes top-to-bottom from
    # the first instruction in the file and `@label` markers are just
    # lookup targets within that same stream -- a screen must be
    # registered before any `show_screen` can reference it, and this is
    # the only place guaranteed to run unconditionally at game start.
    for node in top_level_sets or []:
        _emit_statement(node, characters, images, flagged, lines, has_portraits=bool(portrait_defs))
    for screen in screens or []:
        _emit_screen_def(screen, lines)

    i = 0
    while i < len(worklist):
        name, body = worklist[i]
        i += 1
        lines.append(f"@{name}")
        _emit_body(
            body, name, counter, worklist, lines, characters, images, flagged,
            character_images, assets_dir, character_image_layer_files,
            portrait_defs, portrait_layer_files,
        )
        lines.append("")

    text = "\n".join(lines).rstrip("\n") + "\n"
    return text, flagged


def _emit_body(
    body: list[Node],
    label_name: str,
    counter: _LabelCounter,
    worklist: list[tuple[str, list[Node]]],
    lines: list[str],
    characters: dict[str, CharacterDef],
    images: dict[str, str],
    flagged: FlaggedItems,
    character_images: dict[str, CharacterImageDef] | None = None,
    assets_dir: Path | None = None,
    character_image_layer_files: dict[str, Path] | None = None,
    portrait_defs: dict[str, PortraitDef] | None = None,
    portrait_layer_files: dict[str, Path] | None = None,
) -> None:
    character_images = character_images or {}
    portrait_defs = portrait_defs or {}
    skip_next = False
    for idx, node in enumerate(body):
        if skip_next:
            skip_next = False
            continue
        if (
            isinstance(node, Show)
            and node.image.split()[0] in character_images
        ):
            _emit_character_image_show(
                node, character_images[node.image.split()[0]], assets_dir,
                character_image_layer_files, counter, flagged, lines, images,
            )
            continue
        if isinstance(node, PortraitUpdate):
            _emit_portrait_update(node, portrait_defs, assets_dir, portrait_layer_files, flagged, lines)
            continue
        if (
            isinstance(node, Hide)
            and not node.transition
            and idx + 1 < len(body)
            and isinstance(body[idx + 1], Transition)
        ):
            # A standalone `with <name>` immediately following a bare
            # `hide` (Ren'Py's common two-line idiom -- confirmed real
            # content: 33 occurrences in Mice Tea) needs its fade to play
            # *before* the sprite is actually removed, since images.moon
            # drops the sprite from its list the instant `clearimg` runs.
            # Intercept the pair here, before the Transition node would
            # otherwise reach _emit_statement on its own with no way to
            # delay the already-emitted removal.
            transition_node = body[idx + 1]
            image_name = _resolve_image_path(node.image, images)
            _emit_hide_transition(transition_node.name, transition_node.loc, flagged, lines, _target_name(image_name))
            lines.append(f"clearslot {node.image.split()[0]}")  # see the plain-Hide branch below for why slot, not path
            skip_next = True
            continue
        if isinstance(node, Menu):
            _emit_menu(node, body[idx + 1 :], label_name, counter, worklist, lines, characters, images, flagged)
            return  # remainder was pushed to the worklist as a continuation label
        if isinstance(node, If):
            _emit_if(node, body[idx + 1 :], label_name, counter, worklist, lines, characters, images, flagged)
            return  # remainder was pushed to the worklist as a continuation label
        if isinstance(node, While):
            _emit_while(node, body[idx + 1 :], label_name, counter, worklist, lines, characters, images, flagged)
            return  # remainder was pushed to the worklist as a continuation label
        if isinstance(node, Label):
            # A label declared *inside* another label's body -- unusual but
            # not forbidden in Ren'Py; real content found in the wild (a
            # named point mid-scene, jumped back to directly to re-present
            # a choice after a failed/retry path, rather than a genuinely
            # nested scope -- confirmed against a real title's actual
            # source, not a converter/decompiler artifact). VNDS's own
            # label system is exactly as flat as Ren'Py's: every "@name" is
            # a global jump target, and falling through one during linear
            # execution is a no-op (script.moon's own `next_instruction`
            # skips a "label" line the same way) -- so this needs no
            # synthetic jump, just the marker inline, with the remainder of
            # *this* body (whatever follows the nested label at the same
            # level) continuing to execute under it exactly as Ren'Py
            # itself would fall through.
            lines.append(f"@{node.name}")
            _emit_body(
                node.body + body[idx + 1 :], node.name, counter, worklist, lines, characters, images, flagged,
                character_images, assets_dir, character_image_layer_files,
                portrait_defs, portrait_layer_files,
            )
            return  # remainder was folded into the nested label's own body above
        if isinstance(node, Play) and node.choices:
            # Ren'Py's randomized-file-choice idiom (`play sound [a, b,
            # c]`) as a genuine runtime random pick, not just approximated
            # to the first entry -- needs a _LabelCounter for its
            # synthetic labels (see _emit_random_play), unlike a plain
            # Play, so it can't go through the ordinary _emit_statement
            # path. Doesn't consume the remainder (unlike Menu/If/While/
            # Label above) -- just splices its own lines in and the loop
            # continues normally.
            _emit_random_play(node, label_name, counter, lines, flagged)
            continue
        _emit_statement(node, characters, images, flagged, lines, has_portraits=bool(portrait_defs))


def _emit_random_play(
    node: Play, label_name: str, counter: _LabelCounter, lines: list[str], flagged: FlaggedItems
) -> None:
    """Ren'Py's randomized-file-choice idiom (`play sound [a, "<silence
    0.5>", b]`, silence pseudo-entries already dropped by the parser) as
    a genuine runtime random pick -- not approximated to a fixed entry --
    composed entirely from existing VNDS primitives: `random` (already
    implemented, previously only wired to `renpy.random.randint`) rolls a
    die into a dedicated global, an `ifvar ... jump` chain (the existing
    single-line conditional-jump form) branches to one of N synthetic
    labels each playing a different real entry, converging back on a
    shared continuation label. Doesn't need the worklist (unlike Menu/If/
    While) -- nothing here consumes the rest of the body, it just splices
    itself into the current instruction stream inline."""
    choices = node.choices
    assert choices
    command = _PLAY_COMMAND.get(node.channel)
    generic_shape = None if command is not None else _resolve_custom_channel_shape(node.channel)
    if command is None and generic_shape is None:
        flagged.add(
            text=f"play {node.channel} [...]",
            reason=f"channel '{node.channel}' contains characters incompatible with the VNDS instruction format; audio dropped",
            loc=node.loc,
        )
        return
    if command is None:
        flagged.add(
            text=f"play {node.channel} [...]",
            reason=(
                f"custom audio channel not in the converter's known/verified set ('{node.channel}'); "
                f"behavior (loop={generic_shape[0]}, mixer={generic_shape[1]}) was inferred from the name"
            ),
            loc=node.loc,
        )
    var = counter.fresh(f"{label_name}_rand")
    cont_label = counter.fresh(f"{label_name}_rand_cont")
    choice_labels = [counter.fresh(f"{label_name}_rand_choice") for _ in choices]
    lines.append(f"random {var} 1 {len(choices)}")
    for i, choice_label in enumerate(choice_labels, start=1):
        lines.append(f"ifvar ({var} == {i}) jump {choice_label}")
    lines.append(f"jump {choice_labels[-1]}")  # safety net; random always lands in [1, len(choices)]
    for choice_label, file_ in zip(choice_labels, choices):
        lines.append(f"@{choice_label}")
        filename = _audio_filename(file_)
        if command is not None:
            if node.channel in _ONE_SHOT_CHANNELS:
                lines.append(f"{command} {filename} 1")
            else:
                lines.append(f"{command} {filename}")
        else:
            loop, mixer = generic_shape
            lines.append(f"play {node.channel} {filename} {1 if loop else 0} {mixer}")
        lines.append(f"jump {cont_label}")
    lines.append(f"@{cont_label}")


# The 6 custom Ren'Py statements below (statements.rpy) all show real,
# positioned/sized/colored text over a full-screen image in the PC version
# -- exact coordinates/sizes/colors read directly from each one's own
# `execute_*` function's Text()/Transform() calls. VNDS has no title-card/
# overlay-text system of its own, so these translate to the engine's new
# `overlay_text`/`overlay_clear` primitive (see src/engine/overlay.moon)
# rather than the dialogue box (fixed position/size/one font).
_DAY_TITLE_POS = (200, round(0.275 * 240))  # "Day" -- xalign .5, yalign .275
_DAY_NUMBER_POS = (200, round(0.4 * 240))  # xalign .5, yalign .4
_DAY_SUBTITLE_POS = (200, round(0.875 * 240))  # xalign .5, yalign .875
_DAY_TEXT_COLOR = "fff"
_DAY_MOOD_JINGLE = {
    "hope": "audio/jingle/glisten.mp3",
    "sad": "audio/jingle/hot_cocoa_short.ogg",
    "sparkles": "audio/jingle/sparkles.mp3",
    "ending": "audio/jingle/crisp_morning.mp3",
}
_DAY_DEFAULT_JINGLE = "audio/jingle/a_new_topic.mp3"

# execute_subchapter's yalign is fixed at 0.05; xcenter depends on the
# message's own length (short/medium/long), matching its 3 real
# thresholds/positions exactly -- pure string-length arithmetic, safely
# reproducible at convert time (no interpreter needed, unlike CharacterImage's
# layer_selector). The length-matched backing image (gui/subtitleS/M/L.png)
# is *not* reproduced (flagged approximated) -- a decorative box behind the
# text, not the information itself.
_SUBCHAPTER_Y = round(0.05 * 240)
_SUBCHAPTER_COLOR = "514944"
_SUBCHAPTER_SMALL_LEN = 16
_SUBCHAPTER_MEDIUM_LEN = 27
_SUBCHAPTER_SMALL_X = round(0.17 * 400)
_SUBCHAPTER_MEDIUM_X = round(0.225 * 400)
_SUBCHAPTER_LARGE_X = round(0.28 * 400)

_THE_END_POS = (round(0.0275 * 400), round(0.045 * 240))
_THE_END_COLOR = "fff"

_PLACEHOLDER_POS = (200, 120)
_PLACEHOLDER_TEXT = "Path currently under construction."


def _emit_day_card(node: DayCard, flagged: FlaggedItems, lines: list[str]) -> None:
    lines.append("window hide")
    lines.append("overlay_clear")
    bg = "chapter_titlecard_gyaru" if node.mood == "sparkles" else "chapter_titlecard"
    lines.append(f"bgload {bg}.t3x")
    x, y = _DAY_TITLE_POS
    lines.append(f"overlay_text day_title {x} {y} 80 {_DAY_TEXT_COLOR} {_escape_text('Day')}")
    x, y = _DAY_NUMBER_POS
    lines.append(f"overlay_text day_number {x} {y} 240 {_DAY_TEXT_COLOR} {_escape_text(node.day_number)}")
    _emit_transition("dissolve", node.loc, flagged, lines)
    lines.append("delay 120")
    jingle = _DAY_MOOD_JINGLE.get(node.mood, _DAY_DEFAULT_JINGLE)
    lines.append(f"music {_audio_filename(jingle)}")
    x, y = _DAY_SUBTITLE_POS
    lines.append(f"overlay_text day_subtitle {x} {y} 48 {_DAY_TEXT_COLOR} {_escape_text(node.subtitle)}")
    _emit_transition("dissolve", node.loc, flagged, lines)
    lines.append("delay 300")
    lines.append("bgload black.t3x")
    lines.append("overlay_clear")
    _emit_transition("dissolve", node.loc, flagged, lines)
    flagged.add(
        text=f'day "{node.day_number}" "{node.subtitle}" "{node.mood}"',
        reason="title-card visual style approximated (positioned text over a background, not the PC version's exact per-layer dissolve choreography/font)",
        loc=node.loc,
    )


def _subchapter_x(message: str) -> int:
    length = len(message.replace("{noalt}", "").replace("{/noalt}", ""))
    if length <= _SUBCHAPTER_SMALL_LEN:
        return _SUBCHAPTER_SMALL_X
    if length <= _SUBCHAPTER_MEDIUM_LEN:
        return _SUBCHAPTER_MEDIUM_X
    return _SUBCHAPTER_LARGE_X


def _emit_subchapter_card(node: SubchapterCard, flagged: FlaggedItems, lines: list[str]) -> None:
    x = _subchapter_x(node.message)
    lines.append(f"overlay_text subchapter_text {x} {_SUBCHAPTER_Y} 40 {_SUBCHAPTER_COLOR} {_escape_text(node.message)}")
    _emit_transition("dissolve", node.loc, flagged, lines)
    flagged.add(
        text=f'subchapter "{node.message}"',
        reason="chapter-heading backing image not reproduced (positioned/colored text shown on its own)",
        loc=node.loc,
    )


def _emit_the_end_card(node: TheEndCard, flagged: FlaggedItems, lines: list[str]) -> None:
    lines.append("window hide")
    lines.append("overlay_clear")
    lines.append("bgload the_end.t3x")
    x, y = _THE_END_POS
    lines.append(f"overlay_text the_end_title {x} {y} 40 {_THE_END_COLOR} {_escape_text(node.title)}")
    _emit_transition("dissolve", node.loc, flagged, lines)
    lines.append("delay 300")
    lines.append("overlay_clear")
    _emit_transition("dissolve", node.loc, flagged, lines)
    flagged.add(
        text=f'the_end "{node.title}"',
        reason="end-card visual style approximated (positioned text over a background, not the PC version's exact font/dissolve choreography)",
        loc=node.loc,
    )


def _emit_menu(
    menu: Menu,
    remainder: list[Node],
    label_name: str,
    counter: _LabelCounter,
    worklist: list[tuple[str, list[Node]]],
    lines: list[str],
    characters: dict[str, CharacterDef],
    images: dict[str, str],
    flagged: FlaggedItems,
) -> None:
    for node in menu.prompt:
        _emit_statement(node, characters, images, flagged, lines)

    cont_label = None
    if remainder:
        cont_label = counter.fresh(f"{label_name}_cont")
        worklist.append((cont_label, remainder))

    targets: list[str] = []
    for choice in menu.choices:
        choice_label = counter.fresh(f"{label_name}_choice")
        choice_body = list(choice.body)
        if cont_label and (not choice_body or not _is_control_transfer(choice_body[-1])):
            choice_body.append(Jump(target=cont_label, loc=menu.loc))
        worklist.append((choice_label, choice_body))
        targets.append(choice_label)

    options = "|".join(_escape_choice_option(c.text) for c in menu.choices)
    lines.append(f"choice {options}")
    lines.append(f"jump {'|'.join(targets)}")


def _emit_if(
    node: If,
    remainder: list[Node],
    label_name: str,
    counter: _LabelCounter,
    worklist: list[tuple[str, list[Node]]],
    lines: list[str],
    characters: dict[str, CharacterDef],
    images: dict[str, str],
    flagged: FlaggedItems,
) -> None:
    # Each branch (if/elif) is flattened into a single `ifvar <expr> jump
    # <label>` line (Phase 2.5's engine command, backed by Phase 2.4's
    # expression evaluator) — jumps only if the (possibly compound)
    # condition is true, otherwise falls through to the next check. `else`
    # (and, absent one, whatever follows the whole if/elif/else) becomes
    # its own synthetic label reached by an unconditional jump once every
    # check has fallen through, mirroring _emit_menu's continuation
    # mechanism.
    cont_label = None
    if remainder:
        cont_label = counter.fresh(f"{label_name}_cont")
        worklist.append((cont_label, remainder))

    trailing_jump = cont_label

    for branch in node.branches:
        body = list(branch.body)
        if cont_label and (not body or not _is_control_transfer(body[-1])):
            body.append(Jump(target=cont_label, loc=node.loc))

        if branch.condition is None:  # else
            trailing_jump = counter.fresh(f"{label_name}_else")
            worklist.append((trailing_jump, body))
        else:
            branch_label = counter.fresh(f"{label_name}_if")
            worklist.append((branch_label, body))
            lines.append(f"ifvar {branch.condition} jump {branch_label}")

    if trailing_jump:
        lines.append(f"jump {trailing_jump}")


def _emit_while(
    node: While,
    remainder: list[Node],
    label_name: str,
    counter: _LabelCounter,
    worklist: list[tuple[str, list[Node]]],
    lines: list[str],
    characters: dict[str, CharacterDef],
    images: dict[str, str],
    flagged: FlaggedItems,
) -> None:
    # A while loop is a labeled condition-check that either enters the body
    # or falls through to whatever follows; the body ends by jumping back
    # to the check (re-testing the condition) unless it already exits
    # early via its own jump/call/return (e.g. a menu choice that jumps
    # elsewhere entirely, bypassing the loop). The check itself is built
    # by composing a single-branch If (reusing _emit_if's own `ifvar
    # <cond> jump <label>` + continuation-on-false machinery) rather than
    # writing bespoke raw lines here.
    check_label = counter.fresh(f"{label_name}_while")
    body_label = counter.fresh(f"{label_name}_while_body")

    body = list(node.body)
    if not body or not _is_control_transfer(body[-1]):
        body.append(Jump(target=check_label, loc=node.loc))
    worklist.append((body_label, body))

    check_if = If(
        branches=[IfBranch(condition=node.condition, body=[Jump(target=body_label, loc=node.loc)])],
        loc=node.loc,
    )
    worklist.append((check_label, [check_if, *remainder]))

    lines.append(f"jump {check_label}")


def _character_layer_basename(path: Path) -> str:
    # CharacterImage layer files are real per-character assets discovered
    # dynamically at conversion time (never behind an `image NAME = "path"`
    # declaration the way _resolve_image_path's `images` dict covers), so
    # there's nothing to look up -- normalize the real file's own stem the
    # same way _image_filename does for an undeclared tag. The asset
    # pipeline's own resolve_character_image_layers converts each real
    # source file to exactly this same basename, so the two always agree
    # regardless of the source filename's actual spacing/capitalization
    # (real content: "Arms Jacket Neutral.png" -> "Arms_Jacket_Neutral.t3x").
    return path.stem.replace(" ", "_") + ".t3x"


# The original characterimage.rpy's own fixed constant (`im.matrix.tint(
# .75, 0.85, 1.0)`), applied to *every* resolved layer whenever
# "lighting_night" is one of the show's requested attributes -- confirmed
# real content: ~15 real character selectors check for it, but it isn't a
# layer at all (see expand_attrs' docstring) -- `_duplicate` special-cases
# it as a fixed screen-tint effect shared across every CharacterImage
# character, not a per-character value, so this constant is genuinely
# game-wide, not an approximation of something that varies.
_NIGHT_TINT = (0.75, 0.85, 1.0)


def _emit_character_image_show(
    node: Show,
    char_def: CharacterImageDef,
    assets_dir: Path | None,
    layer_files: dict[str, Path] | None,
    counter: _LabelCounter,
    flagged: FlaggedItems,
    lines: list[str],
    images: dict[str, str] | None = None,
) -> None:
    """Emits a CharacterImage-declared tag's `show <tag> <attrs>` as a
    real-time, runtime multi-layer sprite -- a `clearslot <tag>`
    (atomically replacing the character's *entire* previous layer set,
    see images.moon's `on "clearslot"`) followed by one ordinary `setimg`
    per resolved layer, each in its own `<tag>:<index>` slot so same-batch
    layers don't dedupe-remove each other (images.moon's existing
    per-slot-exact-match `setimg` dedup would otherwise only keep the
    last one). A persistent-gated selector (confirmed real content, e.g.
    margaret's `persistent.nude_sprites` check) becomes a real `ifvar`
    branch between the two pre-resolved layer lists, not a convert-time
    guess -- the actual live flag value decides at runtime, same as any
    other persistent-gated condition. `layer_shift` (a per-layer position
    offset) is never used by any real character in this game (confirmed
    via a full-game grep), so every layer draws at the exact same base
    position as the show's own resolved x/y -- a verified match to
    reality, not a simplification."""
    if node.approximated_atl:
        flagged.add(
            text=f"show {node.image}",
            reason=(
                "ATL animation approximated to a generic keyframe sequence (no exact preset match)"
                if node.anim is not None and node.anim.keyframes is not None
                else "ATL animation/zoom/alpha approximated to its final static xalign/yalign position"
            ),
            loc=node.loc,
        )

    words = node.image.split()
    slot = words[0]
    requested = frozenset(words[1:])
    x, y = _resolve_show_xy(node.position, node.xalign, node.yalign)
    prop_tokens = _static_prop_tokens(node)
    if "lighting_night" in requested:
        # checked against the *raw* requested attributes, not the
        # interpreter-facing `expanded` set below (expand_attrs excludes
        # "lighting_night" from that one entirely, matching the original
        # engine's own _duplicate) -- this is the same "check the raw
        # request separately" split the original does.
        tr, tg, tb = _NIGHT_TINT
        prop_tokens += f" tint_r={_format_prop_value(tr)} tint_g={_format_prop_value(tg)} tint_b={_format_prop_value(tb)}"

    try:
        expanded = expand_attrs(char_def, requested)
        layer_names, persistent_name = resolve_layers(char_def, expanded, assets_dir)
    except Exception as exc:  # noqa: BLE001 - any interpreter failure isolates to this one character/usage
        flagged.add(
            text=f"show {node.image}",
            reason=(
                f"CharacterImage layer_selector for '{slot}' couldn't be resolved for these attributes "
                f"({exc}); falling back to its default (no-attribute) pose"
            ),
            loc=node.loc,
        )
        expanded = frozenset()
        try:
            layer_names, persistent_name = resolve_layers(char_def, expanded, assets_dir)
        except Exception:  # noqa: BLE001 - even the default pose can't always resolve (e.g. no assets_dir)
            layer_names, persistent_name = [], None

    def emit_layers(names: list[str]) -> None:
        lines.append(f"clearslot {slot}")
        for index, lname in enumerate(names):
            resolved = (
                resolve_layer_file(lname, char_def.character_name, char_def.layers, assets_dir)
                if assets_dir is not None
                else None
            )
            if resolved is not None:
                path = Path(resolved[0])
                order_index = resolved[1]
                basename = _character_layer_basename(path)
                if layer_files is not None:
                    layer_files[basename[: -len(".t3x")]] = path
            elif images is not None and lname in images:
                # The original CharacterImage falls back to an ordinary
                # top-level declared image (`ImageReference`) whenever a
                # yielded layer name isn't found as a per-character file.
                # Resolving it the same way any other declared `image NAME
                # = "path"` show would, rather than dropping the layer
                # outright.
                basename = _resolve_image_path(lname, images)
                order_index = index
            else:
                flagged.add(
                    text=f"show {node.image}",
                    reason=f"CharacterImage layer '{lname}' has no resolvable per-character asset file",
                    loc=node.loc,
                )
                continue
            layer_slot = f"{slot}:{order_index}"
            lines.append(f"setimg {basename} {x} {y} {layer_slot}{prop_tokens}")
            if node.anim is not None:
                _emit_anim(node.anim, _target_name(basename), lines)

    if persistent_name is None:
        emit_layers(layer_names)
    else:
        try:
            layers_true = resolve_layers_with_persistent(char_def, expanded, True, assets_dir)
            layers_false = resolve_layers_with_persistent(char_def, expanded, False, assets_dir)
        except Exception:  # noqa: BLE001 - fall back to the already-resolved single list on any surprise
            layers_true = layers_false = layer_names
        true_label = counter.fresh(f"{slot}_ci_true")
        after_label = counter.fresh(f"{slot}_ci_after")
        lines.append(f"ifvar (persistent_{persistent_name} == 1) jump {true_label}")
        emit_layers(layers_false)
        lines.append(f"jump {after_label}")
        lines.append(f"@{true_label}")
        emit_layers(layers_true)
        lines.append(f"@{after_label}")

    if node.transition:
        _emit_transition(node.transition, node.loc, flagged, lines)


# Our Life: Beginnings & Always' real asset layout (confirmed against the
# extracted game): "images/characters/<folder>/<value>.png" for plain
# layers, "images/characters/<folder>/Expressions/<value>.png" for a
# static "expression" layer (brows/sweat/tears -- one file, no animation),
# and "images/characters/<folder>/Expressions/<value>_<slot><frame>.png"
# (frame 0/1/2) for the two animated slots (eyes/mouth) -- matches
# character_sprite.rpy's own `get_image`/`GetImagePath` path patterns
# exactly. `folder` is normally the ChangePortrait `chara` name itself;
# `GetFolder()`'s real fallback (probing whether a "_side"-suffixed
# variant folder exists instead) is approximated here as a static,
# convert-time directory-existence check against the same assets_dir
# CharacterImage already uses, rather than Ren'Py's own runtime
# `renpy.loadable()` probe -- the same approximation character_image.py's
# own `resolve_layer_file` already makes for its per-character assets.
@lru_cache(maxsize=None)
def _find_case_insensitive_dir(parent: Path, name: str) -> Path | None:
    # Always resolves via a real directory scan rather than a direct path
    # join -- confirmed real content: Our Life's on-disk folder names are
    # all-lowercase (e.g. "cove_8") while Portrait declarations/
    # ChangePortrait calls use the original mixed case ("Cove_8"). A
    # direct join would still open on NTFS's case-insensitive filesystem
    # but silently break on a case-sensitive one (Linux/CI) later, same
    # risk character_image.py's own resolve_layer_file already guards
    # against for its per-character asset files. Cached -- real content
    # (Our Life) makes 16000+ ChangePortrait calls, the overwhelming
    # majority reusing the same handful of (parent, name) pairs, so an
    # uncached `iterdir()` scan per call is a genuine, measured
    # performance problem (each scan just to resolve one already-seen
    # folder), not a hypothetical one.
    if not parent.is_dir():
        return None
    lowered = name.lower()
    for d in parent.iterdir():
        if d.is_dir() and d.name.lower() == lowered:
            return d
    return None


def _resolve_portrait_folder_dir(name: str, assets_dir: Path) -> Path | None:
    characters_dir = assets_dir / "images" / "characters"
    stripped = name.replace("_side", "")
    return _find_case_insensitive_dir(characters_dir, stripped) or _find_case_insensitive_dir(characters_dir, name)


@lru_cache(maxsize=None)
def _find_portrait_file(base_dir: Path, stem: str) -> Path | None:
    # Cached for the same reason as _find_case_insensitive_dir above --
    # the same (base_dir, stem) pair recurs across many of a game's
    # thousands of real ChangePortrait calls (e.g. a character's default
    # "eyes"/"n" pose reused constantly).
    if not base_dir.is_dir():
        return None
    lowered = stem.lower()
    for f in base_dir.iterdir():
        if f.is_file() and f.stem.lower() == lowered and f.suffix.lower() in (".png", ".webp", ".jpg", ".jpeg"):
            return f
    return None


def _portrait_layer_basename(path: Path) -> str:
    # Same normalization as CharacterImage's own _character_layer_basename
    # (spaces -> underscores, real per-character assets never behind an
    # ordinary `image NAME = "path"` declaration).
    return path.stem.replace(" ", "_") + ".t3x"


def _emit_portrait_update(
    node: PortraitUpdate,
    portrait_defs: dict[str, PortraitDef],
    assets_dir: Path | None,
    layer_files: dict[str, Path] | None,
    flagged: FlaggedItems,
    lines: list[str],
) -> None:
    """Emits one `$ ChangePortrait(...)` call as real `portrait`/
    `portrait_anim` VNDS instructions -- one per kwarg actually passed
    (matching `SetSpritePart`'s real incremental semantics: an untouched
    slot keeps whatever the engine already has drawn from a prior call
    for this `name`, so nothing needs a clearslot-style full replace the
    way CharacterImage's Show does). `eyes`/`mouth` slots emit
    `portrait_anim` (3 frame paths, for the engine's own blink/lip-flap
    timers); every other slot emits plain `portrait` (1 static path)."""
    portrait_def = portrait_defs.get(node.name)
    tint = node.tint or (1.0, 1.0, 1.0)
    for update in node.updates:
        text = f"ChangePortrait(chara=\"{node.name}\", {update.slot}=\"{update.value}\")"
        if assets_dir is None:
            flagged.add(text=text, reason="portrait layer has no resolvable asset file (no assets_dir given)", loc=node.loc)
            continue
        folder_dir = _resolve_portrait_folder_dir(node.name, assets_dir)
        if folder_dir is None:
            flagged.add(
                text=text,
                reason=f"portrait layer '{update.slot}={update.value}' has no resolvable per-character asset file",
                loc=node.loc,
            )
            continue
        base_dir = folder_dir / "Expressions" if update.is_expression_folder else folder_dir

        def resolve_one(stem: str) -> str | None:
            found = _find_portrait_file(base_dir, stem)
            if found is None:
                return None
            basename = _portrait_layer_basename(found)
            if layer_files is not None:
                layer_files[basename[: -len(".t3x")]] = found
            return basename

        if update.category in ("eyes", "mouth"):
            # Confirmed real content: Our Life declares animateEyes=True on
            # every real Portrait (frame1/2 files exist for every mood) but
            # animateMouth=False on all of them too (frame1/2 files for
            # "mouth" don't exist anywhere in the game's real asset tree at
            # all -- the lip-flap code path is real but genuinely never
            # exercised by this game). Only require the extra 2 frames when
            # this character's Portrait declaration actually enables that
            # animation; otherwise resolve just frame0 and reuse it for all
            # 3 slots (a real, correctly-static portrait, not a synthesized
            # animation that would just crash looking for files that were
            # never shipped).
            animate = (
                (portrait_def.animate_eyes if update.category == "eyes" else portrait_def.animate_mouth)
                if portrait_def is not None
                else False
            )
            frame0 = resolve_one(f"{update.value}_{update.slot}0")
            if frame0 is None:
                flagged.add(
                    text=text,
                    reason=f"portrait layer '{update.slot}={update.value}' has no resolvable per-character asset file",
                    loc=node.loc,
                )
                continue
            if animate:
                frames = [frame0, resolve_one(f"{update.value}_{update.slot}1"), resolve_one(f"{update.value}_{update.slot}2")]
                if any(f is None for f in frames):
                    frames = [frame0, frame0, frame0]  # declared animated but this mood has no frame1/2 -- fall back to static
            else:
                frames = [frame0, frame0, frame0]
            # Lowercased to match _emit_statement's own `speaking <name>`
            # token exactly (that one's derived from _resolve_speaker's
            # display name, also lowercased) -- a case-insensitive bridge
            # between Portrait's speaker="COVE"-style declaration and
            # whatever casing the Character's own display name uses.
            speaker = portrait_def.speaker.lower() if portrait_def is not None and portrait_def.speaker else None
            lines.append(
                f"portrait_anim {node.name} {update.slot} {frames[0]} {frames[1]} {frames[2]} "
                f"{update.category} {1 if (node.blink and animate) else 0} {1 if node.transition else 0} "
                f"{update.order_index} {_format_prop_value(tint[0])} {_format_prop_value(tint[1])} {_format_prop_value(tint[2])}"
                + (f" {speaker}" if speaker else " ~")
            )
        else:
            basename = resolve_one(update.value)
            if basename is None:
                flagged.add(
                    text=text,
                    reason=f"portrait layer '{update.slot}={update.value}' has no resolvable per-character asset file",
                    loc=node.loc,
                )
                continue
            lines.append(
                f"portrait {node.name} {update.slot} {basename} {update.category} "
                f"{1 if node.transition else 0} {update.order_index} "
                f"{_format_prop_value(tint[0])} {_format_prop_value(tint[1])} {_format_prop_value(tint[2])}"
            )


def _emit_statement(
    node: Node,
    characters: dict[str, CharacterDef],
    images: dict[str, str],
    flagged: FlaggedItems,
    lines: list[str],
    has_portraits: bool = False,
) -> None:
    if isinstance(node, Say):
        speaker = _resolve_speaker(node.who, characters)
        # A narrator line (no speaker) must still emit `nameplate ~` to
        # clear any nameplate left over from a preceding character line --
        # text.moon's `nameplate_text` only changes on an explicit
        # `nameplate` command, so without this a narrator line right after
        # a character line kept showing that character's name plate.
        if speaker:
            color = _resolve_speaker_color(node.who, characters)
            prefix = f"#{color.lstrip('#')} " if color else ""
            lines.append(f"nameplate {prefix}{speaker}")
        else:
            lines.append("nameplate ~")
        if has_portraits:
            # Only emitted for a game that actually uses ChangePortrait --
            # every other game's output stays byte-identical without this
            # line. Piggybacks on the same per-line cadence as nameplate
            # (reset every Say, narrator included) rather than a separate
            # begin/end bracket -- gates a portrait's lip-flap animation
            # (portrait_anim's own baked-in speaker name, matched case-
            # insensitively) to whichever character's dialogue is
            # *currently displayed*, approximating Ren'Py's real begin/
            # slow_done/end callback timing (which only animates while
            # text is actively revealing) as "animates for the whole time
            # this line is the current text" -- a reasonable bound given
            # the engine has no per-character speech-timing signal
            # otherwise. `~` (matching nameplate's own no-speaker token)
            # means "nobody" -- no portrait's mouth lip-flaps for a
            # narrator line.
            lines.append(f"speaking {speaker.lower() if speaker else '~'}")
        lines.append(f"text {_escape_text(node.what)}")
    elif isinstance(node, Scene):
        # backgrounds are always full-screen (§5.1) -- any positioning
        # (symbolic or ATL xalign/yalign) has no VNDS equivalent, same
        # treatment either way.
        if node.position:
            flagged.add(
                text=f"scene {node.image} at {node.position}",
                reason="scene position has no VNDS equivalent (bgload is full-screen); position ignored",
                loc=node.loc,
            )
        elif node.xalign is not None or node.yalign is not None:
            flagged.add(
                text=f"scene {node.image}",
                reason="scene ATL position has no VNDS equivalent (bgload is full-screen); position ignored",
                loc=node.loc,
            )
        lines.append(f"bgload {_resolve_image_path(node.image, images)}")
        if node.transition:
            _emit_scene_transition(node.transition, node.loc, flagged, lines)
    elif isinstance(node, Show):
        x, y = _resolve_show_xy(node.position, node.xalign, node.yalign)
        if node.approximated_atl:
            flagged.add(
                text=f"show {node.image}",
                reason=(
                    "ATL animation approximated to a generic keyframe sequence (no exact preset match)"
                    if node.anim is not None and node.anim.keyframes is not None
                    else "ATL animation/zoom/alpha approximated to its final static xalign/yalign position"
                ),
                loc=node.loc,
            )
        image_name = _resolve_image_path(node.image, images)
        # The image tag's first word is Ren'Py's own character/slot identity
        # (e.g. "chance" in "chance a01 grin") -- passed through as setimg's
        # 4th token so the engine can replace a character's sprite by *who*
        # it is, not by screen position. Positions repeat (only 3 canonical
        # slots -- left/center/right), so a scene with 3+ simultaneous
        # characters can put a new character at the same position an
        # earlier, still-visible one occupies; a position-only match would
        # incorrectly remove that earlier sprite instead of leaving it
        # alone (confirmed on real hardware: sprites stacked again once a
        # scene had 3+ characters on screen at once).
        slot = node.image.split()[0]
        lines.append(f"setimg {image_name} {x} {y} {slot}{_static_prop_tokens(node)}")
        if node.anim is not None:
            _emit_anim(node.anim, _target_name(image_name), lines)
        elif node.transition:
            # An ATL animation (above) already handles this show's visual
            # entrance; the two forms don't co-occur in real content
            # (`with` attaches to a plain `show x with y` line, ATL blocks
            # use `show x:` with no trailing `with` on that same header).
            _emit_show_transition(node.transition, node.loc, flagged, lines, _target_name(image_name))
    elif isinstance(node, Hide):
        # extended, real-hardware regression: this used to resolve `node.image`
        # to one specific asset path and emit a path-matched `clearimg` --
        # but `hide <tag>` (almost always given with no attributes) doesn't
        # know or care which specific expression/composited file the
        # character currently happens to be shown as, so the path essentially
        # never matched the sprite actually on screen, and the old sprite
        # was left stuck ("stacking" once a later show reused the same slot
        # in the same position). Matches the same tag/slot identity Show's
        # setimg already replaces by (see the "3+ characters" comment below)
        # via images.moon's existing `clearslot`, rather than a path.
        image_name = _resolve_image_path(node.image, images)
        if node.transition:
            _emit_hide_transition(node.transition, node.loc, flagged, lines, _target_name(image_name))
        slot = node.image.split()[0]
        lines.append(f"clearslot {slot}")
    elif isinstance(node, Transition):
        _emit_standalone_transition(node.name, node.loc, flagged, lines)
    elif isinstance(node, Play):
        if node.is_queue:
            flagged.add(
                text=f"queue {node.channel} \"{node.file}\"",
                reason="queue approximated as an immediate play (no track-chaining support yet)",
                loc=node.loc,
            )
        command = _PLAY_COMMAND.get(node.channel)
        if command is None:
            filename = _audio_filename(node.file)
            shape = _resolve_custom_channel_shape(node.channel)
            if shape is None:
                flagged.add(
                    text=f"play {node.channel} \"{node.file}\"",
                    reason=f"channel '{node.channel}' contains characters incompatible with the VNDS instruction format; audio dropped",
                    loc=node.loc,
                )
            else:
                loop, mixer = shape
                lines.append(f"play {node.channel} {filename} {1 if loop else 0} {mixer}")
                flagged.add(
                    text=f"play {node.channel} \"{node.file}\"",
                    reason=(
                        f"custom audio channel not in the converter's known/verified set ('{node.channel}'); "
                        f"behavior (loop={loop}, mixer={mixer}) was inferred from the name"
                    ),
                    loc=node.loc,
                )
        else:
            # A random-choice Play (node.choices set) is normally
            # intercepted by _emit_body before it ever reaches here (it
            # needs a _LabelCounter for its synthetic random/ifvar/jump
            # chain -- see _emit_random_play); reaching here with choices
            # still set means a caller bypassed _emit_body (e.g. a direct
            # emit_script_vnds test) -- fall back to the first entry
            # rather than silently dropping the whole cue.
            filename = _audio_filename(node.file)
            if node.channel in _ONE_SHOT_CHANNELS:
                lines.append(f"{command} {filename} 1")
            else:
                lines.append(f"{command} {filename}")
    elif isinstance(node, Stop):
        command = _STOP_COMMAND.get(node.channel)
        if command is None:
            shape = _resolve_custom_channel_shape(node.channel)
            if shape is None:
                flagged.add(
                    text=f"stop {node.channel}",
                    reason=f"channel '{node.channel}' contains characters incompatible with the VNDS instruction format; stop dropped",
                    loc=node.loc,
                )
            else:
                lines.append(f"stop {node.channel}")
                flagged.add(
                    text=f"stop {node.channel}",
                    reason=f"custom audio channel not in the converter's known/verified set ('{node.channel}'); behavior inferred from the name",
                    loc=node.loc,
                )
        else:
            lines.append(command)
    elif isinstance(node, SetVolume):
        channel = _VOLUME_CHANNEL.get(node.channel)
        if channel is None:
            shape = _resolve_custom_channel_shape(node.channel)
            if shape is None:
                flagged.add(
                    text=f"renpy.music.set_volume(..., channel='{node.channel}')",
                    reason=f"channel '{node.channel}' contains characters incompatible with the VNDS instruction format; volume change dropped",
                    loc=node.loc,
                )
            else:
                # setvolume is already fully generic at the VNDS-
                # instruction-format level (audio.moon's channel_table
                # resolves any name via its `channels` fallback) -- no
                # shape/loop/mixer needed here, unlike play/stop.
                lines.append(f"setvolume {node.channel} {_format_prop_value(node.level)} {_format_prop_value(node.delay)}")
                flagged.add(
                    text=f"renpy.music.set_volume(..., channel='{node.channel}')",
                    reason=f"custom audio channel not in the converter's known/verified set ('{node.channel}'); behavior inferred from the name",
                    loc=node.loc,
                )
        else:
            lines.append(f"setvolume {channel} {_format_prop_value(node.level)} {_format_prop_value(node.delay)}")
    elif isinstance(node, Window):
        lines.append(f"window {node.state}")
    elif isinstance(node, Random):
        lines.append(f"random {node.var} {node.low} {node.high}")
    elif isinstance(node, Pause):
        if node.seconds is None:
            flagged.add(
                text="pause",
                reason="bare pause has no effect; VNDS already waits for input after each text line",
                loc=node.loc,
            )
        else:
            lines.append(f"delay {round(node.seconds * 60)}")
    elif isinstance(node, Jump):
        lines.append(f"jump {node.target}")
    elif isinstance(node, Call):
        lines.append(f"call {node.target}")
    elif isinstance(node, Return):
        lines.append("return")
    elif isinstance(node, Set):
        # Ren'Py store variables are effectively global game state, unlike
        # the engine's separate `setvar` (local) / `gsetvar` (global) split
        # — always emit `gsetvar` since there's no Ren'Py-level distinction
        # to map `setvar` onto. Always "=" now that Phase 2.4's evaluator
        # handles the expression itself (self-referential accumulation is
        # just `var = (var + expr)`, no separate +/- modifier needed).
        lines.append(f"gsetvar {node.var} = {node.expr}")
    elif isinstance(node, DayCard):
        _emit_day_card(node, flagged, lines)
    elif isinstance(node, SubchapterCard):
        _emit_subchapter_card(node, flagged, lines)
    elif isinstance(node, SubchapterHide):
        # a real, exact translation (not approximated) -- dismisses
        # exactly the overlay SubchapterCard put up.
        lines.append("overlay_clear")
    elif isinstance(node, ResetAudio):
        # a real, exact translation now that Tier 3's setvolume/ambiance/
        # music2 channels exist -- statements.rpy's execute_reset_audio's
        # own 4 calls, one command each.
        lines.append("setvolume music 1 0")
        lines.append("setvolume music2 1 0")
        lines.append("stopmusic2")
        lines.append("stopambiance")
    elif isinstance(node, TheEndCard):
        _emit_the_end_card(node, flagged, lines)
    elif isinstance(node, Placeholder):
        x, y = _PLACEHOLDER_POS
        lines.append("overlay_clear")
        lines.append(f"overlay_text placeholder_msg {x} {y} 32 fff {_escape_text(_PLACEHOLDER_TEXT)}")
        flagged.add(
            text="placeholder",
            reason="renpy.rollback() has no VNDS equivalent (no rollback/undo mechanism); script continues linearly instead of dead-ending this path",
            loc=node.loc,
        )
    elif isinstance(node, Unsupported):
        problem_id = flagged.add(text=node.text, reason=node.reason, loc=node.loc)
        lines.append(f"# FLAGGED {problem_id}")
    else:  # pragma: no cover - exhaustive per the parser's Node union
        raise AssertionError(f"unhandled node type: {type(node).__name__}")
