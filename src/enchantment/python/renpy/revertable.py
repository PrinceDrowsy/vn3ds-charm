"""The containers Ren'Py's stores use (renpy.revertable on 8.x, renpy.python
on 6.x/7.x): minstore binds list, dict, set, object, range and sorted to
these in every store, and Ren'Py's WrapNode wraps every literal in game code
with them.

Rollback doesn't need them to track changes (D19 snapshots the store), but
games rely on what they carry: Ren'Py 8 keeps Python 2's iteritems and
friends as aliases, and on a Python 2 game keys(), values() and items()
return lists. PY2 is set by the driver for Python 2 games.
"""

from charm_stdlib import DefaultFactory, with_factory

PY2 = False


class RevertableList(list):
    pass


class RevertableDict(dict):
    def keys(self):
        return list(super().keys()) if PY2 else super().keys()

    def values(self):
        return list(super().values()) if PY2 else super().values()

    def items(self):
        return list(super().items()) if PY2 else super().items()

    def iterkeys(self):
        return iter(super().keys())

    def itervalues(self):
        return iter(super().values())

    def iteritems(self):
        return iter(super().items())

    def has_key(self, key):
        return key in self


class _RevertableDefaultDict(DefaultFactory, RevertableDict):
    pass


def RevertableDefaultDict(default_factory=None, *args, **kwargs):
    return with_factory(_RevertableDefaultDict, default_factory, args, kwargs)


class RevertableSet(set):
    pass


class RevertableObject(object):
    pass


class MultiRevertable(object):
    pass


def revertable_range(*args):
    return RevertableList(range(*args))


def revertable_sorted(*args, **kwargs):
    return RevertableList(sorted(*args, **kwargs))
