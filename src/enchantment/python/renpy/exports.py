"""renpy.exports, what game code calls `renpy`. Ren'Py also copies all of its
own modules into it, so `renpy.display` works from game code; names the shim
doesn't have resolve to submodules or placeholders."""
import sys

import _charm
import renpy
from renpy import submodule_or_missing
from renpy.atl import atl_warper  # noqa: F401


def image(name, d):
    if d is None:
        raise Exception("Images may not be declared to be None.")
    if not isinstance(name, tuple):
        name = tuple(name.split())
    renpy.display.image.register_image(name, renpy.easy.displayable(d))


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


def register_statement(*args, **kwargs):
    # renpy.statements runs from the game's source, loaded after this module.
    return renpy.statements.register(*args, **kwargs)


def variant(name):
    if isinstance(name, str):
        return name in renpy.config.variants
    for n in name:
        if n in renpy.config.variants:
            return True
    return False


def pure(fn):
    # Marks for Ren'Py's static analysis, which only its image prediction
    # uses; the engine predicts from the node graph (§11).
    return fn


def const(name):
    pass


def not_const(name):
    pass


class Displayable(renpy.display.core.Displayable, renpy.python.RevertableObject):
    pass


class Container(renpy.display.core.Displayable, renpy.python.RevertableObject):
    _list_type = renpy.python.RevertableList


def list_files(common=False):
    return _charm.list_files(common)


def loadable(filename):
    return _charm.loadable(filename)


# Names Ren'Py's exports imports from its other modules, as (module, name
# there, or None for the module itself). Looked up when used, since several
# of those modules load from the game's source after this one.
_IMPORTED = {
    "ParameterizedText": ("renpy.text.extras", "ParameterizedText"),
    "curry": ("renpy.curry", "curry"),
    "partial": ("renpy.curry", "partial"),
    "displayable": ("renpy.easy", "displayable"),
    "split_properties": ("renpy.easy", "split_properties"),
    "predict": ("renpy.easy", "predict"),
    "register_persistent": ("renpy.persistent", "register_persistent"),
    "eval": ("renpy.python", "py_eval"),
    "music": ("renpy.audio.music", None),
    "sound": ("renpy.audio.sound", None),
}


def __getattr__(name):
    if name in _IMPORTED:
        module, attr = _IMPORTED[name]
        __import__(module)
        module = sys.modules[module]
        return module if attr is None else getattr(module, attr)
    # Ren'Py copies its package's globals (platform flags, submodules) into
    # exports, under exports' own names.
    if name in renpy.__dict__:
        return renpy.__dict__[name]
    return submodule_or_missing("renpy", name)
