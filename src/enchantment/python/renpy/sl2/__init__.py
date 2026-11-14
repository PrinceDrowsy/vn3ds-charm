"""renpy.sl2: screen language. Screens arrive parsed, as the harvest's SL2
trees (REWORK-PLAN §8.5)."""
from renpy import submodule_or_missing


def __getattr__(name):
    return submodule_or_missing("renpy.sl2", name)
