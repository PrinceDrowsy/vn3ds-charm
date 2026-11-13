"""Classifies a raw FlaggedItem (from the parser/emitter) into a full Problem
(severity + category + human-readable message/suggestion).

Rules are matched by the exact `reason` strings the parser and emitter
produce (see src/converter/parser/rpy_parser.py and
src/converter/emitters/vnds_writer.py) — keep these in sync if those reasons
change wording.
"""
from __future__ import annotations

from converter.emitters import FlaggedItem

from .schema import Category, Problem, Severity

_MAX_SNIPPET = 80


def _truncate(text: str) -> str:
    text = text.strip()
    return text if len(text) <= _MAX_SNIPPET else text[: _MAX_SNIPPET - 1] + "…"


# (reason prefix, severity, category, message, suggestion). category="unknown"
# means "sniff it from the source text instead" (see _sniff_category below).
_RULES: list[tuple[str, Severity, Category, str, str]] = [
    (
        "renpy.block_rollback() is a no-op",
        "info",
        "flow",
        "Rollback/history isn't implemented yet (Phase 3.7), so there's nothing for this to disable.",
        "",
    ),
    (
        "bare variable reference has no effect",
        "info",
        "flow",
        "A bare variable-name statement has no effect in Ren'Py either; likely leftover debug code.",
        "",
    ),
    (
        "with None has no effect",
        "info",
        "atl",
        "`with None` explicitly cancels any transition in Ren'Py too; there's nothing to convert.",
        "",
    ),
    (
        "movie/video playback has no VNDS equivalent",
        "manual",
        "video",
        "Movie/video playback has no VNDS equivalent and needs a native reimplementation (VN3DS-spec.md §6).",
        "Reimplement this cutscene natively, or provide a static substitute.",
    ),
    (
        "custom transition definition has no VNDS equivalent",
        "approximated",
        "atl",
        "This custom named transition has no VNDS equivalent, but any `with <name>` using it already downgrades to a plain dissolve regardless.",
        "Review the transition; reimplement a closer match manually if the fidelity loss matters.",
    ),
    (
        "default Ren'Py screen already provided natively",
        "info",
        "screen",
        "This is one of Ren'Py's own default screens (say/choice/input/nvl/menus/save/load/...), which the engine already replaces with its own native UI.",
        "",
    ),
    (
        "custom screen has no VNDS equivalent",
        "manual",
        "screen",
        "Custom screens have no VNDS equivalent and need a native reimplementation (VN3DS-spec.md §6).",
        "Reimplement this screen's UI natively; it won't auto-convert.",
    ),
    (
        "persistent/achievement API has no VNDS equivalent",
        "manual",
        "python",
        "persistent.*/achievement.* have no VNDS equivalent and need a native reimplementation (VN3DS-spec.md §6).",
        "Reimplement this persistent-state or achievement effect natively; it won't auto-convert.",
    ),
    (
        "list mutation has no VNDS list-variable equivalent",
        "manual",
        "python",
        "VNDS variables are int/bool/string only (§6.1); this list-backed feature (e.g. a clue/notes journal) needs a native reimplementation.",
        "Reimplement this feature (e.g. a native notebook/journal screen) rather than tracking it as a VNDS variable.",
    ),
    (
        "list/dict-valued assignment has no VNDS equivalent",
        "manual",
        "python",
        "VNDS variables are int/bool/string only (§6.1); this is data for a feature that already needs native reimplementation, not a bug on its own.",
        "Carry this data over when reimplementing the feature it belongs to.",
    ),
    (
        "init python block has no VNDS equivalent",
        "manual",
        "python",
        "init python blocks are most commonly gallery/music-room extras or desktop window config that's irrelevant on 3DS.",
        "Review the block's contents; reimplement natively if it matters, otherwise safe to ignore.",
    ),
    (
        "python block has no VNDS equivalent",
        "manual",
        "python",
        "A python: block mid-scene runs arbitrary game logic (e.g. stat-tracking helper calls) that has no VNDS equivalent.",
        "Review the block's contents; reimplement natively if it matters, otherwise safe to ignore.",
    ),
    (
        "translate block is localization data",
        "info",
        "flow",
        "translate blocks hold a per-language translation (strings or a fully-translated label) -- irrelevant to a single-language port.",
        "",
    ),
    (
        "unknown text tag ",
        "approximated",
        "text-tag",
        "This inline text tag isn't in the supported set ({b}{i}{color}{w}{p}{size}{alt}{noalt}), so it was stripped from the dialogue.",
        "Reimplement this tag's effect manually if it matters for this line.",
    ),
    (
        "unsupported text tag ",
        "approximated",
        "text-tag",
        "{size}/{font} are recognized but have no per-run font-size/font-file support (only one font, one size, ever extracted), so the tag was stripped and its text shown at the normal size/font.",
        "Reimplement this tag's effect manually if the size/font change matters for this line.",
    ),
    (
        "transition '",
        "approximated",
        "atl",
        "This transition isn't dissolve/fade (the only two with a known duration), so it was downgraded to a plain dissolve.",
        "Review the transition; reimplement a closer match manually if the fidelity loss matters.",
    ),
    (
        "queue approximated as an immediate play",
        "approximated",
        "audio",
        "`queue` was converted to an immediate `play`; the engine doesn't support chaining a track after the current one yet.",
        "Review audio timing at this point; the queued track now interrupts rather than following.",
    ),
    (
        "custom audio channel not in the converter's known/verified set",
        "info",
        "audio",
        "A custom audio channel (renpy.music.register_channel), not one of the converter's curated set -- it still plays, but its loop/mixer behavior was guessed from the channel's name.",
        "Verify against the original game's renpy.music.register_channel call; add it to vnds_writer.py's _CUSTOM_CHANNEL_SHAPE if the guess is wrong.",
    ),
    (
        "bare pause has no effect",
        "info",
        "flow",
        "A bare `pause` (no duration) already matches VNDS's default wait-for-input behavior after every text line.",
        "",
    ),
    (
        "DynamicCharacter approximated with its current default display name",
        "approximated",
        "displayable",
        "DynamicCharacter's name can change at runtime; converted using its current default value as a static nameplate.",
        "Review whether this character is ever renamed during play; if so, the nameplate won't update.",
    ),
    (
        "DynamicCharacter's name variable could not be resolved to a literal string",
        "blocking",
        "python",
        "DynamicCharacter()'s name variable isn't a literal string defined elsewhere in the script.",
        "Give the referenced variable a literal string define, or hardcode a display name.",
    ),
    (
        "image declaration is not a plain file path",
        "manual",
        "asset",
        "This image is a dynamic displayable (ATL effect, Python call), not a plain file path, so it can't be resolved automatically.",
        "Manually assign a static asset for this image tag, or reimplement the effect.",
    ),
    (
        "malformed image statement",
        "blocking",
        "asset",
        "This 'image' statement doesn't match the supported 'image tag = \"path\"' form.",
        "Rewrite as 'image tag = \"path\"', or port this declaration manually.",
    ),
    (
        "could not parse image declaration",
        "blocking",
        "asset",
        "This image declaration's right-hand side couldn't be parsed as a Python expression.",
        "Simplify the image declaration's expression.",
    ),
    (
        "scene position has no VNDS equivalent",
        "approximated",
        "asset",
        "Scene position was ignored; VNDS backgrounds are always full-screen.",
        "Review the converted background placement; reposition sprites manually if needed.",
    ),
    (
        "scene ATL position has no VNDS equivalent",
        "approximated",
        "atl",
        "Scene ATL positioning was ignored; VNDS backgrounds are always full-screen.",
        "Review the converted background placement; reposition sprites manually if needed.",
    ),
    (
        "ATL animation/zoom/alpha approximated to its final static",
        "approximated",
        "atl",
        "This sprite's ATL block used a timed tween and/or zoom/alpha (no VNDS equivalent); only its final xalign/yalign position was kept.",
        "Reimplement the animation natively if the motion/zoom/fade matters for this moment.",
    ),
    (
        "ATL block has no recognizable static/final position",
        "blocking",
        "atl",
        "This ATL block doesn't set xalign/yalign, so there's no position to fall back to.",
        "Add an explicit xalign/yalign, or reimplement this ATL block manually.",
    ),
    (
        "ATL animation approximated to a generic keyframe sequence",
        "approximated",
        "atl",
        "This ATL block was converted to a working anim_begin/keyframe/anim_end sequence, but didn't match any named preset exactly (position, zoom, rotation, or a multi-step chain).",
        "Play it back and tune the keyframes if the motion doesn't look right; the animation itself is real, not dropped.",
    ),
    (
        "custom screen uses constructs outside the supported subset",
        "manual",
        "screen",
        "This screen: block uses something outside the pulled-forward custom-screen runtime's supported subset (vbox/hbox, text, textbutton, if/elif/else) — a for loop, a composite action list, an unrecognized action, or inline Python.",
        "Reimplement this screen natively, or simplify it to the supported subset.",
    ),
    (
        "imagemap hotspot uses an unsupported action, this hotspot dropped",
        "approximated",
        "screen",
        "This one hotspot's action (e.g. a dynamic/passed-in action, SetScreenVariable, OpenURL, or an arbitrary Python callback) has no VNDS equivalent, so just this hotspot was dropped — the rest of the imagemap (including its other hotspots) still converts and works.",
        "Add this hotspot's behavior manually if it matters; every other hotspot on the same imagemap is unaffected.",
    ),
    (
        "unrecognized menu choice syntax",
        "blocking",
        "flow",
        "This menu choice uses syntax the converter cannot parse (e.g. a conditional 'if' clause).",
        "Simplify the choice to a plain quoted string, or wait for conditional-choice support.",
    ),
    (
        "Character() missing a string display name",
        "blocking",
        "python",
        "Character() must be given a literal string name; dynamic/None names aren't supported.",
        "Give this Character() a literal string display name.",
    ),
    (
        "define is not a Character() call",
        "blocking",
        "python",
        "This 'define' statement isn't a Character() definition; general Python expressions aren't converted.",
        "Only Character() definitions are supported for 'define' right now; port other defines manually.",
    ),
    (
        "could not parse Character() arguments",
        "blocking",
        "python",
        "The Character() call's arguments couldn't be parsed as a Python expression.",
        "Simplify the Character() call's arguments.",
    ),
    (
        "malformed define statement",
        "blocking",
        "python",
        "This 'define' statement doesn't match the supported 'define name = Character(...)' form.",
        "Rewrite as 'define name = Character(...)', or port this value manually.",
    ),
    (
        "title-card visual style approximated",
        "approximated",
        "screen",
        "The `day` custom statement's title card converts to positioned overlay text over a background, not the PC version's exact per-layer dissolve choreography/font.",
        "Review the title card on-device; adjust overlay_text positions/sizes in the emitter if it doesn't read well.",
    ),
    (
        "chapter-heading backing image not reproduced",
        "approximated",
        "screen",
        "The `subchapter` custom statement's decorative backing image isn't reproduced -- the heading text itself still shows, positioned/colored/sized to match.",
        "Add a real backing image asset manually if the decorative box matters.",
    ),
    (
        "end-card visual style approximated",
        "approximated",
        "screen",
        "The `the_end` custom statement's title card converts to positioned overlay text over a background, not the PC version's exact font/dissolve choreography.",
        "Review the end card on-device; adjust overlay_text positions/sizes in the emitter if it doesn't read well.",
    ),
    (
        "renpy.rollback() has no VNDS equivalent",
        "approximated",
        "flow",
        "The `placeholder` custom statement's message shows, but VNDS has no rollback/undo mechanism, so the script continues linearly instead of dead-ending this path.",
        "Reimplement a real dead-end (e.g. a jump back to a safe point) if this path is ever actually reachable.",
    ),
    (
        "CharacterImage layer_selector for '",
        "approximated",
        "displayable",
        "This CharacterImage character's layer_selector uses a construct outside the interpreter's supported subset for this specific attribute combination, so it fell back to the character's default (no-attribute) pose instead of the real per-attribute layers.",
        "Extend the interpreter subset (src/converter/parser/character_image.py) if this combination needs to render correctly, or adjust the source selector.",
    ),
    (
        "CharacterImage layer '",
        "approximated",
        "displayable",
        "One of this CharacterImage character's yielded layer names has no matching per-character asset file (e.g. it refers to an ordinary top-level image, not a per-character layer), so that one layer is missing from the composite -- every other resolved layer still renders.",
        "Check whether this layer name should resolve as a plain declared image instead of a per-character asset.",
    ),
    (
        "unsupported top-level statement",
        "blocking",
        "unknown",
        "This statement is outside the currently supported Ren'Py subset.",
        "Reimplement this construct manually, or wait for future converter support.",
    ),
    (
        "unsupported statement",
        "blocking",
        "unknown",
        "This statement is outside the currently supported Ren'Py subset.",
        "Reimplement this construct manually, or wait for future converter support.",
    ),
]

# Keyword sniffing for the generic "unsupported statement" rules, so at
# least common constructs (screens, python blocks, conditionals) land in a
# more useful category than "unknown".
_KEYWORD_CATEGORY: list[tuple[str, Category]] = [
    ("screen ", "screen"),
    ("screen(", "screen"),
    ("init python", "python"),
    ("python:", "python"),
    ("$ ", "python"),
    ("if ", "flow"),
    ("elif ", "flow"),
    ("else:", "flow"),
    ("transform ", "atl"),
    ("with ", "atl"),
    ("play ", "audio"),
    ("stop ", "audio"),
    ("queue ", "audio"),
    ("movie", "video"),
    ("renpy.", "python"),
]


def _sniff_category(text: str) -> Category:
    stripped = text.strip()
    for keyword, category in _KEYWORD_CATEGORY:
        if stripped.startswith(keyword):
            return category
    return "unknown"


def classify(item: FlaggedItem) -> Problem:
    for prefix, severity, category, message, suggestion in _RULES:
        if item.reason.startswith(prefix):
            if category == "unknown":
                category = _sniff_category(item.text)
            return Problem(
                id=item.id,
                severity=severity,
                category=category,
                source=str(item.loc),
                ren_py=_truncate(item.text),
                message=message,
                suggestion=suggestion,
            )
    # No rule matched (a new/unexpected reason string) — default to blocking
    # rather than silently under-reporting a real gap.
    return Problem(
        id=item.id,
        severity="blocking",
        category=_sniff_category(item.text),
        source=str(item.loc),
        ren_py=_truncate(item.text),
        message=item.reason,
        suggestion="Reimplement this construct manually.",
    )
