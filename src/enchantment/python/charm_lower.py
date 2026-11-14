"""Lowering (REWORK-PLAN §6.3): a description as a neutral record, a kind
and the attributes Witch's vocabulary lists for it (bundle/descriptions.py,
loaded with load()). Everything a record holds is plain data: numbers,
text, lists, and other records. The harvester lowers Ren'Py's own objects
by the same rules (harvest.rpy), which is what makes the two comparable.
"""
import renpy
from renpy import missing

classes = {}  # class name -> kind
attrs = {}  # kind -> [attribute or [attribute, tag], ...]

_ABSENT = object()
_FUNCTIONS = ("function", "closure", "bound_method")


def load(table):
    global classes, attrs
    classes = table["classes"]
    attrs = table["attrs"]


def qualified(obj):
    module = getattr(obj, "__module__", None)
    if module is None:
        # MicroPython's functions have no __module__; their globals know.
        module = getattr(obj, "__globals__", {}).get("__name__")
    return "%s.%s" % (module or "?", getattr(obj, "__name__", "?"))


def kind_of(cls):
    """The kind a class lowers to, and whether the class itself is listed
    (a subclass lowers as its nearest listed base)."""
    kind = classes.get(qualified(cls))
    if kind is not None:
        return kind, True
    for base in cls.__bases__:
        kind = kind_of(base)[0]
        if kind is not None:
            return kind, False
    return None, False


def lower(v, depth=0):
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        if isinstance(v, renpy.display.core.absolute):
            return {"absolute": float(v)}
        return v
    if depth > 30:
        return {"too_deep": type(v).__name__}
    if isinstance(v, (tuple, list)):
        return [lower(x, depth + 1) for x in v]
    if isinstance(v, dict):
        return {"dict": [[lower(k, depth + 1), lower(x, depth + 1)] for k, x in v.items()]}
    if isinstance(v, (set, frozenset)):
        return {"set": [lower(x, depth + 1) for x in v]}
    if type(v).__name__ == "module":
        return {"module": v.__name__}
    if type(v).__name__ in _FUNCTIONS:
        return {"function": qualified(getattr(v, "__func__", v))}
    if isinstance(v, type):
        return {"class": qualified(v)}
    if isinstance(v, missing.Missing):
        return {"missing": v._path}
    if isinstance(v, renpy.style.StyleCore):
        return {"style": v.parent and list(v.parent), "name": v.name and list(v.name),
                "properties": [[[k, lower(x, depth + 1)] for k, x in d.items()] for d in v.properties]}
    if qualified(type(v)) == "renpy.curry.Curry":
        return {"curry": lower(v.callable, depth + 1), "args": lower(v.args, depth + 1),
                "kwargs": lower(v.kwargs, depth + 1)}
    kind, exact = kind_of(type(v))
    if kind is None:
        return {"object": qualified(type(v))}
    record = {"kind": kind}
    if not exact:
        record["class"] = qualified(type(v))
    for attr in attrs[kind]:
        name, tag = (attr, None) if isinstance(attr, str) else attr
        value = getattr(v, name, _ABSENT)
        if value is _ABSENT:
            continue
        if tag == "atl":
            record[name] = value  # already the owning statement's node
        elif tag == "parameters":
            record[name] = [] if value is None else value["signature"]
        else:
            record[name] = lower(value, depth + 1)
    return record
