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


def has_label(name):
    return _charm.has_label(name)


def write_log(s, *args):
    _charm.write_log(s % args if args else s)


def fsencode(s):
    return s


# What the engine does when the game runs. Game code binds these during
# init (keymaps, config callbacks); calling one is an interaction, which
# can't happen at convert time.

def display_menu(items, **kwargs):
    return _charm.engine("display_menu", items, **kwargs)


def predict_menu():
    return []


def rollback(force=False, checkpoints=1, defer=False, greedy=True, label=None, abnormal=True, current_label=None):
    return _charm.engine("rollback", force=force, checkpoints=checkpoints, defer=defer, greedy=greedy, label=label,
                         abnormal=abnormal, current_label=current_label)


def toggle_fullscreen():
    return _charm.engine("toggle_fullscreen")


def quit_event():
    return _charm.engine("quit_event")


def iconify():
    return _charm.engine("iconify")


def call_in_new_context(label, *args, **kwargs):
    return _charm.engine("call_in_new_context", label, *args, **kwargs)


def invoke_in_new_context(callable, *args, **kwargs):
    return _charm.engine("invoke_in_new_context", callable, *args, **kwargs)


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
    "random": ("renpy.python", "rng"),
    "Keymap": ("renpy.display.behavior", "Keymap"),
    "show_display_say": ("renpy.character", "show_display_say"),
    "predict_show_display_say": ("renpy.character", "predict_show_display_say"),
    "register_sl_statement": ("renpy.sl2.slparser", "CustomParser"),
    "register_sl_displayable": ("renpy.sl2.slparser", "register_sl_displayable"),
    "get_available_image_tags": ("renpy.display.image", "get_available_image_tags"),
    "music": ("renpy.audio.music", None),
    "sound": ("renpy.audio.sound", None),
}


# Curried forms, made when first used: renpy.curry loads from the game's
# source after this module.
_CURRIED = {"curried_call_in_new_context": call_in_new_context,
            "curried_invoke_in_new_context": invoke_in_new_context}


def __getattr__(name):
    if name in _CURRIED:
        value = globals()[name] = renpy.curry.curry(_CURRIED[name])
        return value
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
