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
    changed()
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
        changed()
        return rv
    rv = styles[nametuple] = Style(get_or_create_style(end), name=nametuple)
    changed()
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
        changed()
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
        changed()
        return rv

    def setattr(self, property, value):
        changed()
        self.properties.append({property: value})

    def delattr(self, property):
        changed()
        for d in self.properties:
            if property in d:
                del d[property]

    def __setattr__(self, name, value):
        if name in _OWN:
            object.__setattr__(self, name, value)
            return
        if name not in stylesets.prefixed_all_properties:
            raise Exception("Style property {} is not known.".format(name))
        changed()
        self.properties.append({name: value})

    def __getattr__(self, name):
        # A property read gives its value for the style's current prefix,
        # as Ren'Py's generated accessors do.
        targets = _targets()
        if name in targets:
            return self._get(self.prefix + name)
        raise AttributeError(name)

    def _get(self, key):
        """`key` (a prefixed target property) from this style, its parent,
        or for an indexed style the style it indexes, as Ren'Py's _get
        walks them."""
        s = self
        left = None
        for _ in range(100):
            cache = build_style(s)
            if key in cache:
                return cache[key]
            if left is None and s.name is not None and len(s.name) > 1:
                left = get_full_style(s.name[:-1])
            s = get_full_style(s.parent) if s.parent is not None else None
            if s is None:
                s = left
                left = None
            if s is None:
                return None
        raise Exception("{} is too complex. Check for loops in style inheritance.".format(self))

    def __delattr__(self, name):
        self.delattr(name)

    def set_parent(self, parent):
        changed()
        self.parent = get_tuple_name(parent)

    def clear(self):
        changed()
        self.properties = []

    def take(self, other):
        if not isinstance(other, StyleCore):
            other = get_style(other)
        changed()
        self.properties = copy_properties(other.properties)

    def setdefault(self, **properties):
        for p in self.properties:
            for k in p:
                if k in properties:
                    del properties[k]
        if properties:
            changed()
            self.properties.append(properties)

    def add_properties(self, properties):
        changed()
        self.properties.append(dict(properties))

    def set_prefix(self, prefix):
        self.prefix = prefix


def _targets():
    global _target_set
    if _target_set is None:
        _target_set = set(t for rule in stylesets.rules.values() for t, _source, _f in rule)
    return _target_set


_target_set = None


def _split(name):
    """A prefixed property name as (prefix, property), or None."""
    for prefix in sorted(stylesets.prefix_priority, key=len, reverse=True):
        if name.startswith(prefix) and name[len(prefix):] in stylesets.rules:
            return prefix, name[len(prefix):]
    return None


def _convert(function, value):
    if function is None:
        return value
    if function == "expand_anchor":
        return renpy.styledata.styleutil.expand_anchor(value)
    if function == "color":
        return renpy.easy.color(value)
    if function == "displayable_or_none":
        return renpy.easy.displayable_or_none(value)
    return getattr(renpy.styledata.styleutil, function)(value)


# Bumped by every change to any style; a style's built values are reused
# until it moves.
generation = 0


def changed():
    global generation
    generation += 1


def build_style(s):
    """The values a style's own property dicts set, by prefixed target
    property, with Ren'Py's priorities: a later dict wins over an earlier
    one, and within a dict a more specific prefix or property wins."""
    built = s.__dict__.get("__built")
    if built is not None and built[0] == generation:
        return built[1]
    cache = {}
    priorities = {}
    priority = 1
    for d in s.properties:
        for k, v in d.items():
            split = _split(k)
            if split is None:
                continue
            prefix, prop = split
            p = priority + stylesets.prefix_priority[prefix] + stylesets.property_priority.get(prop, 0)
            for target, source, function in stylesets.rules[prop]:
                if isinstance(source, dict):
                    value = source["const"]
                else:
                    value = _convert(function, v if source == "value" else v[source])
                for alt in stylesets.prefix_alts[prefix]:
                    key = alt + target
                    if p >= priorities.get(key, 0):
                        cache[key] = value
                        priorities[key] = p
        priority += stylesets.priority_levels
    # Kept out of the snapshot: the dumper skips dunder names.
    object.__setattr__(s, "__built", (generation, cache))
    return cache


def copy_properties(p):
    return [dict(i) for i in p]


def reset():
    changed()
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
    changed()
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
