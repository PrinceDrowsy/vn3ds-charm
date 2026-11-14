"""Stores (Ren'Py's renpy.python): each store is a dict that game code runs
in, reachable as a module (`import store.gui`, `from store import x`) and as
an attribute of its parent store. Ren'Py 6.x/7.x also keep the revertable
containers here, where their minstore imports them from."""
import sys

from renpy import submodule_or_missing
from renpy.revertable import (RevertableDict, RevertableList, RevertableObject, RevertableSet,  # noqa: F401
                              revertable_range, revertable_sorted)

store_dicts = {}


class StoreModule:
    """A module backed by a dict: the stores, and Ren'Py's own modules the
    shim runs from the game's source (minstore, defaultstore)."""

    def __init__(self, d):
        object.__setattr__(self, "_dict", d)

    def __getattr__(self, name):
        try:
            return self._dict[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self._dict[name] = value

    def __delattr__(self, name):
        del self._dict[name]


def create_store(name):
    """The dict for store `name` ("store", "store.gui", ...), created with its
    parents on first use, starting with minstore's names as in Ren'Py."""
    d = store_dicts.get(name)
    if d is not None:
        return d
    parent, _, var = name.rpartition(".")
    if parent:
        create_store(parent)
    d = store_dicts[name] = {"__name__": name, "__package__": name}
    for k, v in sys.modules["renpy.minstore"]._dict.items():
        if k not in d:
            d[k] = v
    sys.modules[name] = StoreModule(d)
    if parent:
        store_dicts[parent][var] = sys.modules[name]
    return d


def store_eval(expr, globals=None, locals=None):
    if globals is None:
        globals = store_dicts["store"]
    return eval(expr, globals, locals)


def py_eval(source, globals=None, locals=None):
    # Ren'Py wraps literals in code compiled at run time too; without a
    # parser on the device, run-time strings are evaluated as they are.
    return store_eval(source, globals, locals)


def __getattr__(name):
    return submodule_or_missing("renpy.python", name)
