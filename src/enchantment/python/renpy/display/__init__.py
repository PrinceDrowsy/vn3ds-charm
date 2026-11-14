"""renpy.display: the description classes of REWORK-PLAN §6.3, at Ren'Py's
own module paths. Modules the shim doesn't have yet are placeholders."""
from renpy import submodule_or_missing


def __getattr__(name):
    return submodule_or_missing("renpy.display", name)
