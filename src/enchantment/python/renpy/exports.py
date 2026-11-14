"""renpy.exports, what game code calls `renpy`. Ren'Py also copies all of its
own modules into it, so `renpy.display` works from game code; names the shim
doesn't have resolve to submodules or placeholders."""
import _charm
import renpy
from renpy import submodule_or_missing


def image(name, d):
    if d is None:
        raise Exception("Images may not be declared to be None.")
    if not isinstance(name, tuple):
        name = tuple(name.split())
    _charm.image(name, renpy.easy.displayable(d))


def has_image(name, exact=False):
    if not isinstance(name, tuple):
        name = tuple(name.split())
    while name:
        if _charm.has_image(name):
            return True
        if exact:
            return False
        name = name[:-1]
    return False


image_exists = has_image


def has_screen(name):
    # Ren'Py also checks the screen's variant against config.variants; the
    # harvest doesn't carry variants until screens arrive (R5).
    if not isinstance(name, tuple):
        name = tuple(name.split())
    return bool(name) and _charm.has_screen(name[0])


def __getattr__(name):
    return submodule_or_missing("renpy", name)
