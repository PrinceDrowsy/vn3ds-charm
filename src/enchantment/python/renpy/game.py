"""renpy.game: the running game's global state. The driver fills in what
Ren'Py's startup creates before init (persistent data, preferences)."""
import _charm
from renpy import missing_attribute

persistent = None
preferences = None
post_init = []  # functions run once init is over
less_updates = False  # Ren'Py's --less-updates, for screen readers


def call_in_new_context(label, *args, **kwargs):
    return _charm.engine("call_in_new_context", label, *args, **kwargs)


def invoke_in_new_context(callable, *args, **kwargs):
    return _charm.engine("invoke_in_new_context", callable, *args, **kwargs)


def __getattr__(name):
    return missing_attribute("renpy.game", name)
