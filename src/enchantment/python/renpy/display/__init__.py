"""renpy.display: not in the shim yet; names resolve to submodules or placeholders."""
from renpy import submodule_or_missing


def __getattr__(name):
    return submodule_or_missing("renpy.display", name)
