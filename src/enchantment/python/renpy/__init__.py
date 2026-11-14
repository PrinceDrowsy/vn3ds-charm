"""Enchantment's stand-in for the `renpy` package (REWORK-PLAN §6).

Games and Ren'Py's own common scripts run unmodified on top of it; it
replaces only Ren'Py's engine underneath. Names it doesn't provide yet come
back as recording placeholders (see missing.py).
"""
import sys

from renpy import missing


def submodule_or_missing(package, name):
    """A real submodule if the shim has one, else a placeholder. Ren'Py
    imports all its submodules at startup, so `renpy.display` works without
    an import there too."""
    full = package + "." + name
    try:
        __import__(full)
    except ImportError:
        return missing.Missing(full)
    return sys.modules[full]


def __getattr__(name):
    return submodule_or_missing("renpy", name)
