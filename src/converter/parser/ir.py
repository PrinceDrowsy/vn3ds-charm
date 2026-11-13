"""Internal representation for the Ren'Py subset parser.

Mirrors the source's block structure (labels containing an ordered list of
statements; menu choices containing their own nested statement lists).
Flattening this into VN3DS-CHARM's flat script.vnds label/jump format is the
emitter's job (Phase 1.2), not the parser's.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceLocation:
    file: str
    line: int

    def __str__(self) -> str:
        return f"{self.file}:{self.line}"


@dataclass
class Say:
    who: str | None  # None = narrator; a Character() varname or a literal name
    what: str
    loc: SourceLocation


@dataclass
class Scene:
    image: str
    position: str | None  # left / center / right
    loc: SourceLocation
    transition: str | None = None  # raw Ren'Py transition name, e.g. "dissolve"
    # From an ATL block (`show/scene X: xalign N yalign N ...`), a precise
    # 0.0-1.0 screen fraction rather than the coarser left/center/right
    # snap. `approximated_atl` is True when the block also used a timed
    # tween (`linear`/`ease`) or an unrepresentable property (zoom/alpha,
    # no VNDS equivalent) — approximated by collapsing straight to the
    # block's final static values, dropping the animation/property itself.
    xalign: float | None = None
    yalign: float | None = None
    # `yalign` is the *position* fraction (Ren'Py's `ypos`/the position half
    # of the `yalign` shorthand); `yanchor` is the independent *anchor*
    # fraction (Ren'Py's `yanchor`/the anchor half of the same shorthand).
    # Only meaningfully different from `yalign` when a transform explicitly
    # overrides `ypos` after a `yalign`/`yanchor` line (real content:
    # `yalign 1.0 ypos 1.2` — anchor stays 1.0, position becomes 1.2).
    # Backgrounds never actually apply either (always full-screen, §5.1) —
    # kept here only so Scene's existing position-ignored flagging stays
    # accurate for content using yanchor/ycenter instead of yalign.
    yanchor: float | None = None
    approximated_atl: bool = False


@dataclass
class AnimSpec:
    """A timed ATL animation extracted from a `show X:` block (VN3DS-spec.md
    §9.1). Either `preset` is set (an exact or approximated match to one of
    the engine's named presets) or `keyframes` is set (the general
    fallback, always flagged `approximated` by the caller) — never both."""
    duration: float
    preset: str | None = None
    ease: str | None = None
    keyframes: list[tuple[float, dict[str, float]]] | None = None  # (normalised t 0.0-1.0, {prop: value})


@dataclass
class Show:
    image: str
    position: str | None
    loc: SourceLocation
    transition: str | None = None
    xalign: float | None = None
    yalign: float | None = None  # ypos fraction -- see Scene.yanchor's docstring
    yanchor: float | None = None  # anchor fraction, independent of yalign's position fraction
    # Static zoom/rotate/alpha resolved from an ATL block/named transform
    # (e.g. `zoom 1.4` in one of Mice Tea's "close shot" transforms) --
    # actually applied at setimg time via the engine's existing per-sprite
    # sx/sy/r/alpha animation state (images.moon's draw_foreground already
    # reads these every frame; they just previously defaulted to 1/1/0/1
    # with no way for a *static* (non-animated) block to seed them).
    sx: float | None = None
    sy: float | None = None
    rotate: float | None = None
    alpha: float | None = None
    approximated_atl: bool = False
    anim: AnimSpec | None = None


@dataclass
class Hide:
    image: str
    loc: SourceLocation
    transition: str | None = None


@dataclass
class Transition:
    """A standalone `with <name>` statement, applying to whatever
    scene/show/hide immediately preceded it."""

    name: str
    loc: SourceLocation


@dataclass
class Play:
    # "music" | "sound" | "voice" | "audio" (Ren'Py's built-in one-shot
    # channel, aliased at emission to the same commands as "sound") |
    # "ambiance" (a real, independent 4th engine channel -- see
    # audio.moon -- since it legitimately plays simultaneously with
    # "music" in real content, confirmed via
    # `renpy.music.register_channel`).
    channel: str
    file: str
    is_queue: bool  # from Ren'Py `queue`, approximated as an immediate play (no chaining yet)
    loc: SourceLocation
    # Ren'Py's randomized-file-choice idiom, `play sound [a, "<silence
    # N>", b]` -- when set, `file` is just `choices[0]` (a safe fallback
    # for any caller that doesn't know about `choices`) and the emitter
    # instead synthesizes a genuine runtime random pick across every
    # entry (VN3DS-spec's own `random` + `ifvar` primitives), not just the
    # first one -- real per-playthrough variety, not an approximation.
    choices: list[str] | None = None


@dataclass
class Stop:
    channel: str  # same set as Play.channel
    loc: SourceLocation


@dataclass(frozen=True)
class PortraitLayerUpdateIR:
    """One resolved slot update within a `PortraitUpdate` node -- field
    shape mirrors converter.parser.character_sprite.PortraitLayerUpdate
    exactly (duplicated here, not imported, to keep this module free of
    imports from other parser submodules -- ir.py is the one file every
    other parser module imports *from*, never the reverse)."""

    slot: str
    value: str
    order_index: int
    category: str  # "eyes" | "mouth" | "glow" | "magic" | "expression" | "plain"
    is_expression_folder: bool


@dataclass
class PortraitUpdate:
    """`$ ChangePortrait(chara, blink=.., transition=.., matrix=.., **kwargs)`
    -- Our Life: Beginnings & Always' bespoke multi-layer live-rendered
    portrait system (see character_sprite.py's module docstring for the
    full architecture). Already fully resolved at parse time (unlike
    CharacterImage's Show-node deferral to emission time) -- ChangePortrait's
    kwargs are already literal slot values, no selector-function
    interpretation needed, so there's nothing left for the emitter to
    decide except real asset-file paths (which do need assets_dir, a
    build-bundle-time concern, same as CharacterImage's own layer-file
    resolution)."""

    name: str  # the `chara` argument -- key into the engine's own per-name sprite state
    blink: bool
    transition: bool
    updates: tuple[PortraitLayerUpdateIR, ...]
    tint: tuple[float, float, float] | None
    loc: SourceLocation


@dataclass
class SetVolume:
    """`renpy.music.set_volume(level, channel=..., delay=...)` -- a real
    engine feature (audio.moon tweens the named channel's volume toward
    `level` over `delay` seconds), not an approximation; the engine
    already computes a base sound/music volume from the "config" event,
    this just retargets one channel's current volume at runtime (e.g.
    Mice Tea's `reset_audio` custom statement resetting music/music2 back
    to full volume after a scene fades them down)."""

    channel: str
    level: float
    delay: float
    loc: SourceLocation


@dataclass
class DayCard:
    """Mice Tea's custom `day "N" "subtitle" ["mood"]` statement
    (`statements.rpy`'s `execute_day`) -- a title-card beat (a "Day",
    the day number, and a subtitle, each its own positioned/sized/colored
    text, over a full-screen image, with a mood-specific jingle). `mood`
    defaults to "default" (see `statements.rpy`'s own `parse_day`) when
    the third argument is omitted."""

    day_number: str
    subtitle: str
    mood: str
    loc: SourceLocation


@dataclass
class SubchapterCard:
    """`subchapter "message"` (`statements.rpy`'s `execute_subchapter`) --
    a smaller corner chapter-heading overlay, shown alongside (not
    replacing) whatever scene/dialogue is already on screen."""

    message: str
    loc: SourceLocation


@dataclass
class SubchapterHide:
    """`subchapter_hide` -- dismisses the `SubchapterCard` overlay."""

    loc: SourceLocation


@dataclass
class ResetAudio:
    """`reset_audio` (`statements.rpy`'s `execute_reset_audio`) -- resets
    music/music2's volume to full and stops music2/ambiance, used between
    scenes as an audio-state cleanup beat."""

    loc: SourceLocation


@dataclass
class TheEndCard:
    """`the_end "title"` (`statements.rpy`'s `execute_the_end`) -- the
    game's ending title card."""

    title: str
    loc: SourceLocation


@dataclass
class Placeholder:
    """`placeholder ["wip"]` (`statements.rpy`'s `execute_placeholder`) --
    a dev-tool marker for an unfinished content path, showing a "Path
    currently under construction" message. The PC version follows this
    with `renpy.rollback()` (undoing to the player's previous choice) --
    VNDS has no rollback/undo mechanism at all (a real, separately-tracked
    future phase, not attempted here), so this is the one piece of the 6
    custom statements with a genuine, narrower fidelity gap: the message
    shows, but the script continues linearly past it rather than dead-
    ending the path. Zero real usages found in Mice Tea's own script
    content (the statement exists but is never actually invoked)."""

    loc: SourceLocation


@dataclass
class Pause:
    seconds: float | None  # None = bare `pause` (no-op; VNDS already waits for input)
    loc: SourceLocation


@dataclass
class Window:
    state: str  # "show" | "hide"
    loc: SourceLocation


@dataclass
class Random:
    """`$ var = renpy.random.randint(low, high)` -> the original VNDS
    `random` command (already implemented in script.moon since Phase 0,
    never wired into the converter until now). Only literal int bounds are
    resolvable, matching the engine's own `num(c[3])`/`num(c[4])` parsing."""

    var: str
    low: str
    high: str
    loc: SourceLocation


@dataclass
class Jump:
    target: str
    loc: SourceLocation


@dataclass
class Call:
    target: str
    loc: SourceLocation


@dataclass
class Return:
    loc: SourceLocation


@dataclass
class MenuChoice:
    text: str
    body: list[Node]
    loc: SourceLocation


@dataclass
class Menu:
    choices: list[MenuChoice]
    loc: SourceLocation
    # Statements (usually a Say) appearing before the first choice, e.g. a
    # narrator/character line posing the question the menu answers.
    prompt: list[Node] = field(default_factory=list)


@dataclass
class Set:
    """A variable assignment: Ren'Py `default`/`define` of a literal, or `$
    var = <expr>` / `var += <expr>` / `var -= <expr>`. `expr` is a rendered,
    validated expression string in the safe subset (§6.1) that the engine's
    expr.moon evaluator understands — a literal, a bare variable reference,
    or a full arithmetic/comparison/boolean expression. Emitted as VNDS
    `gsetvar <var> = <expr>` (Phase 2.4's evaluator handles the rest)."""

    var: str
    expr: str
    loc: SourceLocation


@dataclass
class IfBranch:
    # An expr.moon-compatible expression string; None means this is the
    # trailing `else`.
    condition: str | None
    body: list[Node]


@dataclass
class If:
    branches: list[IfBranch]
    loc: SourceLocation


@dataclass
class While:
    """`while <cond>: <body>` — most commonly Ren'Py's "repeat a menu until
    the player picks an exit option" conversation-topic loop
    (`while inconvo: menu: ...`). `condition` is an expr.moon-compatible
    expression string, same as IfBranch.condition."""

    condition: str
    body: list[Node]
    loc: SourceLocation


@dataclass
class Unsupported:
    """A construct outside the supported subset. Parsing continues past it —
    the converter always terminates with a Problem Report, never a crash."""

    text: str
    reason: str
    loc: SourceLocation


@dataclass
class Label:
    name: str
    body: list[Node]
    loc: SourceLocation


@dataclass
class CharacterDef:
    varname: str
    # None is a deliberate, valid Ren'Py idiom (`Character(None, ...)`) for
    # a styled-but-nameless narrator — distinct from a parse failure, which
    # is reported via Unsupported instead of ever reaching this dataclass.
    display_name: str | None
    color: str | None
    loc: SourceLocation
    # `Character(namebox_background="gui/namebox/nameboxXXX.png")` — a
    # per-character nameplate skin override (VN3DS-spec.md §6, the custom
    # UI-asset-import system). Confirmed real content: Mice Tea's
    # characters.rpy uses this 84 times. Resolved to a converted bundle
    # basename by assets/pipeline.py's resolve_ui_assets, same as the
    # game-wide default namebox.
    namebox_background: str | None = None


Node = (
    Say
    | Scene
    | Show
    | Hide
    | Transition
    | Play
    | Stop
    | SetVolume
    | DayCard
    | SubchapterCard
    | SubchapterHide
    | ResetAudio
    | TheEndCard
    | Placeholder
    | Pause
    | Window
    | Random
    | Jump
    | Call
    | Return
    | Menu
    | Set
    | If
    | While
    | Unsupported
    | PortraitUpdate
)


@dataclass
class ScreenText:
    text: str


@dataclass
class ScreenButton:
    label: str
    action: str  # already a resolved VNDS action string, e.g. "jump start"


@dataclass
class ScreenBox:
    """A vbox/hbox layout container. VNDS/the engine's renderer collapses
    both to "items in order" (listbox.moon has no side-by-side layout) —
    the distinction is kept here only because the source syntax has it."""
    children: "list[ScreenNode]"


@dataclass
class ScreenIfBranch:
    cond: str | None  # None = else (always taken if reached)
    children: "list[ScreenNode]"


@dataclass
class ScreenIf:
    branches: list[ScreenIfBranch]


@dataclass
class ScreenHotspot:
    """One `hotspot (x, y, w, h) action <expr>` region inside an
    `imagemap:` block. Real Ren'Py authors these as absolute pixels in the
    ground image's own native resolution -- but the asset pipeline may
    resize that same ground image at convert time (e.g. to fit the
    engine's 400x240 target screen), so raw pixel values would land in
    the wrong place once the *actual loaded* image has different real
    dimensions (a real-hardware regression: confirmed via Jisei's real
    main_menu, ground image 1024x768 resized to 320x240, every hotspot
    landing hundreds of pixels outside the visible image, making every
    option unselectable). `x`/`y`/`w`/`h` are therefore fractions
    (0.0-1.0) of the game's own declared design resolution
    (`config.screen_width`/`config.screen_height`, see
    `scan_screen_resolution`) -- resolution-independent, same convention
    already used for ATL xalign/yalign. The engine multiplies these
    fractions by whatever the actually-loaded ground image's real pixel
    dimensions turn out to be at draw time. `action is None` means
    `NullAction()` — a real, intentional no-op (a decorative/locked
    hotspot), never a resolution failure; a hotspot whose action can't be
    resolved at all is dropped entirely at parse time rather than kept
    with `action=None` (see rpy_parser.py's `_parse_hotspot_action`)."""
    x: float
    y: float
    w: float
    h: float
    action: str | None


@dataclass
class ScreenImagemap:
    """A Ren'Py `imagemap:` block — a background (`ground`) image plus
    pixel-rectangle touch regions mapped to actions. Real 13-corpus survey:
    6 of 13 games use this, most commonly for `main_menu` but also in
    custom in-game screens (galleries, character creators, confirm
    dialogs) — general enough to be its own `ScreenNode` variant, not a
    main-menu special case. No `idle`/`hover` state is kept: real 3DS
    hardware is touch-only (no continuous mouse hover), so only `ground`
    is ever drawn."""
    ground: str
    hotspots: list[ScreenHotspot]


ScreenNode = ScreenText | ScreenButton | ScreenBox | ScreenIf | ScreenImagemap


@dataclass
class ScreenDef:
    """A parsed `screen <name>:` block (VN3DS-spec.md's pulled-forward
    Phase 5.1 custom-screen runtime) — only the common subset (vbox/hbox,
    text, textbutton + a handful of actions, if/elif/else, imagemap/
    hotspot) is supported; anything else makes the whole screen
    `Unsupported` rather than a partial/lossy conversion."""
    name: str
    root: ScreenBox
    loc: SourceLocation


@dataclass
class FrameAsset:
    """A Ren'Py `Frame(image, borders, tile=...)`-declared 9-patch UI asset
    (VN3DS-spec.md §6, the custom UI-asset-import system) — `borders` is
    (left, top, right, bottom) in source-image pixels; fixed-size corners,
    edges/center either stretched (`tile=False`) or tiled (`tile=True`) to
    fit whatever size the engine draws it at (see `ui_frame.moon`'s
    `draw_frame`). `image` is the original source-relative path (resolved
    to a converted bundle basename by assets/pipeline.py's
    `resolve_ui_assets`, same as every other asset path in this IR)."""
    image: str
    borders: tuple[int, int, int, int]
    tile: bool


@dataclass
class Script:
    characters: dict[str, CharacterDef] = field(default_factory=dict)
    labels: list[Label] = field(default_factory=list)
    # Ren'Py `image <tag> = "<path>"` declarations, tag -> declared path.
    # Only literal string paths are resolvable here; ATL blocks and
    # displayable-returning calls (Transform, Blink, ...) aren't.
    images: dict[str, str] = field(default_factory=dict)
    # `image <tag> = im.Composite(None, (0,0), "layer1", (0,0), "layer2", ...)`
    # declarations, tag -> ordered layer paths (base first). A common Ren'Py
    # pattern for swappable face parts (base/eyebrows/mouth/eyes) that isn't
    # a plain file path, so `images` can't represent it, but *is* resolvable
    # at convert time by alpha-compositing the layers into one real image
    # (see assets/pipeline.py's `resolve_composite_images`).
    composites: dict[str, list[str]] = field(default_factory=dict)
    # Top-level `default`/`define` of a literal (int/bool/str), in source
    # order — emitted ahead of the first label so they execute once at
    # script start, matching Ren'Py's "runs before the game begins" timing.
    top_level_sets: list[Set] = field(default_factory=list)
    # Custom `screen <name>:` definitions, registered the same way
    # top_level_sets are (once, before the first label) so `show_screen`
    # can reference them from anywhere.
    screens: list[ScreenDef] = field(default_factory=list)
    # Path (relative to the game/ folder) of the game's own
    # `style.default.font = "..."` declaration, if found — almost always
    # sitting inside an `init python:` block (arbitrary Python, otherwise
    # entirely unparsed) so this is recovered by a standalone regex scan
    # over the raw source rather than the statement-by-statement parser.
    # Lets the real hardware bundle use the game's own intended font
    # (images.moon's `text.moon` already has an unused "default.ttf"
    # override mechanism) instead of always falling back to LÖVE's
    # generic built-in font.
    default_font: str | None = None
    # The game's own typewriter reveal speed (`config.default_text_cps`/
    # `config.text_cps`, a static value — NOT `preferences.text_cps`,
    # which is a *runtime-adjustable* user setting some games default to 0
    # instead of a fixed cps and let the player change via an options
    # menu, out of scope here), recovered the same way default_font is —
    # a standalone regex scan, since it's almost always inside an
    # `init python:` block. text.moon previously always used a hardcoded
    # 40 cps regardless of what the source game actually specified.
    default_text_cps: float | None = None
    # The custom UI-asset-import system (VN3DS-spec.md §6): the game's own
    # dialogue textbox is a plain background image (confirmed real
    # content: no Frame()/border-scaling in either target game, just a
    # fixed-size `Image("gui/textbox.png", ...)` or legacy
    # `style.window.background = "..."`) -- unlike namebox/choice buttons
    # below, which are real 9-patch Frame()s. Recovered the same
    # standalone-regex-scan way default_font is.
    textbox_image: str | None = None
    # The nameplate/namebox background -- a real Frame() in both target
    # games (Mice Tea: `tile=True`, genuinely tiled, not stretched).
    namebox: "FrameAsset | None" = None
    # In-story choice / custom-screen / save-load / main-menu button
    # backgrounds (listbox.moon's single shared widget) -- both target
    # games ship exactly 2 states (idle/hover), matching listbox.moon's
    # existing 2-state model.
    choice_idle: "FrameAsset | None" = None
    choice_hover: "FrameAsset | None" = None
    # The game's own declared design/authoring resolution (see
    # scan_screen_resolution), used both for ATL xpos/ypos rescaling
    # (rpy_parser.py's _resolve_atl_value) and, downstream, for scaling
    # foreground/character art by the same proportion as the rest of the
    # game's composition (see pipeline.py's foreground-scale fix) —
    # always set (falls back to (800, 600) when undeclared), so never
    # actually None once parse_rpy has run.
    screen_resolution: tuple[int, int] | None = None
