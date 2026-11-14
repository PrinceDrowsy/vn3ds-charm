"""renpy.game: the running game's global state. The driver fills in what
Ren'Py's startup creates before init (persistent data, preferences)."""
from renpy import missing_attribute

persistent = None
preferences = None


def __getattr__(name):
    return missing_attribute("renpy.game", name)
