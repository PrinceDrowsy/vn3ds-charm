"""renpy.sl2.slparser. Registering a screen-language statement only teaches
Ren'Py's parser, which ran on the PC: the harvested screens already hold
each statement's displayable and arguments. So a registration here accepts
the same calls and chains, and keeps nothing."""
from renpy import missing_attribute


class Parser(object):
    def __init__(self, name):
        self.name = name

    def add_positional(self, name):
        return self

    def add_property(self, name):
        return self

    def add_style_property(self, name):
        return self

    def add_prefix_style_property(self, prefix, name):
        return self

    def add_property_group(self, group, prefix=''):
        return self

    def copy_properties(self, name):
        return self


class CustomParser(Parser):
    def __init__(self, name, positional=0, children="many", screen=None):
        Parser.__init__(self, name)


def register_sl_displayable(name, *args, **kwargs):
    return Parser(name)


def __getattr__(name):
    return missing_attribute("renpy.sl2.slparser", name)
