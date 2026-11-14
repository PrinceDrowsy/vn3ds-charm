"""renpy.text: text descriptions. Layout and glyphs are the engine's
(REWORK-PLAN §8.4)."""
from renpy import submodule_or_missing


def __getattr__(name):
    return submodule_or_missing("renpy.text", name)
