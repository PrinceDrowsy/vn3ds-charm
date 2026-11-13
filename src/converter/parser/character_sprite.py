"""Parses Ren'Py's `ChangePortrait`/`CharacterSprite`/`Portrait` custom
displayable system (a hand-written, imperative multi-layer character
portrait -- confirmed real content: Our Life: Beginnings & Always'
`portrait.rpy`/`character_sprite.rpy`/`character_definitions.rpy`,
~60 independently-swappable named layers, live per-frame blink/lip-flap
animation, a manual cross-fade dissolve on layer change, and pulsing
"glow"/"magic" special layers).

Architecturally distinct from `character_image.py`'s `CharacterImage`:
that system is a *declarative*, semi-static Ren'Py built-in (an
attribute-set -> layer-list function, resolved once per `show <tag>
<attrs>` at convert time). `ChangePortrait` is fully imperative --
`$ ChangePortrait(chara, base=.., eyes=.., **kwargs)` directly assigns
named slot values one call at a time, with no selector function to
interpret at all. That makes the *static* half of this module simpler
than CharacterImage's (no constrained-Python-subset interpreter needed --
each kwarg's value is already the literal slot value), but the *runtime*
half needs real new engine primitives CharacterImage never did: blink/
lip-flap frame-cycling, a cross-fade dissolve, and glow/magic pulsing
opacity, none of which exist in the engine before this module -- see
`src/engine/portrait.moon`.

Everything in *this* file runs at convert time only, same as
character_image.py: each `$ ChangePortrait(...)` call resolves to a
`PortraitUpdate` IR node (one entry per kwarg actually passed -- matching
`SetSpritePart`'s real incremental semantics, where an untouched slot
keeps whatever the engine already has drawn from a prior call). The
engine only ever receives already-resolved slot/path/category data; it
never evaluates any Ren'Py expression itself.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from .ir import SourceLocation
from .lexer import tokenize_lines


@dataclass
class PortraitDef:
    """One `image TAG = Portrait(name=..., ...)` declaration. `name` (not
    `tag`) is what `$ ChangePortrait(chara, ...)` calls actually reference
    -- Ren'Py's own `Portrait.__init__` only seeds a character's real
    animateMouth/speaker/dimensions into `characterSprites[name]` the
    first time that Portrait displayable is actually shown, so those
    fields are resolved here per declaration and threaded onto whichever
    `PortraitUpdate`s reference the same `name` string, not re-derived at
    runtime."""

    tag: str
    name: str
    speaker: str | None
    animate_eyes: bool
    animate_mouth: bool
    width: int
    height: int
    loc: SourceLocation


@dataclass
class SpriteLayerCategories:
    """Game-wide slot metadata from `character_definitions.rpy`-style
    constant lists -- generic by variable name (`characterSpritePartsOrder`
    /`characterSpriteExpressions`/`characterSpriteGlowing`/
    `characterSpriteMagic`), not hardcoded to any one game, though the
    `ChangePortrait(chara, blink=True, transition=True, **kwargs)` call
    signature itself is matched by exact name (same precedent as
    `CharacterImage` being matched by exact name in character_image.py)."""

    parts_order: tuple[str, ...] = field(default_factory=tuple)
    expressions: frozenset[str] = frozenset()
    glowing: frozenset[str] = frozenset()
    magic: frozenset[str] = frozenset()

    def order_index(self, slot: str) -> int:
        """Slots outside the declared order (shouldn't happen in real
        content, but real-world .rpy files are never fully trusted) sort
        after every known slot, in first-seen order amongst themselves --
        keeps output deterministic rather than crashing."""
        try:
            return self.parts_order.index(slot)
        except ValueError:
            return len(self.parts_order) + hash(slot) % 1000


@dataclass
class PortraitLayerUpdate:
    """One resolved slot update from a single `$ ChangePortrait(...)` call
    -- one of these per kwarg actually passed (the real, incremental
    `SetSpritePart` semantics: untouched slots keep whatever the engine
    already has drawn from a prior call for this `name`)."""

    slot: str
    value: str
    order_index: int
    category: str  # "eyes" | "mouth" | "glow" | "magic" | "expression" | "plain"
    is_expression_folder: bool  # True -> "<folder>/Expressions/<value>.png", else "<folder>/<value>.png"


@dataclass
class PortraitUpdateCall:
    """A single resolved `$ ChangePortrait(...)` call site -- everything
    the emitter needs to turn it into real VNDS `portrait` instructions
    (see vnds_writer.py/PortraitUpdate IR node), with no further Ren'Py
    interpretation required."""

    name: str  # the `chara` argument -- key into the engine's own per-name sprite state
    blink: bool
    transition: bool
    updates: tuple[PortraitLayerUpdate, ...]
    tint: tuple[float, float, float] | None
    loc: SourceLocation


_LIST_ASSIGN_RE_TEMPLATE = r"^[ \t]*(?:default|define)\s+{name}\s*=\s*"


def _scan_bracketed_list(source: str, name: str) -> tuple[str, ...] | None:
    """Finds `default NAME = [...]` / `define NAME = [...]` anywhere in
    `source` (module-level constants, not nested in a block -- these are
    ordinary top-level Ren'Py statements, confirmed real content spans
    many source lines with one element per line) and parses the bracketed
    literal as real Python, tracking bracket depth across lines (a plain
    per-line regex can't see the closing `]`, which is often many lines
    later)."""
    match = re.search(_LIST_ASSIGN_RE_TEMPLATE.format(name=re.escape(name)), source, re.MULTILINE)
    if match is None:
        return None
    start = match.end()
    if start >= len(source) or source[start] != "[":
        return None
    depth = 0
    end = start
    for i in range(start, len(source)):
        if source[i] == "[":
            depth += 1
        elif source[i] == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    else:
        return None
    try:
        tree = ast.parse(source[start:end], mode="eval")
    except SyntaxError:
        return None
    if not isinstance(tree.body, ast.List):
        return None
    values: list[str] = []
    for elt in tree.body.elts:
        if not (isinstance(elt, ast.Constant) and isinstance(elt.value, str)):
            return None
        values.append(elt.value)
    return tuple(values)


def scan_sprite_layer_categories(source: str) -> SpriteLayerCategories:
    """Game-wide prepass (like `scan_transform_declarations`/
    `scan_string_defines`) -- merges across every file the same way, since
    these constants can live in a different file than the `Portrait`/
    `ChangePortrait` usages that depend on them."""
    # `characterSpritePartsOrder` itself is commonly just `= characterSpritePartsOrder_const`
    # (a bare name reference, not a literal list -- confirmed real content)
    # -- the real literal list lives under the `_const` name, tried first.
    parts_order = _scan_bracketed_list(source, "characterSpritePartsOrder_const") or _scan_bracketed_list(
        source, "characterSpritePartsOrder"
    )
    expressions = _scan_bracketed_list(source, "characterSpriteExpressions")
    glowing = _scan_bracketed_list(source, "characterSpriteGlowing")
    magic = _scan_bracketed_list(source, "characterSpriteMagic")
    return SpriteLayerCategories(
        parts_order=parts_order or (),
        expressions=frozenset(expressions or ()),
        glowing=frozenset(glowing or ()),
        magic=frozenset(magic or ()),
    )


def merge_sprite_layer_categories(a: SpriteLayerCategories, b: SpriteLayerCategories) -> SpriteLayerCategories:
    """First-non-empty-wins merge for `parts_order` (a game only ever
    declares this once for real; whichever file's prepass saw it first
    keeps it), set-union for the three category sets (each real game seen
    so far declares these once too, but a union is harmless and correct
    if a hypothetical game split them across files)."""
    return SpriteLayerCategories(
        parts_order=a.parts_order or b.parts_order,
        expressions=a.expressions | b.expressions,
        glowing=a.glowing | b.glowing,
        magic=a.magic | b.magic,
    )


_PORTRAIT_RE = re.compile(r"^image\s+(\w+)\s*=\s*Portrait\((.*)\)\s*$")


def _const_str(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _const_bool(node: ast.expr | None, default: bool) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    return default


def _const_int(node: ast.expr | None, default: int) -> int:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return int(node.value)
    return default


def parse_portrait_declarations(source: str, filename: str = "<string>") -> dict[str, PortraitDef]:
    """Scans one file for `image TAG = Portrait(...)` declarations,
    keyed by `name` (what `$ ChangePortrait(chara, ...)` calls actually
    reference), not `tag` -- confirmed real content: Our Life's `name=`
    values (e.g. "Cove_8") never collide across declarations, since each
    is a distinct character/pose/crop variant."""
    defs: dict[str, PortraitDef] = {}
    for line in tokenize_lines(source):
        match = _PORTRAIT_RE.match(line.text)
        if not match:
            continue
        tag, args_text = match.groups()
        try:
            tree = ast.parse(f"f({args_text})", mode="eval")
        except SyntaxError:
            continue
        call = tree.body
        if not isinstance(call, ast.Call):
            continue
        kwargs = {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}
        name = _const_str(kwargs.get("name"))
        if name is None:
            continue
        defs[name] = PortraitDef(
            tag=tag,
            name=name,
            speaker=_const_str(kwargs.get("speaker")),
            animate_eyes=_const_bool(kwargs.get("animateEyes"), False),
            animate_mouth=_const_bool(kwargs.get("animateMouth"), False),
            width=_const_int(kwargs.get("width"), 300),
            height=_const_int(kwargs.get("height"), 600),
            loc=SourceLocation(filename, line.lineno),
        )
    return defs


def _resolve_tint(node: ast.expr) -> tuple[float, float, float] | None:
    """A `matrix=` kwarg is a Ren'Py color-matrix expression, usually a
    `*`-chain of `im.matrix.saturation(...)`/`im.matrix.tint(r,g,b)`/
    `im.matrix.brightness(...)` (confirmed real content). The engine has
    no true color-matrix primitive (only a plain per-sprite RGB multiply,
    the same `tint_r/g/b` mechanism CharacterImage's `lighting_night`
    approximation already uses) -- so this pulls out just the
    `im.matrix.tint(r, g, b)` factor from anywhere in the chain, if
    present, and ignores saturation/brightness entirely (no engine
    equivalent). Returns None if the expression contains no recognizable
    `im.matrix.tint(...)` call, in which case the caller applies no tint
    at all (a real, if approximated, no-op rather than a crash)."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return _resolve_tint(node.left) or _resolve_tint(node.right)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "tint"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "matrix"
        and len(node.args) == 3
    ):
        values = []
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)):
                values.append(float(arg.value))
            elif isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub) and isinstance(arg.operand, ast.Constant):
                values.append(-float(arg.operand.value))
            else:
                return None
        return values[0], values[1], values[2]
    return None


def _categorize_slot(slot: str, categories: SpriteLayerCategories) -> tuple[str, bool]:
    if slot == "eyes":
        return "eyes", True
    if slot == "mouth":
        return "mouth", True
    if slot in categories.glowing:
        return "glow", slot in categories.expressions
    if slot in categories.magic:
        return "magic", slot in categories.expressions
    if slot in categories.expressions:
        return "expression", True
    return "plain", False


_CHANGE_PORTRAIT_RE = re.compile(r"^\$\s*ChangePortrait\((.*)\)\s*$")
_NON_LAYER_KWARGS = {"chara", "blink", "transition", "matrix"}


def parse_change_portrait_call(
    text: str, categories: SpriteLayerCategories, loc: SourceLocation
) -> PortraitUpdateCall | None:
    """Resolves one `$ ChangePortrait(chara, blink=.., transition=..,
    matrix=.., **kwargs)` statement into a `PortraitUpdateCall` -- unlike
    CharacterImage's `layer_selector`, there's no function body to
    interpret at all: every kwarg's value is already the literal slot
    value (or, for `blink`/`transition`/`matrix`, a call-level flag/tint).
    Returns None for anything this can't resolve (a non-literal `chara`
    or slot value, an unparseable call) -- the caller falls back to the
    generic unsupported-statement classification, same as any other
    unresolvable construct in this converter."""
    match = _CHANGE_PORTRAIT_RE.match(text)
    if not match:
        return None
    try:
        tree = ast.parse(f"f({match.group(1)})", mode="eval")
    except SyntaxError:
        return None
    call = tree.body
    if not isinstance(call, ast.Call):
        return None
    chara_node = call.args[0] if call.args else None
    kwargs = {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}
    if chara_node is None:
        chara_node = kwargs.get("chara")
    name = _const_str(chara_node)
    if name is None:
        return None
    blink = _const_bool(kwargs.get("blink"), True)
    transition = _const_bool(kwargs.get("transition"), True)
    tint = _resolve_tint(kwargs["matrix"]) if "matrix" in kwargs else None

    updates: list[PortraitLayerUpdate] = []
    for slot, value_node in kwargs.items():
        if slot in _NON_LAYER_KWARGS:
            continue
        value = _const_str(value_node)
        if value is None:
            return None  # a non-literal slot value (unsupported) -- bail the whole call, not just this slot
        category, is_expr_folder = _categorize_slot(slot, categories)
        updates.append(
            PortraitLayerUpdate(
                slot=slot,
                value=value,
                order_index=categories.order_index(slot),
                category=category,
                is_expression_folder=is_expr_folder,
            )
        )
    updates.sort(key=lambda u: u.order_index)
    return PortraitUpdateCall(name=name, blink=blink, transition=transition, updates=tuple(updates), tint=tint, loc=loc)
