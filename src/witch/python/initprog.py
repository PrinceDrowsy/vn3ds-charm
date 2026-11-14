"""A game's init as an ordered program of steps (REWORK-PLAN §6.1, R2.3).

Ren'Py runs `python early` blocks as their files load, then every init block
in `script.initcode` order, following each block's chain of statements. The
program lists the same statements in the same order, each with the Python 3
source of its code (converted from Python 2 where the game's Ren'Py is), for
the shim's driver to run.
"""
from __future__ import annotations

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
    step = {"node": index, "class": n["class"], "file": n["file"], "line": n["line"]}
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
        step.update(store=f.get("store") or "store", varname=f["varname"])
    elif n["class"] == "Style":
        step.update(name=f.get("style_name"), parent=f.get("parent"))
    elif n["class"] == "Screen":
        step["name"] = (f.get("screen") or {}).get("name")
    elif n["class"] == "TranslateString":
        step.update(language=f.get("language"), old=f["old"], new=f["new"])
    elif n["class"] == "TranslatePython":
        step["language"] = f.get("language")
    return step


def _is_harvester(n: dict) -> bool:
    return "zzz_witch_harvest" in n["file"]


def program(harvest: dict) -> dict:
    nodes = harvest["nodes"]
    early = [_step(harvest, i) for i, n in enumerate(nodes) if n["class"] == "EarlyPython" and not _is_harvester(n)]
    init = []
    for priority, start in harvest["initcode"]:
        if start is None or _is_harvester(nodes[start]):
            continue
        steps = []
        i = start
        while i is not None:
            steps.append(_step(harvest, i))
            i = nodes[i]["next"]
        init.append({"priority": priority, "steps": steps})
    modules = {}
    for name, entry in harvest["modules"].items():
        if "source" in entry:
            modules[name] = {"source": entry["source"]}
        elif "ast" in entry:
            try:
                modules[name] = {"source": py2.to_source(entry["ast"], "exec")}
            except py2.ConversionError as e:
                modules[name] = {"error": f"Python 2 conversion: {e}"}
        else:
            modules[name] = entry
    return {"py2": harvest["python"]["version"][0] == 2, "renpy_version": harvest["renpy_version"],
            "modules": modules, "early": early, "init": init}
