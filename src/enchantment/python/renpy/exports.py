"""renpy.exports, what game code calls `renpy`. Ren'Py also copies all of its
own modules into it, so `renpy.display` works from game code; names the shim
doesn't have resolve to submodules or placeholders."""
from renpy import submodule_or_missing


def __getattr__(name):
    return submodule_or_missing("renpy", name)
