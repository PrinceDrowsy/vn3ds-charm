"""A game's init as an ordered program of steps (REWORK-PLAN §6.1, R2.3).

Ren'Py runs `python early` blocks as their files load, then every init block
in `script.initcode` order, following each block's chain of statements. The
program lists the same statements in the same order, each with the Python 3
source of its code (converted from Python 2 where the game's Ren'Py is), for
the shim's driver to run.
"""
from __future__ import annotations

import ast

from . import py2

# Init-time statement classes and the fields whose code they run.
_CODE_FIELDS = {
    "Python": ("code",), "EarlyPython": ("code",), "Define": ("code", "index"), "Default": ("code",),
    "Image": ("code",), "TranslatePython": ("code",),
}


def _source(harvest: dict, ref: dict | None, mode: str) -> dict | None:
    """The Python 3 source of a harvested code reference, or why there's none."""
    if ref is None:
        return None
    if "c" not in ref:
        return {"error": "no source in the harvest"}
    entry = harvest["compiled"][ref["c"]]
    if "error" in entry:
        return {"error": f"Ren'Py couldn't compile it: {entry['error']}"}
    if "source" in entry:
        return {"source": entry["source"]}
    try:
        return {"source": py2.to_source(entry["ast"], mode)}
    except py2.ConversionError as e:
        return {"error": f"Python 2 conversion: {e}"}


def _mode(ref: dict | None) -> str:
    return ref.get("mode", "eval") if ref else "eval"


def _step(harvest: dict, index: int) -> dict:
    n = harvest["nodes"][index]
    f = n["fields"]
    step = {"node": index, "class": n["class"], "file": n["file"], "line": n["line"], "next": n["next"]}
    for field in _CODE_FIELDS.get(n["class"], ()):
        ref = f.get(field)
        if ref is not None:
            step[field] = {"mode": _mode(ref), **_source(harvest, ref, _mode(ref))}
    if n["class"] in ("Python", "EarlyPython"):
        step["store"] = f.get("store") or "store"
        step["hide"] = bool(f.get("hide"))
    elif n["class"] in ("Define", "Default"):
        step.update(store=f.get("store") or "store", varname=f["varname"], operator=f.get("operator") or "=")
    elif n["class"] == "Image":
        step.update(name=f["imgname"], atl=bool(f.get("atl")))
    elif n["class"] == "Transform":
        step.update(store=f.get("store") or "store", varname=f["varname"], parameters=f.get("parameters"))
    elif n["class"] == "Style":
        properties = (f.get("properties") or {}).get("dict", [])
        step.update(name=f["style_name"], parent=f.get("parent"), clear=bool(f.get("clear")), take=f.get("take"),
                    delattr=f.get("delattr") or [],
                    properties=[[name, _source(harvest, ref, "eval")] for name, ref in properties],
                    variant=_source(harvest, f.get("variant"), "eval"))
    elif n["class"] == "Screen":
        step["name"] = (f.get("screen") or {}).get("name")
    elif n["class"] == "TranslateString":
        step.update(language=f.get("language"), old=f["old"], new=f["new"])
    elif n["class"] == "TranslatePython":
        step["language"] = f.get("language")
    elif n["class"] in ("Call", "Jump"):
        target = f["label" if n["class"] == "Call" else "target"]
        if f.get("expression"):
            step["expression"] = _source(harvest, target, "eval")
        else:
            step["label"] = target
    elif n["class"] == "If":
        step["entries"] = [[_source(harvest, cond, "eval"), block["block"][0]] for cond, block in f["entries"]]
    elif n["class"] == "While":
        step.update(condition=_source(harvest, f["condition"], "eval"), block=f["block"]["block"][0])
    return step


def _targets(harvest: dict, n: dict) -> list[int]:
    """The nodes init code can go to from `n` besides its next."""
    f = n["fields"]
    if n["class"] == "If":
        return [block["block"][0] for _, block in f["entries"]]
    if n["class"] == "While":
        return [f["block"]["block"][0]]
    if n["class"] in ("Call", "Jump") and not f.get("expression"):
        label = harvest["labels"].get(f["label" if n["class"] == "Call" else "target"])
        return [] if label is None else [label]
    return []


def _reachable(harvest: dict, starts: list[int]) -> dict:
    """Every node init code can reach from `starts`, as steps by index."""
    steps = {}
    todo = list(starts)
    while todo:
        i = todo.pop()
        if i is None or i in steps:
            continue
        n = harvest["nodes"][i]
        steps[i] = _step(harvest, i)
        todo.append(n["next"])
        todo += _targets(harvest, n)
    return steps


def _statements(source: str) -> list[dict]:
    """A module's top-level statements, run one at a time so that a part the
    shim can't support yet doesn't stop the rest from loading."""
    return [{"line": stmt.lineno, "source": ast.unparse(stmt)} for stmt in ast.parse(source).body]


def _is_harvester(n: dict) -> bool:
    return "zzz_witch_harvest" in n["file"]


def _early(harvest: dict, i: int) -> list[dict]:
    """What Ren'Py does with node `i` as it loads its file, before init:
    a statement class with an early_execute creates its store, `python
    early` runs, and a `define` of an early config variable sets it."""
    early = harvest["early"]
    n = harvest["nodes"][i]
    if n["class"] not in early["classes"]:
        return []
    f = n["fields"]
    if n["class"] == "EarlyPython":
        return [_step(harvest, i)]
    steps = [{"node": i, "class": "CreateStore", "file": n["file"], "line": n["line"],
              "store": f.get("store") or "store"}]
    if (n["class"] == "Define" and f.get("store") == "store.config" and f["varname"] in early["config"]
            and (f.get("operator") or "=") == "=" and f.get("index") is None):
        steps.append(dict(_step(harvest, i), **{"class": "EarlyConfig"}))
    return steps


def _rpym_name(path: str) -> str | None:
    """The name renpy.load_module knows a .rpym file by, or None for a
    script file."""
    stem, dot, ext = path.rpartition(".")
    if ext not in ("rpym", "rpymc"):
        return None
    for root in ("renpy/common/", "game/"):
        if stem.startswith(root):
            return stem[len(root):]
    return stem


def program(harvest: dict) -> dict:
    nodes = harvest["nodes"]
    # A .rpym module loads when init code calls renpy.load_module: its
    # early work, then its init blocks in file order, all at that moment.
    early = []
    rpym = {}
    for i, n in enumerate(nodes):
        if _is_harvester(n):
            continue
        name = _rpym_name(n["file"])
        if name is None:
            early += _early(harvest, i)
            continue
        module = rpym.setdefault(name, {"early": [], "init": []})
        module["early"] += _early(harvest, i)
        if n["class"] == "Init":
            module["init"].append([n["fields"]["priority"], n["fields"]["block"]["block"][0]])
    init = [[priority, start] for priority, start in harvest["initcode"]
            if start is not None and not _is_harvester(nodes[start])]
    starts = [start for _, start in init] + [start for m in rpym.values() for _, start in m["init"]]
    # Init code is a graph, not a list: labels, calls, ifs and loops run
    # in it as anywhere else. Labels it reaches by name are kept by name.
    steps = _reachable(harvest, starts)
    labels = dict((name, i) for name, i in harvest["labels"].items() if i in steps)
    modules = []  # in load order
    for name, entry in harvest["modules"]:
        if "source" in entry:
            source = entry["source"]
        elif "ast" in entry:
            try:
                source = py2.to_source(entry["ast"], "exec")
            except py2.ConversionError as e:
                modules.append([name, {"error": f"Python 2 conversion: {e}"}])
                continue
        else:
            modules.append([name, entry])
            continue
        modules.append([name, {"statements": _statements(source)}])
    return {"py2": harvest["python"]["version"][0] == 2, "renpy_version": harvest["renpy_version"],
            "renpy_modules": harvest["renpy_modules"], "style_tables": harvest.get("style_tables"),
            "modules": modules, "early": early, "init": init, "rpym": rpym,
            "steps": dict((str(i), step) for i, step in steps.items()), "labels": labels,
            "platform": harvest["early"]["platform"],
            "files": [f for f in harvest["early"]["files"] if not _is_harvester({"file": f})],
            "common_files": [f for f in harvest["early"]["common_files"] if not _is_harvester({"file": f})]}
