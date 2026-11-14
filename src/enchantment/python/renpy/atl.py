"""ATL. Its trees are in the bundle and run in the C ATL VM (REWORK-PLAN
§7.4); what's here is the warper registry, which games extend from Python
(Python warpers are sampled into tables when lowered, §6.3), and the table
of transform properties with their types, from the game's own Ren'Py."""
import renpy
from renpy import missing_attribute

warpers = {}

position = renpy.object.Sentinel("position")


def any_object(x):
    return x


def bool_or_none(x):
    if x is None:
        return x
    return bool(x)


def float_or_none(x):
    if x is None:
        return x
    return float(x)


_TYPES = {"position": position, "any_object": any_object, "bool_or_none": bool_or_none,
          "float_or_none": float_or_none, "float": float, "int": int, "bool": bool}

PROPERTIES = {}


def load_properties(table):
    """Installs the harvested property table (name -> type name, or a list
    of them for a tuple property)."""
    def kind(t):
        return tuple(kind(i) for i in t) if isinstance(t, list) else _TYPES[t]

    PROPERTIES.clear()
    for name, t in table.items():
        PROPERTIES[name] = kind(t)


def atl_warper(f):
    warpers[f.__name__] = f
    return f


# The warpers Ren'Py defines itself; the rest come from 000atl.rpy.
@atl_warper
def pause(t):
    if t < 1.0:
        return 0.0
    return 1.0


@atl_warper
def instant(t):
    return 1.0


def __getattr__(name):
    return missing_attribute("renpy.atl", name)
