"""The standard modules game code imports, where MicroPython's differ from
CPython's in ways Ren'Py's code depends on. Each is a proxy in sys.modules
that adds the missing pieces and passes everything else through.

- os: environ (a game on the 3DS has no environment variables, so it's
  empty) and path (stdlib/ospath.py).
- collections: defaultdict, which MicroPython only has in micropython-lib.
- random: stdlib/pyrandom.py, CPython's Random (MicroPython's random has
  only getrandbits and seed).

Modules with no place on the device (the updater's tarfile, threads, urllib, subprocess, zlib and codecs, the PC
engine's pygame_sdl2) are placeholders that report each use.
"""
import collections as _collections
import os as _os
import sys


_ABSENT = object()


class DefaultFactory:
    """defaultdict's lookup, for any dict class (renpy.revertable uses it too).

    MicroPython builds a built-in subclass's dict from the constructor's
    arguments and doesn't take a changed constructor or super().__getitem__
    well, so the factory is set after construction (see with_factory) and
    lookups go through get().
    """

    default_factory = None

    def __getitem__(self, key):
        value = self.get(key, _ABSENT)
        if value is _ABSENT:
            if self.default_factory is None:
                raise KeyError(key)
            value = self[key] = self.default_factory()
        return value


def with_factory(cls, default_factory, args, kwargs):
    d = cls(*args, **kwargs)
    d.default_factory = default_factory
    return d


class DefaultDict(DefaultFactory, dict):
    pass


def defaultdict(default_factory=None, *args, **kwargs):
    return with_factory(DefaultDict, default_factory, args, kwargs)


class _Proxy:
    def __init__(self, module, **extra):
        object.__setattr__(self, "_module", module)
        object.__setattr__(self, "_extra", extra)

    def __getattr__(self, name):
        try:
            return self._extra[name]
        except KeyError:
            return getattr(self._module, name)


def format(value, spec=""):
    """The format() built-in MicroPython lacks: a value's own __format__ if
    its class has one, else what str.format does with the spec."""
    method = getattr(type(value), "__format__", None)
    if method is not None:
        return method(value, spec)
    return ("{:" + spec + "}").format(value)


_ABSENT_MODULES = ("tarfile", "threading", "urllib", "urllib.parse", "urllib.request", "subprocess", "zlib", "codecs", "pygame_sdl2")


def install():
    import builtins
    builtins.format = format
    from renpy.missing import MissingModule
    for name in _ABSENT_MODULES:
        sys.modules[name] = MissingModule(name)
    import ospath
    import pyrandom
    sys.modules["random"] = pyrandom
    sys.modules["os"] = _Proxy(_os, environ={}, path=ospath)
    sys.modules["os.path"] = ospath
    sys.modules["collections"] = _Proxy(_collections, defaultdict=defaultdict)
