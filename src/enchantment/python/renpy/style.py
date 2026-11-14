"""Styles (Ren'Py's style.pyx, which is compiled, so it can't run as shipped).

A style is a description (REWORK-PLAN §6.3): a name, a parent and the list
of property dicts assigned to it, in order, exactly what Ren'Py keeps and
pickles. Resolving them into per-prefix property values is lowering's job,
with the game's own property tables (renpy.styledata.stylesets); nothing
here computes a property's final value.
"""
import renpy
from renpy.styledata import stylesets

styles = {}  # name tuple -> style


def get_style(name):
    nametuple = (name,)
    rv = styles.get(nametuple)
    if rv is not None:
        return rv
    start, _mid, end = name.partition("_")
    if not end:
        raise Exception("Style %r does not exist." % name)
    # _foo_bar inherits from _bar, not bar.
    if not start:
        _start, _mid, end = name[1:].partition("_")
        if not end:
            raise Exception("Style %r does not exist." % name)
        end = "_" + end
    try:
        parent = get_style(end)
    except Exception:
        raise Exception("Style %r does not exist." % name)
    rv = styles[nametuple] = Style(parent, name=nametuple)
    return rv


def get_or_create_style(name):
    nametuple = (name,)
    rv = styles.get(nametuple)
    if rv is not None:
        return rv
    start, _mid, end = name.partition("_")
    # Both sides of the _, so _foo doesn't inherit from foo.
    if not start or not end:
        rv = styles[nametuple] = Style("default", name=nametuple)
        return rv
    rv = styles[nametuple] = Style(get_or_create_style(end), name=nametuple)
    return rv


def get_full_style(name):
    rv = styles.get(name)
    if rv is not None:
        return rv
    rv = get_style(name[0])
    for i in name[1:]:
        rv = rv[i]
    return rv


def get_tuple_name(s):
    if isinstance(s, StyleCore):
        return s.name
    if isinstance(s, tuple) or s is None:
        return s
    return (s,)


def get_text_style(style, default):
    if style is None:
        style = default
    style = get_tuple_name(style)
    rv = get_full_style((style[0] + "_text",))
    for i in style[1:]:
        rv = rv[i]
    return rv


class StyleManager(object):
    """The `style` object in the store."""

    def __setattr__(self, name, value):
        if not isinstance(value, StyleCore):
            if getattr(value, "_is_style_compat", False):
                self.__dict__[name] = value
                return
            raise Exception("Value is not a style.")
        name = (name,)
        if value.name is None:
            value.name = name
        styles[name] = value

    __setitem__ = __setattr__

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return get_style(name)

    __getitem__ = __getattr__

    def create(self, name, parent, description=None):
        self[name] = Style(parent, help=description)

    def rebuild(self):
        rebuild()

    def exists(self, name):
        return (name in styles) or ((name,) in styles)

    def get(self, name):
        if isinstance(name, tuple):
            return get_full_style(name)
        return get_style(name)


def style_name_to_string(name):
    if name is None:
        return "anonymous style"
    rv = "style " + name[0]
    for i in name[1:]:
        rv += "['{}']".format(i)
    return rv


_OWN = ("prefix", "properties", "parent", "name", "help")


class StyleCore(object):
    def __init__(self, parent, properties=None, name=None, help=None, heavy=True):
        object.__setattr__(self, "prefix", "insensitive_")
        object.__setattr__(self, "properties", [])
        if properties:
            if type(properties) is not dict:
                properties = dict(properties)
            self.properties.append(properties)
        object.__setattr__(self, "parent", get_tuple_name(parent))
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "help", help)

    def copy(self):
        rv = Style(self.parent)
        rv.properties = list(self.properties)
        return rv

    def __eq__(self, o):
        if self is o:
            return True
        return (type(self) is type(o) and self.parent == o.parent and self.name == o.name
                and self.properties == o.properties)

    def __ne__(self, o):
        return not self == o

    def __hash__(self):
        return id(self)

    def __repr__(self):
        if self.parent:
            return "<{} is {}>".format(style_name_to_string(self.name), style_name_to_string(self.parent))
        return "<{}>".format(style_name_to_string(self.name))

    def __getitem__(self, name):
        tname = self.name + (name,)
        rv = styles.get(tname)
        if rv is not None:
            return rv
        parent = self.parent + (name,) if self.parent is not None else None
        rv = styles[tname] = Style(parent, name=tname)
        return rv

    def setattr(self, property, value):
        self.properties.append({property: value})

    def delattr(self, property):
        for d in self.properties:
            if property in d:
                del d[property]

    def __setattr__(self, name, value):
        if name in _OWN:
            object.__setattr__(self, name, value)
            return
        if name not in stylesets.prefixed_all_properties:
            raise Exception("Style property {} is not known.".format(name))
        self.properties.append({name: value})

    def __delattr__(self, name):
        self.delattr(name)

    def set_parent(self, parent):
        self.parent = get_tuple_name(parent)

    def clear(self):
        self.properties = []

    def take(self, other):
        if not isinstance(other, StyleCore):
            other = get_style(other)
        self.properties = copy_properties(other.properties)

    def setdefault(self, **properties):
        for p in self.properties:
            for k in p:
                if k in properties:
                    del properties[k]
        if properties:
            self.properties.append(properties)

    def add_properties(self, properties):
        self.properties.append(dict(properties))

    def set_prefix(self, prefix):
        self.prefix = prefix


def copy_properties(p):
    return [dict(i) for i in p]


def reset():
    styles.clear()


def build_styles():
    # Building is resolution, which happens when the styles are lowered.
    for i in renpy.config.build_styles_callbacks:
        i()


def rebuild(prepare_screens=True):
    build_styles()


def backup():
    return dict((k, (v.parent, copy_properties(v.properties))) for k, v in styles.items())


def restore(o):
    for i in list(styles):
        if i not in o:
            del styles[i]
    for k, (parent, properties) in o.items():
        s = get_or_create_style(k[0])
        for i in k[1:]:
            s = s[i]
        s.clear()
        s.set_parent(parent)
        s.properties = copy_properties(properties)


from renpy.styledata.styleclass import Style  # noqa: E402
