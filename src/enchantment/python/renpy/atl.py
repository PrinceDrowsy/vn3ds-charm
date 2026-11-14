"""ATL. Its trees are in the bundle and run in the C ATL VM (REWORK-PLAN
§7.4); what's here is the warper registry, which games extend from Python.
Python warpers are sampled into tables when lowered (§6.3)."""
from renpy import missing_attribute

warpers = {}


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
