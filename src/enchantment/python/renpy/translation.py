"""renpy.translation. Strings stay in the game's own language until the
shim carries translations (REWORK-PLAN §8.10)."""
from renpy import missing_attribute


def translate_string(s, language=None):
    return s


def __getattr__(name):
    return missing_attribute("renpy.translation", name)
