"""Runs a game's init program (witch/python/initprog.py) on the shim and
writes what it produced, for Witch to compare with Ren'Py's own (R2.3).

    micropython charm_init.py PROGRAM.json RESULT.json
"""
import builtins
import io
import json
import sys

import renpy
from renpy import missing, py2, revertable
from renpy.python import StoreModule, create_store, store_dicts


def run(step):
    kind = step["class"]
    missing.where = (step["file"], step["line"])
    if kind in ("Python", "EarlyPython"):
        exec(code(step, "code"), create_store(step["store"]))
    elif kind == "Define":
        store = create_store(step["store"])
        value = eval(code(step, "code"), store)
        if "index" in step:
            store[step["varname"]][eval(code(step, "index"), store)] = value
        elif step["operator"] == "=":
            store[step["varname"]] = value
        else:
            # Ren'Py 8's `define x += y` and friends.
            store[step["varname"]] = eval("_a %s _b" % step["operator"][:-1], {"_a": store[step["varname"]],
                                                                               "_b": value})
    elif kind == "Pass":
        pass
    else:
        # Images, transforms, styles, screens, translations and defaults go
        # into Ren'Py's registries rather than the store; the shim takes them
        # on as it grows. Until then they're listed, not run.
        missing.record("statement " + kind)


def code(step, field):
    entry = step[field]
    if "error" in entry:
        raise SyntaxError(entry["error"])
    return entry["source"]


def traceback_text(e):
    out = io.StringIO()
    sys.print_exception(e, out)
    return out.getvalue()


class Dumper:
    """The store in the same value model harvest.rpy uses for Ren'Py's
    (ids on first sight, refs after). Dicts and sets aren't sorted here;
    Witch compares them as unordered."""

    def __init__(self):
        self.seen = {}
        self.alive = []

    def value(self, v, depth=0):
        if v is None or isinstance(v, (bool, int, str)):
            if isinstance(v, int) and not isinstance(v, bool) and not -2 ** 53 < v < 2 ** 53:
                return {"int": str(v)}
            return v
        if isinstance(v, float):
            return v if v == v and v not in (float("inf"), float("-inf")) else {"float": repr(v)}
        if isinstance(v, missing.Missing):
            return {"missing": v._path}
        if isinstance(v, type):
            return {"class": qualified(v)}
        if callable(v) and not hasattr(v, "__dict__"):
            return {"function": qualified(v)}
        if depth > 40:
            return {"too_deep": type(v).__name__}
        key = id(v)
        if key in self.seen:
            return {"ref": self.seen[key]}
        self.seen[key] = len(self.seen)
        self.alive.append(v)
        out = {"id": self.seen[key]}
        if isinstance(v, list):
            out["list"] = [self.value(x, depth + 1) for x in v]
        elif isinstance(v, tuple):
            out["tuple"] = [self.value(x, depth + 1) for x in v]
        elif isinstance(v, dict):
            out["dict"] = [[self.value(k, depth + 1), self.value(x, depth + 1)] for k, x in v.items()]
        elif isinstance(v, (set, frozenset)):
            out["set"] = [self.value(x, depth + 1) for x in v]
        else:
            out["object"] = qualified(type(v))
            attrs = getattr(v, "__dict__", {})
            out["attrs"] = dict((k, self.value(x, depth + 1)) for k, x in attrs.items() if not k.startswith("__"))
        return out


def qualified(obj):
    return "%s.%s" % (getattr(obj, "__module__", None) or "?", getattr(obj, "__name__", "?"))


def load_module(name, entry):
    """Runs one of Ren'Py's own modules from the game's source, as that
    module, and makes it importable."""
    if "error" in entry:
        raise ImportError("%s: %s" % (name, entry["error"]))
    d = {"__name__": name}
    sys.modules[name] = module = StoreModule(d)
    setattr(renpy, name.rpartition(".")[2], module)
    exec(entry["source"], d)


def post_import():
    """Ren'Py's renpy.post_import: the main store, with defaultstore's names
    and its eval, also reachable as renpy.store."""
    store = create_store("store")
    renpy.store = sys.modules["renpy.store"] = sys.modules["store"]
    defaultstore = sys.modules["renpy.defaultstore"]._dict
    for k, v in defaultstore.items():
        if k not in store:
            store[k] = v
    store["eval"] = defaultstore["eval"]


def main(program_path, result_path):
    with open(program_path) as f:
        program = json.load(f)
    if program["py2"]:
        revertable.PY2 = True
        py2.install(builtins)

    errors = []
    for name in ("renpy.minstore", "renpy.defaultstore"):
        missing.where = (name, 0)
        try:
            load_module(name, program["modules"][name])
        except Exception as e:
            errors.append({"node": None, "class": "module", "file": name, "line": 0,
                           "error": "%s: %s" % (type(e).__name__, e), "trace": traceback_text(e)})
    post_import()

    ran = 0
    for step in program["early"] + [s for block in program["init"] for s in block["steps"]]:
        try:
            run(step)
            ran += 1
        except Exception as e:
            errors.append({"node": step["node"], "class": step["class"], "file": step["file"], "line": step["line"],
                           "error": "%s: %s" % (type(e).__name__, e), "trace": traceback_text(e)})

    dumper = Dumper()
    stores = dict((name, dict((k, dumper.value(v)) for k, v in d.items() if not k.startswith("__")))
                  for name, d in store_dicts.items())
    with open(result_path, "w") as f:
        json.dump({"ran": ran, "errors": errors, "missing": missing.report(), "store": stores}, f)


main(sys.argv[1], sys.argv[2])
