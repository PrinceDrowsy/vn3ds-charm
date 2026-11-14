"""The base of every displayable description (REWORK-PLAN §6.3). The
constructors here and in the other renpy.display modules follow the public
behaviour of Ren'Py's own (MIT, Copyright 2004-2018 Tom Rothamel), keeping
the attributes games read and write; drawing is the engine's."""
import copy

import renpy
from renpy import missing_attribute


class DisplayableArguments(renpy.object.Object):
    """The arguments a duplicated displayable was given (image attributes
    passed down to a DynamicImage or LayeredImage)."""

    name = ()
    args = ()
    consumed = False
    prefix = None

    def copy(self, **kwargs):
        rv = DisplayableArguments()
        rv.__dict__.update(self.__dict__)
        rv.__dict__.update(kwargs)
        return rv


class absolute(float):
    """An absolute float coordinate: pixels, not a fraction."""
    __slots__ = []


default_style = renpy.style.Style("default")


class Displayable(renpy.object.Object):
    focusable = None
    full_focus_name = None
    role = ''
    transform_event = None
    transform_event_responder = False
    _main = None
    _composite_parts = []
    _location = None
    _uses_scope = False
    _args = DisplayableArguments()
    _duplicatable = False
    _clipping = False
    _tooltip = None

    def __init__(self, focus=None, default=False, style='default', _args=None, tooltip=None, **properties):
        if style == "default" and not properties:
            self.style = default_style
        else:
            self.style = renpy.style.Style(style, properties)
        self.focus_name = focus
        self.default = default
        self._tooltip = tooltip
        if _args is not None:
            self._args = _args

    def _equals(self, o):
        if type(self) is not type(o):
            return False
        if self.focus_name != o.focus_name:
            return False
        if self.style != o.style:
            return False
        if self.default != o.default:
            return False
        return True

    def _copy(self, args=None):
        rv = copy.copy(self)
        if args is not None:
            rv._args = args
        return rv

    def _duplicate(self, args):
        return self

    def _in_current_store(self):
        return self

    def _unique(self):
        return

    def _target(self):
        return self


def __getattr__(name):
    return missing_attribute("renpy.display.core", name)
