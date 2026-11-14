"""Runs a game's init program (witch/python/initprog.py) on the shim and
writes what it produced, for Witch to compare with Ren'Py's own (R2.3).

    micropython charm_init.py PROGRAM.json RESULT.json
"""
import builtins
import io
import json
import sys

# Pure-Python stand-ins for standard modules MicroPython doesn't ship.
sys.path.append("stdlib")

import charm_stdlib  # noqa: E402
import renpy  # noqa: E402
from renpy import missing, py2, revertable  # noqa: E402
from renpy.python import StoreModule, create_store, store_dicts  # noqa: E402


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


def stand_in_modules(names):
    """Registers a placeholder for each of the game's Ren'Py modules the shim
    doesn't implement, so importing it works. `names` is sorted, so parents
    come before their submodules."""
    for name in names:
        if name in sys.modules:
            continue
        parent, _, child = name.rpartition(".")
        if not isinstance(sys.modules.get(parent), missing.MissingModule):
            try:
                __import__(name)
                continue  # the shim has it
            except (ImportError, AttributeError):  # AttributeError: a plain module has no __path__
                pass
        module = sys.modules[name] = missing.MissingModule(name)
        if parent:
            setattr(sys.modules[parent], child, module)


def load_module(name, entry, attempt):
    """Runs one of Ren'Py's own modules from the game's source, as that
    module, one top-level statement at a time, and makes it importable."""
    if "error" in entry:
        raise ImportError("%s: %s" % (name, entry["error"]))
    d = {"__name__": name, "__builtins__": builtins.__dict__}  # a dict, as in a CPython module
    sys.modules[name] = module = StoreModule(d)
    setattr(renpy, name.rpartition(".")[2], module)
    for statement in entry["statements"]:
        attempt((name, statement["line"]), exec, statement["source"], d)


def shim_vars(obj=None):
    """MicroPython has no vars(). Ren'Py's code mutates what it returns, so
    for the shim's dict-backed modules it's the backing dict itself."""
    if obj is None:
        raise TypeError("vars() without an argument isn't supported")
    if isinstance(obj, StoreModule):
        return obj._dict
    return obj.__dict__


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


def startup():
    """What Ren'Py's main does between loading the script and running init:
    the store's self-reference and style manager, then persistent data (fresh
    on a first run) and the preferences it carries."""
    store = store_dicts["store"]
    store["store"] = sys.modules["store"]
    store["style"] = renpy.style.StyleManager()
    persistent = sys.modules["renpy.persistent"]._dict["Persistent"]()
    renpy.game.persistent = persistent
    renpy.game.preferences = persistent._preferences
    store["persistent"] = persistent
    store["_preferences"] = persistent._preferences
    store["_test"] = renpy.test.testast._test


def main(program_path, result_path):
    with open(program_path) as f:
        program = json.load(f)
    builtins.vars = shim_vars
    charm_stdlib.install()
    if program["py2"]:
        revertable.PY2 = True
        py2.install(builtins)

    errors = []

    def attempt(where, function, *args):
        missing.where = where
        try:
            function(*args)
            return True
        except Exception as e:
            errors.append({"node": None, "class": "startup", "file": where[0], "line": where[1],
                           "error": "%s: %s" % (type(e).__name__, e), "trace": traceback_text(e)})
            return False

    attempt(("renpy modules", 0), stand_in_modules, program["renpy_modules"])
    for name, entry in program["modules"]:  # in the harvest's load order
        attempt((name, 0), load_module, name, entry, attempt)
    attempt(("post_import", 0), post_import)
    attempt(("startup", 0), startup)

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
