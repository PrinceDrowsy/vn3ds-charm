"""The bundle verifier (REWORK-PLAN §13.1): structure first, then meaning."""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass

from .bundle.reader import Bundle, FormatError, Node
from .bundle.schema import NONE
from .report import Problem, Reach, Report

# Labels Ren'Py itself enters, in addition to `start`.
ENTRY_LABELS = ("splashscreen", "before_main_menu", "main_menu", "start", "after_load", "after_warp", "quit")

_HAS_LABEL = re.compile(r"""\s*renpy\.has_label\(\s*(['"])([^'"]+)\1\s*\)\s*""")


@dataclass(frozen=True)
class Source:
    """What the original game itself defines, as its own engine reported
    it. A reference the original can't resolve either is inherited."""

    labels: frozenset[str]
    image_tags: frozenset[str]


def verify(data: bytes, name: str = "", source: Source | None = None) -> Report:
    report = Report(name, [])
    try:
        bundle = Bundle(data)
        nodes = [bundle.node(i) for i in range(bundle.count("NODE"))]
        _check_tables(bundle, nodes)
    except FormatError as e:
        report.problems.append(Problem(e.code, "crash", "static", str(e),
                                       "The bundle is damaged or from another Witch version; reconvert it."))
        return report
    _Checker(bundle, nodes, report.problems, source).run()
    return report


def _sorted_unique(keys: list[str], what: str) -> None:
    encoded = [k.encode("utf-8") for k in keys]
    for a, b in zip(encoded, encoded[1:]):
        if a == b:
            raise FormatError("duplicate-entry", f"{what} {a.decode()!r} is listed twice")
        if a > b:
            raise FormatError("unsorted-table", f"{what} table isn't sorted at {b.decode()!r}")


def _check_tables(bundle: Bundle, nodes: list[Node]) -> None:
    for tag in ("NAME", "LOCS"):
        if bundle.count(tag) != len(nodes):
            raise FormatError("bundle-section", f"{tag} has {bundle.count(tag)} entries for {len(nodes)} nodes")
    labels = bundle.labels()
    _sorted_unique([n for n, _ in labels], "label")
    for label, i in labels:
        if i == NONE or nodes[i].kind.name != "label" or nodes[i].fields["name"] != label:
            raise FormatError("bad-reference", f"label {label!r} doesn't point at its label node")
    _sorted_unique([n for n, _ in bundle.images()], "image")
    _sorted_unique([bundle.asset(i).path for i in range(bundle.count("ASST"))], "asset")
    for _, d in bundle.images():
        if d == NONE:
            raise FormatError("bad-reference", "an image entry has no displayable")
    for i in range(bundle.count("DISP")):
        bundle.disp(i)
    for i in range(bundle.count("CODE")):
        bundle.code(i)
    for i in range(len(nodes)):
        bundle.node_name(i)
        bundle.node_loc(i)


class _Checker:
    def __init__(self, bundle: Bundle, nodes: list[Node], problems: list[Problem], source: Source | None):
        self.bundle = bundle
        self.nodes = nodes
        self.problems = problems
        self.source = source
        self.labels = dict(bundle.labels())
        # Ren'Py resolves `show tag attrs` by attribute matching, which arrives
        # with R4; until then a show only needs some image with its tag.
        self.tags = {name.split(" ")[0] for name, _ in bundle.images()}

    def run(self) -> None:
        if self.nodes and "start" not in self.labels:
            self._add("missing-start", "crash", "static", None,
                      "The script has no `start` label, so a new game can't begin.")
        self.reach = self._reach()
        for node in self.nodes:
            self._check_node(node)
        self._check_images()

    def _add(self, code: str, severity, reach: Reach, node: Node | None, message: str, suggestion: str = "",
             inherited: bool = False) -> None:
        file, line = self.bundle.node_loc(node.index) if node else ("", 0)
        node_name = self.bundle.node_name(node.index) if node else ""
        self.problems.append(Problem(code, severity, reach, message, suggestion, file, line, node_name, inherited))

    def _successors(self, node: Node) -> list[int]:
        f = node.fields
        kind = node.kind.name
        out = []
        if kind in ("jump", "call"):
            target = self.labels.get(f["target"] if kind == "jump" else f["label"])
            if target is not None:
                out.append(target)
        elif kind == "menu":
            out += [item["block"] for item in f["items"]]
        elif kind == "if":
            out += [entry["block"] for entry in f["entries"] if not self._dead_guard(entry["condition"])]
        elif kind in ("while", "translate"):
            out.append(f["block"])
        if kind not in ("jump", "jump_expression", "return"):
            out.append(node.next)
        return [i for i in out if i != NONE]

    def _dead_guard(self, condition: int) -> bool:
        """`renpy.has_label("x")` for a label the game doesn't have. Labels
        are fixed once the script loads, so that branch never runs; Ren'Py's
        own optional hooks (`hide_windows`) are written this way."""
        if condition == NONE:
            return False
        m = _HAS_LABEL.fullmatch(self.bundle.code(condition)[0])
        return m is not None and m.group(2) not in self.labels

    def _walk(self, roots: list[int], seen: set[int]) -> set[int]:
        found = set()
        queue = deque(r for r in roots if r not in seen)
        while queue:
            i = queue.popleft()
            if i in seen or i in found:
                continue
            found.add(i)
            queue.extend(self._successors(self.nodes[i]))
        return found

    def _reach(self) -> list[Reach]:
        static = self._walk([self.labels[n] for n in ENTRY_LABELS if n in self.labels], set())
        dynamic = self._walk(list(self.labels.values()), static)
        return ["static" if i in static else "dynamic" if i in dynamic else "none" for i in range(len(self.nodes))]

    def _check_node(self, node: Node) -> None:
        reach = self.reach[node.index]
        f = node.fields
        kind = node.kind.name
        if "atl" in node.flags:
            self._add("atl-not-carried", "mismatch", reach, node,
                      f"This `{kind}` has an ATL block, which isn't carried into the bundle yet.",
                      "ATL is harvested in R4.")
        if kind == "unknown":
            self._add("unsupported-statement", "missing", reach, node,
                      f"Ren'Py statement `{f['classname']}` has no Enchantment equivalent; it would do nothing.",
                      "Map it in the harvester and the engine.")
        elif kind in ("jump", "call"):
            target = f["target"] if kind == "jump" else f["label"]
            if target not in self.labels:
                inherited = self.source is not None and target not in self.source.labels
                self._add("missing-label", "crash", reach, node, f"`{kind} {target}` targets a label that doesn't exist.",
                          "The original game lacks it too; often DLC that isn't installed." if inherited else "",
                          inherited)
        elif kind == "menu":
            if f["items"] and all(item["block"] == NONE for item in f["items"]):
                self._add("menu-without-choices", "stuck", reach, node,
                          "This menu has captions but no choices, so the player can't continue.")
        elif kind in ("show", "scene") and f["name"] and f["expression"] == NONE:
            tag = f["name"][0]
            if tag not in self.tags:
                inherited = self.source is not None and tag not in self.source.image_tags
                self._add("missing-image", "missing", reach, node,
                          f"`{kind} {' '.join(f['name'])}`: no image with the tag `{tag}` is defined.",
                          "The original game doesn't define it either." if inherited else "", inherited)

    def _image_reach(self) -> dict[str, Reach]:
        """Each tag's best reach over the shows that use it. A reachable
        `show expression` could name any image, so it lifts every tag."""
        order = ("none", "dynamic", "static")
        best: dict[str, Reach] = {}
        floor: Reach = "none"
        for node in self.nodes:
            if node.kind.name not in ("show", "scene"):
                continue
            reach = self.reach[node.index]
            if node.fields["expression"] != NONE:
                floor = max(floor, "dynamic" if reach != "none" else "none", key=order.index)
            elif node.fields["name"]:
                tag = node.fields["name"][0]
                best[tag] = max(best.get(tag, "none"), reach, key=order.index)
        return {tag: max(best.get(tag, "none"), floor, key=order.index) for tag in self.tags}

    def _check_images(self) -> None:
        reach = self._image_reach()
        for name, d in self.bundle.images():
            disp = self.bundle.disp(d)
            r = reach[name.split(" ")[0]]
            if disp.kind.name == "unknown":
                self.problems.append(Problem(
                    "unsupported-displayable", "missing", r,
                    f"Image `{name}` is a `{disp.fields['classname']}`, which Enchantment can't draw yet."))
            elif disp.kind.name == "image":
                asset = disp.fields["asset"]
                if asset == NONE:
                    self.problems.append(Problem("missing-asset", "missing", r,
                                                 f"Image `{name}` has no file in the bundle."))
                elif self.bundle.asset(asset).type != "image":
                    self.problems.append(Problem(
                        "wrong-asset-type", "crash", r,
                        f"Image `{name}` points at `{self.bundle.asset(asset).path}`, which isn't an image."))
