"""Runs a game's init program (witch/python/initprog.py) on the shim and
writes what it produced, for Witch to compare with Ren'Py's own (R2.3).

    micropython charm_init.py PROGRAM.json RESULT.json
"""
import builtins
import io
import json
import os
import sys

# Pure-Python stand-ins for standard modules MicroPython doesn't ship, and
# the convert-time engine port.
sys.path.append("stdlib")
sys.path.append("convert")

import _charm  # noqa: E402
import charm_lower  # noqa: E402
import charm_stdlib  # noqa: E402
import pyrandom  # noqa: E402
import renpy  # noqa: E402
from renpy import missing, py2, revertable  # noqa: E402
from renpy.python import StoreModule, create_store, store_dicts  # noqa: E402
from renpy.styledata import stylesets  # noqa: E402


_ABSENT = object()


def run(step):
    """One init statement, as Ren'Py 7.0's ast.py executes it. Expressions
    evaluate in the main store whatever store the statement names."""
    kind = step["class"]
    missing.where = (step["file"], step["line"])
    main = store_dicts["store"]
    if kind in ("Python", "EarlyPython"):
        # `python hide` code runs with locals of its own, as Ren'Py's
        # py_exec_bytecode gives it, so its wrapper function stays out of
        # the store.
        if step["hide"]:
            exec(code(step, "code"), create_store(step["store"]), {})
        else:
            exec(code(step, "code"), create_store(step["store"]))
    elif kind == "CreateStore":
        if step["store"] not in renpy.config.special_namespaces:
            create_store(step["store"])
    elif kind == "EarlyConfig":
        setattr(renpy.config, step["varname"], eval(code(step, "code"), main))
    elif kind == "Define":
        store = create_store(step["store"])
        value = eval(code(step, "code"), main)
        special = renpy.config.special_namespaces.get(step["store"])
        if "index" in step:
            store[step["varname"]][eval(code(step, "index"), main)] = value
        elif step["operator"] != "=":
            # Ren'Py 8's `define x += y` and friends.
            store[step["varname"]] = eval("_a %s _b" % step["operator"][:-1], {"_a": store[step["varname"]],
                                                                               "_b": value})
        elif special is not None:
            special.set(step["varname"], value)
        else:
            store[step["varname"]] = value
        dump_definition(step)
    elif kind == "Default":
        special = renpy.config.special_namespaces.get(step["store"])
        if special is not None:
            special.set_default(step["varname"], eval(code(step, "code"), main))
        else:
            # Evaluated when the game starts (or a save without it loads).
            create_store(step["store"])
            _charm.default(step["store"], step["varname"], step["node"])
            dump_definition(step)
    elif kind == "Image":
        if "code" in step:
            image = eval(code(step, "code"), main)
        else:
            image = renpy.display.transform.ATLTransform(step["node"])
        renpy.exports.image(tuple(step["name"]), image)
    elif kind == "Transform":
        transform = renpy.display.transform.ATLTransform(step["node"], parameters=step["parameters"])
        create_store(step["store"])[step["varname"]] = transform
        renpy.dump.transforms.append((step["varname"], step["file"], step["line"]))
    elif kind == "Screen":
        _charm.screen(step["name"], step["node"])
        renpy.dump.screens.append((step["name"], step["file"], step["line"]))
    elif kind == "TranslateString":
        _charm.translate_string(step["language"], step["old"], step["new"])
    elif kind == "Style":
        if renpy.config.defer_styles:
            # Applied when the language is set, after init (§8.10).
            renpy.translation.deferred_styles.append(step["node"])
        else:
            apply_style(step)
    elif kind in ("Pass", "Init"):
        pass
    else:
        missing.record("statement " + kind)


def dump_definition(step):
    name = step["varname"] if step["store"] == "store" else step["store"][6:] + "." + step["varname"]
    renpy.dump.definitions.append((name, step["file"], step["line"]))


def code(step, field):
    return source(step[field])


def source(entry):
    if "error" in entry:
        raise SyntaxError(entry["error"])
    return entry["source"]


def apply_style(step):
    """Ren'Py's ast.Style.apply."""
    main = store_dicts["store"]
    if step["variant"] is not None and not renpy.exports.variant(eval(code(step, "variant"), main)):
        return
    s = renpy.style.get_or_create_style(step["name"])
    if step["clear"]:
        s.clear()
    if step["parent"] is not None:
        s.set_parent(step["parent"])
    if step["take"] is not None:
        s.take(step["take"])
    for name in step["delattr"]:
        s.delattr(name)
    if step["properties"]:
        properties = {}
        for name, entry in step["properties"]:
            value = eval(source(entry), main)
            if name == "properties":
                properties.update(value)
            else:
                properties[name] = value
        s.add_properties(properties)


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
            return {"class": charm_lower.qualified(v)}
        if type(v).__name__ == "module" or isinstance(v, (StoreModule, missing.MissingModule)):
            return {"module": getattr(v, "__name__", None) or getattr(v, "_name", "?")}
        if type(v).__name__ in ("function", "closure", "bound_method") or callable(v) and not hasattr(v, "__dict__"):
            # Functions take attributes on this MicroPython (patch 0002), so
            # they have a __dict__ too.
            return {"function": charm_lower.qualified(getattr(v, "__func__", v))}
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
        elif charm_lower.kind_of(type(v))[0] is not None or isinstance(v, renpy.style.StyleCore):
            # A description (REWORK-PLAN §6.3): compared by its record.
            out["lowered"] = charm_lower.lower(v)
        else:
            out["object"] = charm_lower.qualified(type(v))
            attrs = getattr(v, "__dict__", {})
            out["attrs"] = dict((k, self.value(x, depth + 1)) for k, x in attrs.items() if not k.startswith("__"))
        return out


def stand_in_modules(names, loaded):
    """Registers a placeholder for each of the game's Ren'Py modules that
    neither the shim implements nor the program loads from the game's
    source (`loaded`), so importing it works. The shim's own modules aren't
    imported here: they build on Ren'Py's own (renpy.object), which load
    after this."""
    for name in names:
        if name in sys.modules or name in loaded or shim_has(name):
            continue
        module = sys.modules[name] = missing.MissingModule(name)
        parent, _, child = name.rpartition(".")
        if parent in sys.modules:
            setattr(sys.modules[parent], child, module)


def shim_has(name):
    path = name.replace(".", "/")
    for candidate in (path + ".py", path + "/__init__.py"):
        try:
            os.stat(candidate)
            return True
        except OSError:
            pass
    return False


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


def startup(load_rpym, rpym):
    """What Ren'Py's main does before loading the script: the screen
    variants (a PC's, since the port reproduces the PC game), the store's
    self-reference and style manager, then the error-handling module and
    the system styles it sets up."""
    renpy.config.variants = ["large", "pc", None]
    # Where the game's files are, as the engine names them in the bundle.
    renpy.config.basedir = renpy.config.renpy_base = "/"
    renpy.config.gamedir = "/game"
    renpy.config.commondir = "/renpy/common"
    store = store_dicts["store"]
    store["store"] = sys.modules["store"]
    store["style"] = renpy.style.StyleManager()
    load_rpym("_errorhandling")
    if "tl/None/common" in rpym:
        load_rpym("tl/None/common")
    if renpy.config.init_system_styles is not None:
        renpy.config.init_system_styles()
    renpy.style.build_styles()


def load_persistent(virtual_size):
    """What Ren'Py's main does between loading the script and running init:
    persistent data and the preferences it carries, as on any launch after
    the first, where the screen size init last ended with applies."""
    store = store_dicts["store"]
    persistent = sys.modules["renpy.persistent"]._dict["Persistent"]()
    persistent._virtual_size = tuple(virtual_size)
    renpy.config.screen_width, renpy.config.screen_height = persistent._virtual_size
    renpy.game.persistent = persistent
    renpy.game.preferences = persistent._preferences
    store["persistent"] = persistent
    store["_preferences"] = persistent._preferences
    store["_test"] = renpy.test.testast._test


def resolved(style, dumper):
    """A style's non-None values, in the form harvest.rpy gives Ren'Py's."""
    values = {}
    for prefix in ("insensitive_", "idle_", "hover_", "selected_idle_", "selected_hover_"):
        for target in renpy.style._targets():
            v = style._get(prefix + target)
            if v is not None:
                values[prefix + target] = dumper.value(v)
    return values


def main(program_path, result_path):
    with open(program_path) as f:
        program = json.load(f)
    builtins.vars = shim_vars
    charm_stdlib.install()
    if program["py2"]:
        revertable.PY2 = True
        pyrandom.PY2 = True
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

    for flag, value in program["platform"].items():
        setattr(renpy, flag, tuple(value) if isinstance(value, list) else value)
    charm_lower.load(program["descriptions"])
    _charm.labels = set(program["all_labels"])
    _charm.files = program["files"]
    _charm.common_files = program["common_files"]
    if program["style_tables"] is not None:
        stylesets.load(program["style_tables"])
    attempt(("renpy modules", 0), stand_in_modules, program["renpy_modules"],
            set(name for name, _ in program["modules"]))
    for name, entry in program["modules"]:  # in the harvest's load order
        attempt((name, 0), load_module, name, entry, attempt)
    attempt(("post_import", 0), post_import)

    ran = [0]

    def run_steps(steps):
        for step in steps:
            try:
                run(step)
                ran[0] += 1
            except Exception as e:
                errors.append({"node": step["node"], "class": step["class"], "file": step["file"],
                               "line": step["line"], "error": "%s: %s" % (type(e).__name__, e),
                               "trace": traceback_text(e)})

    steps = program["steps"]
    labels = program["labels"]

    def run_chain(start):
        """One init block, followed as Ren'Py's execution context would:
        through labels, calls and returns, ifs, loops and jumps."""
        main = store_dicts["store"]
        stack = []
        i = start
        while i is not None:
            step = steps[str(i)]
            i = step["next"]
            kind = step["class"]
            try:
                missing.where = (step["file"], step["line"])
                if kind in ("Call", "Jump"):
                    label = eval(source(step["expression"]), main) if "expression" in step else step["label"]
                    if label not in labels:
                        raise Exception("init code reaches label %r, which the program doesn't hold" % label)
                    if kind == "Call":
                        stack.append(i)
                    i = labels[label]
                elif kind == "Return":
                    i = stack.pop() if stack else None
                elif kind == "If":
                    for condition, block in step["entries"]:
                        if eval(source(condition), main):
                            i = block
                            break
                elif kind == "While":
                    if eval(source(step["condition"]), main):
                        i = step["block"]
                elif kind != "Label":
                    run(step)
                ran[0] += 1
            except Exception as e:
                errors.append({"node": step["node"], "class": kind, "file": step["file"], "line": step["line"],
                               "error": "%s: %s" % (type(e).__name__, e), "trace": traceback_text(e)})

    loaded = set()

    def load_rpym(name, **kwargs):
        """renpy.load_module: a .rpym file's early work and init blocks, run
        now, with `kwargs` set in the store while they run."""
        if name in loaded:
            return
        loaded.add(name)
        module = program["rpym"].get(name)
        if module is None:
            raise Exception("Module %s could not be loaded." % name)
        old_locked = renpy.config.locked
        renpy.config.locked = False
        store = store_dicts["store"]
        saved = dict((k, store.get(k, _ABSENT)) for k in kwargs)
        store.update(kwargs)
        where = missing.where
        run_steps(module["early"])
        for _priority, start in module["init"]:
            run_chain(start)
        missing.where = where
        for k, v in saved.items():
            if v is _ABSENT:
                store.pop(k, None)
            else:
                store[k] = v
        renpy.config.locked = old_locked

    renpy.exports.load_module = load_rpym
    # renpy.atl builds on renpy.object, so it loads after Ren'Py's modules.
    attempt(("atl", 0), renpy.atl.load_properties, program["atl_properties"])
    attempt(("startup", 0), startup, load_rpym, program["rpym"])
    run_steps(program["early"])
    attempt(("persistent", 0), load_persistent, program["virtual_size"])
    for _priority, start in program["init"]:
        run_chain(start)

    dumper = Dumper()
    stores = dict((name, dict((k, dumper.value(v)) for k, v in d.items() if not k.startswith("__")))
                  for name, d in store_dicts.items())
    with open(result_path, "w") as f:
        json.dump({"ran": ran[0], "errors": errors, "missing": missing.report(), "store": stores,
                   "registries": {
                       "images": [[list(name), charm_lower.lower(d)] for name, d in _charm.images.items()],
                       "screens": _charm.screens,
                       "defaults": [list(d) for d in _charm.defaults],
                       "strings": _charm.strings,
                       "styles": [[list(name), dumper.value(style)] for name, style in renpy.style.styles.items()],
                       "resolved_styles": [[list(name), resolved(style, dumper)]
                                           for name, style in renpy.style.styles.items()],
                       "deferred_styles": renpy.translation.deferred_styles,
                       "channels": [[name, charm_lower.lower(c)] for name, c in renpy.audio.audio.channels.items()],
                   }}, f)


main(sys.argv[1], sys.argv[2])
