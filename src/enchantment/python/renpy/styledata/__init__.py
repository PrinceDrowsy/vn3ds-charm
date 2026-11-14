"""renpy.styledata: the style class and the property tables it checks
against. Ren'Py generates and compiles both; the tables come from the
game's own Ren'Py through the harvest (stylesets.load)."""
from renpy import submodule_or_missing


def import_style_functions():
    pass


def __getattr__(name):
    return submodule_or_missing("renpy.styledata", name)
