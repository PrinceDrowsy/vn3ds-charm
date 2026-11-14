"""Turns a Ren'Py harvest (harvest.rpy's output) into the bundle's node graph.

Node i of the harvest becomes node i of the bundle, so Ren'Py's node count
and node names carry over unchanged (saves refer to the names).
"""
from __future__ import annotations

from ..bundle.schema import NONE
from ..bundle.writer import Writer


def _text(value):
    """A harvested expression or plain string, as source text."""
    if isinstance(value, dict):
        return value["expr"]
    return value


def _first(value):
    """The first node of a harvested block, or the node a reference names."""
    if isinstance(value, dict):
        if "block" in value:
            return value["block"][0] if value["block"] else NONE
        if "node" in value:
            return NONE if value["node"] is None else value["node"]
    return NONE


def source_path(path: str) -> str:
    """A Ren'Py file path relative to the game, without the developer's machine prefix."""
    path = "/" + path.replace("\\", "/")  # paths may already start at game/
    for marker in ("/game/", "/renpy/common/"):
        at = path.rfind(marker)
        if at >= 0:
            return path[at + 1:]
    return path.rsplit("/", 1)[-1]


class _Graph:
    def __init__(self, harvest: dict, writer: Writer):
        self.h = harvest
        self.w = writer

    def code(self, value, mode: str = "eval") -> int:
        if value is None:
            return NONE
        if isinstance(value, dict) and "code" in value:
            return self.w.code(value["code"], value["mode"])
        return self.w.code(_text(value), mode)

    def parameters(self, info) -> int:
        if info is None:
            return NONE
        parts = [name if default is None else f"{name}={_text(default)}" for name, default in info["parameters"]]
        if info.get("extrapos"):
            parts.append("*" + info["extrapos"])
        if info.get("extrakw"):
            parts.append("**" + info["extrakw"])
        return self.w.code(", ".join(parts), "parameters")

    def arguments(self, info) -> int:
        if info is None:
            return NONE
        parts = [_text(expr) if name is None else f"{name}={_text(expr)}" for name, expr in info["arguments"]]
        if info.get("extrapos"):
            parts.append("*" + _text(info["extrapos"]))
        if info.get("extrakw"):
            parts.append("**" + _text(info["extrakw"]))
        return self.w.code(", ".join(parts), "arguments")

    def imspec(self, spec, layer=None) -> dict:
        if spec is None:
            return {"layer": layer or ""}
        # Ren'Py's imspec grew from 3 to 6 to 7 fields over its versions.
        if len(spec) == 3:
            name, at_list, spec_layer = spec
            expression = tag = zorder = None
            behind = []
        elif len(spec) == 6:
            name, expression, tag, at_list, spec_layer, zorder = spec
            behind = []
        else:
            name, expression, tag, at_list, spec_layer, zorder, behind = spec[:7]
        return {
            "name": list(name),
            "expression": self.code(expression),
            "tag": tag or "",
            "at": [self.code(a) for a in at_list or []],
            "layer": spec_layer or layer or "",
            "zorder": self.code(zorder),
            "behind": list(behind or []),
        }

    def node(self, n: dict) -> tuple[str, set, dict]:
        """(kind, flags, payload) for one harvested node."""
        f = n["fields"]
        c = n["class"]
        atl = {"atl"} if f.get("atl") else set()
        if c == "Label":
            return "label", set(), {"name": n["name"], "parameters": self.parameters(f.get("parameters"))}
        if c == "Say":
            return "say", {"interact"} if f.get("interact", True) else set(), {
                "who": self.code(f.get("who")),
                "what": f["what"],
                "attributes": list(f.get("attributes") or []),
                "temporary_attributes": list(f.get("temporary_attributes") or []),
                "with": self.code(f.get("with_")),
                "arguments": self.arguments(f.get("arguments")),
                "identifier": f.get("identifier") or "",
            }
        if c in ("Show", "Hide"):
            return c.lower(), atl, self.imspec(f["imspec"])
        if c == "Scene":
            return "scene", atl, self.imspec(f["imspec"], f.get("layer"))
        if c == "With":
            return "with", set(), {"expr": self.code(f["expr"]), "paired": self.code(f.get("paired"))}
        if c == "Jump":
            if f.get("expression"):
                return "jump_expression", set(), {"target": self.code(f["target"])}
            return "jump", set(), {"target": f["target"]}
        if c == "Call":
            arguments = self.arguments(f.get("arguments"))
            if f.get("expression"):
                return "call_expression", set(), {"label": self.code(f["label"]), "arguments": arguments}
            return "call", set(), {"label": f["label"], "arguments": arguments}
        if c == "Return":
            return "return", set(), {"expression": self.code(f.get("expression"))}
        if c == "Menu":
            items = [{
                "label": item[0],
                "condition": self.code(item[1]),
                "block": _first(item[2]) if item[2] is not None else NONE,
                "arguments": self.arguments(item[3]) if len(item) > 3 else NONE,
            } for item in f["items"]]
            return "menu", set(), {"items": items, "set": self.code(f.get("set")), "with": self.code(f.get("with_")),
                                   "arguments": self.arguments(f.get("arguments"))}
        if c == "If":
            entries = [{"condition": self.code(cond), "block": _first(block)} for cond, block in f["entries"]]
            return "if", set(), {"entries": entries}
        if c == "While":
            return "while", set(), {"condition": self.code(f["condition"]), "block": _first(f["block"])}
        if c in ("Python", "EarlyPython"):
            kind = "python" if c == "Python" else "early_python"
            return kind, {"hide"} if f.get("hide") else set(), {"code": self.code(f["code"]), "store": f["store"]}
        if c == "Pass":
            return "pass", set(), {}
        if c == "UserStatement":
            words = f["parsed"][0] if f.get("parsed") else []
            name = " ".join(words) if isinstance(words, list) else str(words)
            return "user_statement", set(), {"name": name, "line": f["line"]}
        if c == "Translate":
            return "translate", set(), {"identifier": f["identifier"], "language": f.get("language") or "",
                                        "block": _first(f["block"])}
        if c == "EndTranslate":
            return "end_translate", set(), {}
        if c in ("ShowLayer", "Camera"):
            return ("show_layer" if c == "ShowLayer" else "camera"), atl, {
                "layer": f.get("layer") or "", "at": [self.code(a) for a in f.get("at_list") or []]}
        if c == "Init":
            return "init", set(), {"priority": f["priority"], "block": _first(f["block"])}
        if c == "Define":
            return "define", set(), {"store": f["store"], "varname": f["varname"],
                                     "operator": f.get("operator") or "=", "index": self.code(f.get("index")),
                                     "code": self.code(f["code"])}
        if c == "Default":
            return "default", set(), {"store": f["store"], "varname": f["varname"], "code": self.code(f["code"])}
        if c == "Image":
            return "image", atl, {"name": list(f["imgname"]), "code": self.code(f.get("code"))}
        if c == "Transform":
            return "transform", atl, {"store": f.get("store") or "store", "varname": f["varname"],
                                      "parameters": self.parameters(f.get("parameters"))}
        if c == "Style":
            return "style", set(), {"name": f.get("style_name") or "", "parent": f.get("parent") or ""}
        if c == "Screen":
            return "screen", set(), {"name": f["screen"].get("name", "")}
        if c == "Testcase":
            return "testcase", set(), {"label": f["label"]}
        if c == "TranslateString":
            return "translate_string", set(), {"language": f.get("language") or "", "old": f["old"], "new": f["new"]}
        if c == "TranslatePython":
            return "translate_python", set(), {"language": f.get("language") or "", "code": self.code(f["code"])}
        if c in ("TranslateBlock", "TranslateEarlyBlock"):
            return "translate_block", {"early"} if c == "TranslateEarlyBlock" else set(), {
                "language": f.get("language") or "", "block": _first(f["block"])}
        return "unknown", set(), {"classname": c}

    def build(self) -> None:
        nodes = self.h["nodes"]
        for i, n in enumerate(nodes):
            kind, flags, payload = self.node(n)
            self.w.node(kind, payload, node_id=n["name"], file=source_path(n["file"]), line=n["line"], flags=flags)
        for i, n in enumerate(nodes):
            if n["next"] is not None:
                self.w.link(i, n["next"])
        for name, i in sorted(self.h["labels"].items()):
            if i is not None and nodes[i]["class"] == "Label" and nodes[i]["name"] == name:
                self.w.label(name, i)
        # Displayable trees and their assets are harvested in R4; until then
        # every image is listed by name with its Ren'Py class.
        for name in sorted(self.h["images"]):
            self.w.image(name, self.w.disp("unknown", {"classname": self.h["images"][name]["class"]}))


def build(harvest: dict, writer: Writer | None = None) -> Writer:
    writer = writer or Writer()
    _Graph(harvest, writer).build()
    return writer
