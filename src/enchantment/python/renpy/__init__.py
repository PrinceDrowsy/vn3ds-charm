"""Enchantment's stand-in for the `renpy` package (REWORK-PLAN §6).

Games and Ren'Py's own common scripts run unmodified on top of it; it
replaces only Ren'Py's engine underneath. Names it doesn't provide yet come
back as recording placeholders (see missing.py).
"""
import sys

from renpy import missing


def submodule_or_missing(package, name):
    """For a package's __getattr__: a real submodule if the shim has one, else
    a placeholder. Ren'Py imports all its submodules at startup, so
    `renpy.display` works without an import there too. Dunder names are never
    placeholders: the import machinery and hasattr() probe for them."""
    if name.startswith("__"):
        raise AttributeError(name)
    full = package + "." + name
    try:
        __import__(full)
    except ImportError:
        return missing.Missing(full)
    return sys.modules[full]


def missing_attribute(module, name):
    """For a plain module's __getattr__ (no submodules to look for)."""
    if name.startswith("__"):
        raise AttributeError(name)
    return missing.Missing(module + "." + name)


def __getattr__(name):
    return submodule_or_missing("renpy", name)
