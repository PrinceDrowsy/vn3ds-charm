"""Parses Ren'Py's `CharacterImage(...)` custom displayable (a hand-written
dynamic, attribute-driven multi-layer character sprite system -- confirmed
real content: `characterimage.rpy`, ~270 lines, implementing alias/conflict-
aware layer selection driven by whichever attribute *words* follow a
`show <tag> <attrs>`) and provides a constrained Python-subset interpreter
for each character's own `layer_selector` function, resolving which named
layers apply to a given attribute combination.

Everything here runs at *convert time* only. A `show <tag> <attrs>`
resolves to an ordered list of real layer files + positions, emitted as an
ordinary `clearslot`/`setimg` sequence (see vnds_writer.py) -- the O3DS
engine never runs any of this, just draws already-resolved sprites, same
cost as any other foreground layer.
"""
from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path

from .ir import SourceLocation
from .lexer import tokenize_lines


@dataclass
class CharacterImageDef:
    tag: str
    character_name: str
    layers: tuple[str, ...]  # in declared order -- draw order, and wildcard-pattern source
    attribute_sets: tuple[frozenset[str], ...]
    aliases: dict[str, frozenset[str]]
    selector: ast.FunctionDef
    loc: SourceLocation
    # Module-level constant lists the selector references directly by name
    # (e.g. `if a in AFD_L_EYES:`) rather than through its own `attr`
    # parameter -- confirmed real content, not hypothetical.
    module_lists: dict[str, frozenset[str]]
    # Other top-level helper functions declared alongside the selector in
    # the same `init python:` block(s) (e.g. `margaret_get_arms_file`,
    # `julie_get_arms_file`) -- confirmed real, common content: many
    # characters factor out "compute this variant's file name" as its own
    # plain value-returning function, called from within the main
    # selector rather than inlined.
    module_functions: dict[str, ast.FunctionDef]


class InterpreterBailout(Exception):
    """A `layer_selector` body uses a construct outside the supported
    subset -- caught by the caller, which falls back to a `manual` flag
    for *this character only* (a real technical boundary, not a
    shortcut -- other, simpler characters must not be blocked by one
    complex one)."""


class _Return(Exception):
    def __init__(self, value: object = None):
        super().__init__()
        self.value = value


class _Continue(Exception):
    pass


def _truthy(value: object) -> bool:
    if isinstance(value, (frozenset, set)):
        return len(value) > 0
    return bool(value)


class _LayerSelectorInterpreter:
    """Executes a `layer_selector(ci, attr)` function body over a concrete
    `attr` frozenset, collecting `yield`ed layer names. Supports: `if`/
    `elif`/`else`; `and`/`or`/`not`; `in`/`not in`/`==`/`!=`; set literals,
    `&` intersection, `+` union; local variable assignment; string `+`
    concatenation and `.replace()`/`.split()`; indexing; `len()`; `for x in
    <iterable>:` loops; `yield <expr>`; bare `return` (early exit); and
    `persistent.X` reads (resolved via the injected `persistent_resolver`
    callback, so the caller can run this twice -- once assuming every
    persistent read is True, once False -- to detect whether a given
    attribute combination's result actually depends on one, without a full
    symbolic executor)."""

    def __init__(
        self,
        attr: frozenset[str],
        attr_param_name: str,
        persistent_resolver,
        module_lists: dict[str, frozenset[str]] | None = None,
        loadable_checker=None,
        module_functions: dict[str, ast.FunctionDef] | None = None,
    ):
        self.attr = attr
        self.attr_param_name = attr_param_name
        self.persistent_resolver = persistent_resolver
        # module-level constant lists a selector references directly by
        # name (e.g. `if a in AFD_L_EYES:`) rather than through its own
        # `attr` parameter -- confirmed real content, not a hypothetical.
        self.module_lists = module_lists or {}
        # Other helper functions declared alongside the selector (e.g.
        # margaret_get_arms_file) -- called for their *return value* via
        # `_call_function`, a separate execution mode from the main
        # selector's own yield-collecting `run()`.
        self.module_functions = module_functions or {}
        # `renpy.loadable(path)` -- a real filesystem-existence check
        # (confirmed real content: margaret's selector picks between
        # alternate file variants this way) -- defaults to "nothing
        # exists" when the caller doesn't have a real assets_dir to check
        # against, which just means those alternate-variant branches never
        # get picked (a safe, conservative fallback, not a crash).
        self.loadable_checker = loadable_checker or (lambda _path: False)
        self.persistent_names_seen: set[str] = set()
        self.locals: dict[str, object] = {}
        self.yields: list[str] = []

    def run(self, func: ast.FunctionDef) -> list[str]:
        self.locals = {}
        self.yields = []
        try:
            self._exec_body(func.body)
        except _Return:
            pass
        return self.yields

    def _exec_body(self, body: list[ast.stmt]) -> None:
        for stmt in body:
            self._exec_stmt(stmt)

    def _exec_stmt(self, stmt: ast.stmt) -> None:
        if isinstance(stmt, ast.Expr):
            if isinstance(stmt.value, ast.Call):
                # A bare side-effect call whose result is never used --
                # confirmed real content is exclusively analytics/unlock-
                # tracking bookkeeping here (e.g.
                # `persistent.cv_npcs.add('afd_l')`,
                # `check_npc_unlock_progress()`, or a call to another
                # locally-defined helper that itself only does the same --
                # see margaret_check_for_unlock), never anything that
                # affects which layers get yielded. Safely skipped rather
                # than bailing the whole character over an unrelated call
                # this interpreter was never meant to execute.
                return
            self._eval(stmt.value)
            return
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                raise InterpreterBailout("unsupported assignment target")
            self.locals[stmt.targets[0].id] = self._eval(stmt.value)
            return
        if isinstance(stmt, ast.If):
            if _truthy(self._eval(stmt.test)):
                self._exec_body(stmt.body)
            else:
                self._exec_body(stmt.orelse)
            return
        if isinstance(stmt, ast.For):
            if not isinstance(stmt.target, ast.Name):
                raise InterpreterBailout("unsupported for-loop target")
            name = stmt.target.id
            for item in self._eval(stmt.iter):
                self.locals[name] = item
                try:
                    self._exec_body(stmt.body)
                except _Continue:
                    continue
            return
        if isinstance(stmt, ast.Return):
            value = self._eval(stmt.value) if stmt.value is not None else None
            raise _Return(value)
        if isinstance(stmt, ast.Continue):
            raise _Continue()
        if isinstance(stmt, ast.Pass):
            return
        raise InterpreterBailout(f"unsupported statement: {type(stmt).__name__}")

    def _call_function(self, func: ast.FunctionDef, args: list) -> object:
        """Calls a locally-defined helper (e.g. margaret_get_arms_file) for
        its *return value* -- a separate mode from `run()`'s yield
        collection for the main selector. Confirmed real content: several
        characters factor out "compute this variant's file name" as its
        own plain function, called from within the main selector. Runs
        with a fresh local scope bound to the callee's own positional
        params (shadowing the caller's locals for the duration of the
        call, then restored) -- `persistent_names_seen`/`loadable_checker`/
        `module_lists`/`yields` stay shared via `self`, so a helper
        touching `persistent.X` or `renpy.loadable(...)` is tracked and
        resolved exactly the same as if the main selector had done it
        directly."""
        params = [a.arg for a in func.args.args]
        if len(params) != len(args):
            raise InterpreterBailout(f"argument count mismatch calling {func.name}(...)")
        saved_locals = self.locals
        self.locals = dict(zip(params, args))
        try:
            self._exec_body(func.body)
            return None
        except _Return as ret:
            return ret.value
        finally:
            self.locals = saved_locals

    def _eval(self, node: ast.expr):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in self.locals:
                return self.locals[node.id]
            if node.id == self.attr_param_name:
                return self.attr
            if node.id in self.module_lists:
                return self.module_lists[node.id]
            raise InterpreterBailout(f"unresolved name: {node.id}")
        if isinstance(node, ast.Yield):
            value = self._eval(node.value) if node.value is not None else None
            if not isinstance(value, str):
                raise InterpreterBailout("yield of a non-string value")
            self.yields.append(value)
            return None
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not _truthy(self._eval(node.operand))
        if isinstance(node, ast.BoolOp):
            values = [self._eval(v) for v in node.values]
            is_and = isinstance(node.op, ast.And)
            result = values[0]
            for v in values[1:]:
                if is_and != _truthy(result):
                    return result
                result = v
            return result
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise InterpreterBailout("chained comparisons not supported")
            left = self._eval(node.left)
            right = self._eval(node.comparators[0])
            op = node.ops[0]
            if isinstance(op, ast.In):
                return left in right
            if isinstance(op, ast.NotIn):
                return left not in right
            if isinstance(op, ast.Eq):
                return left == right
            if isinstance(op, ast.NotEq):
                return left != right
            # Numeric comparisons -- confirmed real content: margaret's
            # selector checks `len(parts) > 1` after a `.split("_")` to
            # decide whether a direction suffix carries an extra
            # "talking" segment.
            if isinstance(op, ast.Gt):
                return left > right
            if isinstance(op, ast.Lt):
                return left < right
            if isinstance(op, ast.GtE):
                return left >= right
            if isinstance(op, ast.LtE):
                return left <= right
            raise InterpreterBailout("unsupported comparison operator")
        if isinstance(node, ast.BinOp):
            left = self._eval(node.left)
            right = self._eval(node.right)
            if isinstance(node.op, ast.Add):
                if isinstance(left, str) and isinstance(right, str):
                    return left + right
                if isinstance(left, (frozenset, set)) and isinstance(right, (frozenset, set)):
                    return frozenset(left) | frozenset(right)
                raise InterpreterBailout("unsupported '+' operand types")
            if isinstance(node.op, ast.BitAnd):
                return frozenset(left) & frozenset(right)
            raise InterpreterBailout("unsupported binary operator")
        if isinstance(node, ast.Set):
            return frozenset(self._eval(e) for e in node.elts)
        if isinstance(node, ast.Call):
            return self._eval_call(node)
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "persistent":
                self.persistent_names_seen.add(node.attr)
                return self.persistent_resolver(node.attr)
            raise InterpreterBailout(f"unsupported attribute access: .{node.attr}")
        if isinstance(node, ast.Subscript):
            value = self._eval(node.value)
            if isinstance(node.slice, ast.Slice):
                raise InterpreterBailout("slice subscripts not supported")
            index = self._eval(node.slice)
            return value[index]
        raise InterpreterBailout(f"unsupported expression: {type(node).__name__}")

    def _eval_call(self, node: ast.Call):
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "renpy"
            and node.func.attr == "loadable"
        ):
            # a real filesystem-existence check (confirmed real content:
            # margaret's selector picks between alternate file variants
            # this way, e.g. `renpy.loadable("characters/margaret/" +
            # arms_file + " mouse.png")`) -- resolved against the actual
            # extracted asset directory via the injected callback, not
            # evaluated as a generic attribute/call (renpy.* isn't a real
            # name in this interpreter's world at all otherwise).
            args = [self._eval(a) for a in node.args]
            if len(args) != 1 or not isinstance(args[0], str):
                raise InterpreterBailout("unsupported renpy.loadable(...) argument")
            return self.loadable_checker(args[0])
        if isinstance(node.func, ast.Attribute):
            obj = self._eval(node.func.value)
            method = node.func.attr
            args = [self._eval(a) for a in node.args]
            if isinstance(obj, str):
                if method == "replace" and len(args) == 2:
                    return obj.replace(args[0], args[1])
                if method == "split" and len(args) <= 1:
                    return obj.split(*args)
                if method == "lower" and len(args) == 0:
                    return obj.lower()
                if method == "upper" and len(args) == 0:
                    return obj.upper()
            if isinstance(obj, (frozenset, set)):
                if method == "intersection" and len(args) == 1:
                    return frozenset(obj) & frozenset(args[0])
                if method == "union" and len(args) == 1:
                    return frozenset(obj) | frozenset(args[0])
            raise InterpreterBailout(f"unsupported method call: .{method}(...)")
        if isinstance(node.func, ast.Name):
            args = [self._eval(a) for a in node.args]
            if node.func.id == "len" and len(args) == 1:
                return len(args[0])
            if node.func.id in ("set", "Set"):
                return frozenset(args[0]) if args else frozenset()
            if node.func.id in self.module_functions:
                return self._call_function(self.module_functions[node.func.id], args)
            raise InterpreterBailout(f"unsupported function call: {node.func.id}(...)")
        raise InterpreterBailout("unsupported call shape")


def _make_loadable_checker(assets_dir: Path | None):
    if assets_dir is None:
        return None

    def checker(path: str) -> bool:
        return (assets_dir / path).is_file()

    return checker


def resolve_layers(
    char_def: CharacterImageDef, attrs: frozenset[str], assets_dir: Path | None = None
) -> tuple[list[str], str | None]:
    """Runs the interpreter over `char_def.selector` for a concrete
    attribute set, returning (yielded_layer_names, gating_persistent_name).
    `gating_persistent_name` is None when the result doesn't depend on any
    `persistent.X` read for this attribute combination -- otherwise it's
    the single persistent attribute name gating it (the emitter re-runs
    `resolve_layers_with_persistent` for both True/False to get each
    variant's own layer list). Detects gating by running the interpreter
    twice -- once with every `persistent.X` read resolved True, once
    False -- and comparing results (a much simpler stand-in for a full
    symbolic executor, correct for the dominant real shape: a single
    persistent flag toggling part of the output). Raises
    InterpreterBailout if either run hits an unsupported construct, or if
    2+ *distinct* persistent names were read while the two results differ
    (a multi-flag branch is outside this pass's scope). `assets_dir`, when
    given, backs `renpy.loadable(...)` checks with the real extracted
    asset tree."""
    attr_param_name = char_def.selector.args.args[1].arg
    loadable_checker = _make_loadable_checker(assets_dir)

    interp_true = _LayerSelectorInterpreter(
        attrs, attr_param_name, lambda _n: True, char_def.module_lists, loadable_checker, char_def.module_functions
    )
    result_true = interp_true.run(char_def.selector)
    interp_false = _LayerSelectorInterpreter(
        attrs, attr_param_name, lambda _n: False, char_def.module_lists, loadable_checker, char_def.module_functions
    )
    result_false = interp_false.run(char_def.selector)

    if result_true == result_false:
        return result_true, None

    names_seen = interp_true.persistent_names_seen | interp_false.persistent_names_seen
    if len(names_seen) != 1:
        raise InterpreterBailout("result depends on 2+ persistent flags (unsupported)")
    (persistent_name,) = names_seen
    return result_true, persistent_name


def resolve_layers_with_persistent(
    char_def: CharacterImageDef, attrs: frozenset[str], persistent_value: bool, assets_dir: Path | None = None
) -> list[str]:
    """Re-runs the interpreter with every `persistent.X` read forced to a
    specific value -- used once `resolve_layers` has confirmed exactly one
    persistent name gates this combination, to get each of the two real
    variants to bake as separate pre-resolved layer lists."""
    attr_param_name = char_def.selector.args.args[1].arg
    interp = _LayerSelectorInterpreter(
        attrs, attr_param_name, lambda _n: persistent_value, char_def.module_lists,
        _make_loadable_checker(assets_dir), char_def.module_functions,
    )
    return interp.run(char_def.selector)


def expand_attrs(char_def: CharacterImageDef, requested: frozenset[str]) -> frozenset[str]:
    """Expands alias names in `requested` into their real attribute sets
    (Ren'Py's own `_duplicate`'s alias-expansion, simple set logic --
    faithfully reproducible, unlike the interpreter above). Attributes not
    recognized as an alias pass through unchanged (either a real
    attribute, or something the selector itself checks for directly).

    `"lighting_night"` is excluded from the result entirely -- confirmed
    real content: the original `characterimage.rpy`'s `_duplicate` method
    special-cases it the exact same way (`if attr == "lighting_night":
    continue`, skipped *before* alias expansion, never added to the set
    passed to `layer_selector`). It isn't a layer at all -- `_duplicate`
    checks the *raw*, unexpanded request for it separately afterward to
    apply a fixed blue-ish `im.matrix.tint(.75, 0.85, 1.0)` to every
    resolved layer (see vnds_writer.py's `_NIGHT_TINT`/`_emit_character_
    image_show`, which checks the original `requested` set directly rather
    than needing this function to thread the signal through)."""
    expanded: set[str] = set()
    for name in requested:
        if name == "lighting_night":
            continue
        if name in char_def.aliases:
            expanded |= char_def.aliases[name]
        else:
            expanded.add(name)
    return frozenset(expanded)


def resolve_layer_file(
    layer_name: str, character_name: str, layers: tuple[str, ...], assets_dir: Path
) -> tuple[str, int] | None:
    """Matches one interpreter-yielded layer name (e.g. "BaseL", "eyes
    neutral") against `layers`' declared entries (some exact, some
    wildcard patterns like "Base*"/"eyes *") to find (a) its real file
    under `assets_dir/characters/<character_name>/` and (b) its draw-order
    index (position in `layers`, matching the original algorithm's own
    `layer_order` -- draw order is *not* yield order). Returns None if no
    declared layer entry matches at all."""
    base_dir = assets_dir / "characters" / character_name
    if not base_dir.is_dir():
        return None
    lowered = layer_name.lower()

    def find_real_file() -> Path | None:
        # Always resolves via a real (case-insensitive) directory scan
        # rather than guessing a candidate path string and trusting
        # `Path.is_file()` -- on a case-insensitive filesystem (NTFS) a
        # wrong-case guess would still open successfully, silently baking
        # a basename into the emitted script that doesn't match the real
        # file's actual case (breaks on a case-sensitive filesystem/CI
        # runner later, and doesn't match what
        # resolve_character_image_layers converts on disk).
        for f in base_dir.iterdir():
            if f.is_file() and f.stem.lower() == lowered and f.suffix.lower() in (".png", ".webp", ".jpg", ".jpeg"):
                return f
        return None

    for index, entry in enumerate(layers):
        if "*" in entry:
            prefix = entry.replace("*", "").lower()
            if not lowered.startswith(prefix):
                continue
        else:
            if entry.lower() != lowered:
                continue
        found = find_real_file()
        if found is not None:
            return str(found), index
    return None


_INIT_PYTHON_RE = re.compile(r"^(\s*)(?:init\s+(?:-?\d+\s+)?)?python(?:\s+\w+)?\s*:\s*$")


def _extract_python_blocks(source: str) -> list[str]:
    """Slices out each `init [N] python [early/hide]:` block's raw body
    text (indentation preserved, unlike `tokenize_lines`' dedented/flat
    `RawLine`s) so it can be `ast.parse`d as real Python -- a
    `layer_selector` function's `if`/`for` control flow needs its real
    indentation structure, which a flat per-line scan (fine for
    `scan_transform_declarations`' property-assignment lines) can't
    reconstruct."""
    lines = source.splitlines()
    blocks: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        match = _INIT_PYTHON_RE.match(lines[i])
        if not match:
            i += 1
            continue
        header_indent = len(match.group(1).expandtabs(4))
        i += 1
        body_lines: list[str] = []
        while i < n:
            line = lines[i]
            if not line.strip():
                body_lines.append("")
                i += 1
                continue
            indent = len(line[: len(line) - len(line.lstrip())].expandtabs(4))
            if indent <= header_indent:
                break
            body_lines.append(line)
            i += 1
        if body_lines:
            try:
                blocks.append(textwrap.dedent("\n".join(body_lines)))
            except Exception:
                pass
    return blocks


def _const_str(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _string_tuple_literal(node: ast.expr | None) -> tuple[str, ...] | None:
    if not isinstance(node, (ast.Tuple, ast.List)):
        return None
    values: list[str] = []
    for elt in node.elts:
        s = _const_str(elt)
        if s is None:
            return None
        values.append(s)
    return tuple(values)


def _resolve_set_expr(node: ast.expr, python_lists: dict[str, frozenset[str]]) -> frozenset[str] | None:
    """Resolves a set-valued expression appearing in `attribute_sets=(...)`
    -- a plain `{...}` literal, a bare reference to a module-level list/set
    constant, `set(NAME)`, or a chain of `.union(...)` calls on any of
    those (confirmed real content: `set(MARGARET_ARMS).union(SPECIAL_POSES)
    .union(MARGARET_POSES)`) -- recursively, so an arbitrarily long
    `.union()` chain resolves the same way."""
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        values = [_const_str(e) for e in node.elts]
        if any(v is None for v in values):
            return None
        return frozenset(values)  # type: ignore[arg-type]
    if isinstance(node, ast.Name):
        return python_lists.get(node.id)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("set", "Set")
        and len(node.args) == 1
    ):
        return _resolve_set_expr(node.args[0], python_lists)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "union" and len(node.args) == 1:
        base = _resolve_set_expr(node.func.value, python_lists)
        other = _resolve_set_expr(node.args[0], python_lists)
        if base is None or other is None:
            return None
        return base | other
    return None


def _attribute_sets_literal(
    node: ast.expr | None, python_lists: dict[str, frozenset[str]]
) -> tuple[frozenset[str], ...] | None:
    if not isinstance(node, (ast.Tuple, ast.List)):
        return None
    result: list[frozenset[str]] = []
    for elt in node.elts:
        resolved = _resolve_set_expr(elt, python_lists)
        if resolved is None:
            return None
        result.append(resolved)
    return tuple(result)


def _aliases_literal(node: ast.expr | None) -> dict[str, frozenset[str]] | None:
    if not isinstance(node, ast.Dict):
        return None
    result: dict[str, frozenset[str]] = {}
    for key, value in zip(node.keys, node.values):
        k = _const_str(key)
        if k is None or not isinstance(value, ast.Set):
            return None
        values = [_const_str(e) for e in value.elts]
        if any(v is None for v in values):
            return None
        result[k] = frozenset(values)  # type: ignore[arg-type]
    return result


_IMAGE_CI_RE = re.compile(r"^image\s+(\w+)\s*=\s*(CharacterImage\(.*\))\s*$")


def _parse_character_image_line(
    text: str,
    filename: str,
    lineno: int,
    python_functions: dict[str, ast.FunctionDef],
    python_lists: dict[str, frozenset[str]],
) -> CharacterImageDef | None:
    match = _IMAGE_CI_RE.match(text)
    if not match:
        return None
    tag, call_text = match.groups()
    try:
        tree = ast.parse(call_text, mode="eval")
    except SyntaxError:
        return None
    call = tree.body
    if not isinstance(call, ast.Call):
        return None
    kwargs = {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}

    character_name = _const_str(kwargs.get("character_name"))
    layers = _string_tuple_literal(kwargs.get("layers"))
    attribute_sets = _attribute_sets_literal(kwargs.get("attribute_sets"), python_lists)
    aliases = _aliases_literal(kwargs.get("aliases"))
    selector_node = kwargs.get("layer_selector")
    selector = python_functions.get(selector_node.id) if isinstance(selector_node, ast.Name) else None
    if selector is not None and (len(selector.args.args) < 2):
        selector = None  # must take (ci, attr) -- anything else can't be interpreted below

    if character_name is None or layers is None or attribute_sets is None or aliases is None or selector is None:
        return None
    return CharacterImageDef(
        tag=tag,
        character_name=character_name,
        layers=layers,
        attribute_sets=attribute_sets,
        aliases=aliases,
        selector=selector,
        loc=SourceLocation(filename, lineno),
        module_lists=python_lists,
        module_functions=python_functions,
    )


def _collect_module_python(
    source: str, seed_lists: dict[str, frozenset[str]] | None = None
) -> tuple[dict[str, ast.FunctionDef], dict[str, frozenset[str]]]:
    """Scans every `init python:` block in one file, collecting top-level
    function defs (layer_selector candidates) and list/set constant
    assignments. `seed_lists` pre-populates already-known constants (e.g.
    from a game-wide prepass) so a `.union(OTHER_FILE_CONSTANT)` reference
    still resolves when that constant is declared in a different file
    (confirmed real content: felicia.rpy's attribute_sets references
    `SPECIAL_POSES`, which is actually declared in margaret.rpy -- Ren'Py's
    own namespace for these module-level constants is flat across files,
    same as transforms and string defines)."""
    python_functions: dict[str, ast.FunctionDef] = {}
    python_lists: dict[str, frozenset[str]] = dict(seed_lists) if seed_lists else {}
    for block_text in _extract_python_blocks(source):
        try:
            tree = ast.parse(block_text)
        except SyntaxError:
            continue
        for stmt in tree.body:
            if isinstance(stmt, ast.FunctionDef):
                python_functions[stmt.name] = stmt
            elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                literal = _resolve_set_expr(stmt.value, python_lists)
                if literal is not None:
                    python_lists[stmt.targets[0].id] = literal
    return python_functions, python_lists


def scan_character_image_constants(source: str) -> dict[str, frozenset[str]]:
    """Game-wide prepass counterpart to `scan_transform_declarations`/
    `scan_string_defines`: collects one file's module-level list/set
    constants only (no functions, no CharacterImage declarations) so
    callers can merge them across every file before per-file declaration
    parsing."""
    _, python_lists = _collect_module_python(source)
    return python_lists


def parse_character_image_declarations(
    source: str,
    filename: str = "<string>",
    global_lists: dict[str, frozenset[str]] | None = None,
) -> dict[str, CharacterImageDef]:
    """Scans one file for `image TAG = CharacterImage(...)` declarations,
    resolving `layer_selector=NAME`/`attribute_sets=(..., set(NAME), ...)`
    against `def NAME(...):`/`NAME = [...]` found in this same file's
    `init python:` blocks (confirmed real content: the selector function
    always lives in the same file as its character, but a referenced
    constant occasionally lives in another character's file -- `global_lists`,
    built by `scan_character_image_constants` across the whole game, covers
    that case). A declaration referencing anything unresolvable (a non-
    literal kwarg, a selector function this file doesn't define, a shape
    the interpreter can't run) is silently skipped here -- the existing
    "image declaration is not a plain file path" fallback (rpy_parser.py's
    top-level image handling) already flags it `manual`, so nothing is
    lost, just not upgraded to a real render."""
    python_functions, python_lists = _collect_module_python(source, seed_lists=global_lists)

    defs: dict[str, CharacterImageDef] = {}
    for line in tokenize_lines(source):
        if not (line.text.startswith("image ") and "CharacterImage(" in line.text):
            continue
        parsed = _parse_character_image_line(line.text, filename, line.lineno, python_functions, python_lists)
        if parsed is not None:
            defs[parsed.tag] = parsed
    return defs
