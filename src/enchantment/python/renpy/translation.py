"""renpy.translation. Strings stay in the game's own language until the
shim carries translations (REWORK-PLAN §8.10)."""
from renpy import submodule_or_missing


def translate_string(s, language=None):
    return s


def __getattr__(name):
    return submodule_or_missing("renpy.translation", name)
