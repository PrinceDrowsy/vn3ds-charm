"""Transforms (renpy.display.transform). A Transform is a description:
its child and the state its properties set, kept as Ren'Py 7.0's
TransformState keeps them, so game code can read and change them. Running
ATL and drawing are the engine's (REWORK-PLAN §6.3, §7.4)."""
import math

import renpy
from renpy import missing_attribute
from renpy.display.layout import Container


null = None


def get_null():
    global null

    if null is None:
        null = renpy.display.layout.Null()

    return null


def cartesian_to_polar(x, y, xaround, yaround):

    dx = x - xaround
    dy = y - yaround

    radius = math.hypot(dx, dy)
    angle = math.atan2(dx, -dy) / math.pi * 180

    if angle < 0:
        angle += 360

    return angle, radius


def polar_to_cartesian(angle, radius, xaround, yaround):

    angle = angle * math.pi / 180

    dx = radius * math.sin(angle)
    dy = -radius * math.cos(angle)

    x = type(xaround)(xaround + dx)
    y = type(yaround)(yaround + dy)

    return x, y


def first_not_none(*args):

    for i in args:
        if i is not None:
            return i
    return i


class TransformState(renpy.object.Object):

    nearest = None
    xoffset = None
    yoffset = None
    inherited_xpos = None
    inherited_ypos = None
    inherited_xanchor = None
    inherited_yanchor = None
    transform_anchor = False
    additive = 0.0
    debug = None
    events = True
    crop_relative = False
    xpan = None
    ypan = None
    xtile = 1
    ytile = 1
    last_angle = None
    maxsize = None

    def __init__(self):
        self.alpha = 1
        self.nearest = None
        self.additive = 0.0
        self.rotate = None
        self.rotate_pad = True
        self.transform_anchor = False
        self.zoom = 1
        self.xzoom = 1
        self.yzoom = 1

        self.xpos = None
        self.ypos = None
        self.xanchor = None
        self.yanchor = None
        self.xoffset = 0
        self.yoffset = 0

        self.xaround = 0.0
        self.yaround = 0.0
        self.xanchoraround = 0.0
        self.yanchoraround = 0.0

        self.xpan = None
        self.ypan = None
        self.xtile = 1
        self.ytile = 1

        self.subpixel = False

        self.crop = None
        self.crop_relative = False
        self.corner1 = None
        self.corner2 = None
        self.size = None
        self.maxsize = None

        self.delay = 0

        self.debug = None
        self.events = True

        self.inherited_xpos = None
        self.inherited_ypos = None
        self.inherited_xanchor = None
        self.inherited_yanchor = None

    def take_state(self, ts):

        self.nearest = ts.nearest
        self.alpha = ts.alpha
        self.additive = ts.additive
        self.rotate = ts.rotate
        self.rotate_pad = ts.rotate_pad
        self.transform_anchor = ts.transform_anchor
        self.zoom = ts.zoom
        self.xzoom = ts.xzoom
        self.yzoom = ts.yzoom

        self.xaround = ts.xaround
        self.yaround = ts.yaround
        self.xanchoraround = ts.xanchoraround
        self.yanchoraround = ts.yanchoraround

        self.crop = ts.crop
        self.crop_relative = ts.crop_relative
        self.corner1 = ts.corner1
        self.corner2 = ts.corner2
        self.size = ts.size
        self.maxsize = ts.maxsize

        self.xpan = ts.xpan
        self.ypan = ts.ypan
        self.xtile = ts.xtile
        self.ytile = ts.ytile

        self.last_angle = ts.last_angle

        self.debug = ts.debug
        self.events = ts.events

        (self.inherited_xpos,
         self.inherited_ypos,
         self.inherited_xanchor,
         self.inherited_yanchor,
         _,
         _,
         _) = ts.get_placement()

        self.xoffset = ts.xoffset
        self.yoffset = ts.yoffset
        self.subpixel = ts.subpixel

    def diff(self, newts):

        rv = {}

        def diff2(prop, new, old):
            if new != old:
                rv[prop] = (old, new)

        def diff4(prop, new, inherited_new, old, inherited_old):
            if new is None:
                new_value = inherited_new
            else:
                new_value = new

            if old is None:
                old_value = inherited_old
            else:
                old_value = old

            if new_value != old_value:
                rv[prop] = (old_value, new_value)

        diff2("nearest", newts.nearest, self.nearest)
        diff2("alpha", newts.alpha, self.alpha)
        diff2("additive", newts.additive, self.additive)
        diff2("rotate", newts.rotate, self.rotate)
        diff2("rotate_pad", newts.rotate_pad, self.rotate_pad)
        diff2("transform_anchor", newts.transform_anchor, self.transform_anchor)
        diff2("zoom", newts.zoom, self.zoom)
        diff2("xzoom", newts.xzoom, self.xzoom)
        diff2("yzoom", newts.yzoom, self.yzoom)

        diff2("xaround", newts.xaround, self.xaround)
        diff2("yaround", newts.yaround, self.yaround)
        diff2("xanchoraround", newts.xanchoraround, self.xanchoraround)
        diff2("yanchoraround", newts.yanchoraround, self.yanchoraround)

        diff2("subpixel", newts.subpixel, self.subpixel)

        diff2("crop", newts.crop, self.crop)
        diff2("crop_relative", newts.crop_relative, self.crop_relative)
        diff2("corner1", newts.corner1, self.corner1)
        diff2("corner2", newts.corner2, self.corner2)
        diff2("size", newts.size, self.size)
        diff2("maxsize", newts.maxsize, self.maxsize)

        diff4("xpos", newts.xpos, newts.inherited_xpos, self.xpos, self.inherited_xpos)
        diff4("xanchor", newts.xanchor, newts.inherited_xanchor, self.xanchor, self.inherited_xanchor)
        diff2("xoffset", newts.xoffset, self.xoffset)

        diff4("ypos", newts.ypos, newts.inherited_ypos, self.ypos, self.inherited_ypos)
        diff4("yanchor", newts.yanchor, newts.inherited_yanchor, self.yanchor, self.inherited_yanchor)
        diff2("yoffset", newts.yoffset, self.yoffset)

        diff2("xpan", newts.xpan, self.xpan)
        diff2("ypan", newts.ypan, self.ypan)

        diff2("xtile", newts.xtile, self.xtile)
        diff2("ytile", newts.ytile, self.ytile)

        diff2("debug", newts.debug, self.debug)
        diff2("events", newts.events, self.events)

        return rv

    def get_placement(self, cxoffset=0, cyoffset=0):

        return (
            first_not_none(self.xpos, self.inherited_xpos),
            first_not_none(self.ypos, self.inherited_ypos),
            first_not_none(self.xanchor, self.inherited_xanchor),
            first_not_none(self.yanchor, self.inherited_yanchor),
            self.xoffset + cxoffset,
            self.yoffset + cyoffset,
            self.subpixel,
            )

    def get_xalign(self):
        return self.xpos

    def set_xalign(self, v):
        self.xpos = v
        self.xanchor = v

    xalign = property(get_xalign, set_xalign)

    def get_yalign(self):
        return self.ypos

    def set_yalign(self, v):
        self.ypos = v
        self.yanchor = v

    yalign = property(get_yalign, set_yalign)

    def get_around(self):
        return (self.xaround, self.yaround)

    def set_around(self, value):
        self.xaround, self.yaround = value
        self.xanchoraround, self.yanchoraround = None, None

    def set_alignaround(self, value):
        self.xaround, self.yaround = value
        self.xanchoraround, self.yanchoraround = value

    around = property(get_around, set_around)
    alignaround = property(get_around, set_alignaround)

    def get_angle(self):
        xpos = first_not_none(self.xpos, self.inherited_xpos, 0)
        ypos = first_not_none(self.ypos, self.inherited_ypos, 0)
        angle, _radius = cartesian_to_polar(xpos, ypos, self.xaround, self.yaround)
        return angle

    def get_radius(self):
        xpos = first_not_none(self.xpos, self.inherited_xpos, 0)
        ypos = first_not_none(self.ypos, self.inherited_ypos, 0)
        _angle, radius = cartesian_to_polar(xpos, ypos, self.xaround, self.yaround)
        return radius

    def set_angle(self, value):
        xpos = first_not_none(self.xpos, self.inherited_xpos, 0)
        ypos = first_not_none(self.ypos, self.inherited_ypos, 0)
        _angle, radius = cartesian_to_polar(xpos, ypos, self.xaround, self.yaround)
        angle = value
        self.xpos, self.ypos = polar_to_cartesian(angle, radius, self.xaround, self.yaround)

        if self.xanchoraround:
            self.xanchor, self.yanchor = polar_to_cartesian(angle, radius, self.xaround, self.yaround)

    def set_radius(self, value):
        xpos = first_not_none(self.xpos, self.inherited_xpos, 0)
        ypos = first_not_none(self.ypos, self.inherited_ypos, 0)
        angle, _radius = cartesian_to_polar(xpos, ypos, self.xaround, self.yaround)
        radius = value
        self.xpos, self.ypos = polar_to_cartesian(angle, radius, self.xaround, self.yaround)

        if self.xanchoraround:
            self.xanchor, self.yanchor = polar_to_cartesian(angle, radius, self.xaround, self.yaround)

    angle = property(get_angle, set_angle)
    radius = property(get_radius, set_radius)

    def get_pos(self):
        return self.xpos, self.ypos

    def set_pos(self, value):
        self.xpos, self.ypos = value

    pos = property(get_pos, set_pos)

    def get_anchor(self):
        return self.xanchor, self.yanchor

    def set_anchor(self, value):
        self.xanchor, self.yanchor = value

    anchor = property(get_anchor, set_anchor)

    def get_align(self):
        return self.xpos, self.ypos

    def set_align(self, value):
        self.xanchor, self.yanchor = value
        self.xpos, self.ypos = value

    align = property(get_align, set_align)

    def get_offset(self):
        return self.xoffset, self.yoffset

    def set_offset(self, value):
        self.xoffset, self.yoffset = value

    offset = property(get_offset, set_offset)

    def set_xcenter(self, value):
        self.xpos = value
        self.xanchor = 0.5

    def get_xcenter(self):
        return self.xpos

    def set_ycenter(self, value):
        self.ypos = value
        self.yanchor = 0.5

    def get_ycenter(self):
        return self.ypos

    xcenter = property(get_xcenter, set_xcenter)
    ycenter = property(get_ycenter, set_ycenter)


class Proxy(object):

    def __init__(self, name):
        self.name = name

    def __get__(self, instance, owner):
        return getattr(instance.state, self.name)

    def __set__(self, instance, value):
        return setattr(instance.state, self.name, value)


class Transform(Container):
    __version__ = 5
    transform_event_responder = True
    nearest = Proxy("nearest")
    alpha = Proxy("alpha")
    additive = Proxy("additive")
    rotate = Proxy("rotate")
    rotate_pad = Proxy("rotate_pad")
    transform_anchor = Proxy("transform_anchor")
    zoom = Proxy("zoom")
    xzoom = Proxy("xzoom")
    yzoom = Proxy("yzoom")
    xpos = Proxy("xpos")
    ypos = Proxy("ypos")
    xanchor = Proxy("xanchor")
    yanchor = Proxy("yanchor")
    xalign = Proxy("xalign")
    yalign = Proxy("yalign")
    around = Proxy("around")
    alignaround = Proxy("alignaround")
    angle = Proxy("angle")
    radius = Proxy("radius")
    xaround = Proxy("xaround")
    yaround = Proxy("yaround")
    xanchoraround = Proxy("xanchoraround")
    yanchoraround = Proxy("yanchoraround")
    pos = Proxy("pos")
    anchor = Proxy("anchor")
    align = Proxy("align")
    crop = Proxy("crop")
    crop_relative = Proxy("crop_relative")
    corner1 = Proxy("corner1")
    corner2 = Proxy("corner2")
    size = Proxy("size")
    maxsize = Proxy("maxsize")
    delay = Proxy("delay")
    xoffset = Proxy("xoffset")
    yoffset = Proxy("yoffset")
    offset = Proxy("offset")
    subpixel = Proxy("subpixel")
    xcenter = Proxy("xcenter")
    ycenter = Proxy("ycenter")
    xpan = Proxy("xpan")
    ypan = Proxy("ypan")
    xtile = Proxy("xtile")
    ytile = Proxy("ytile")
    debug = Proxy("debug")
    events = Proxy("events")

    DEFAULT_ARGUMENTS = {
        "selected_activate": {},
        "selected_hover": {},
        "selected_idle": {},
        "selected_insensitive": {},
        "activate": {},
        "hover": {},
        "idle": {},
        "insensitive": {},
        "": {},
        }
    active = False
    children = False
    arguments = DEFAULT_ARGUMENTS

    def __init__(self,
                 child=None,
                 function=None,
                 style="default",
                 focus=None,
                 default=False,
                 _args=None,
                 **kwargs):
        self.kwargs = kwargs
        self.style_arg = style
        super(Transform, self).__init__(style=style, focus=focus, default=default, _args=_args)
        self.function = function
        child = renpy.easy.displayable_or_none(child)
        if child is not None:
            self.add(child)
        self.state = TransformState()
        if kwargs:
            self.arguments = {}
            for k, v in kwargs.items():
                prefix = ""
                prop = k
                while True:
                    if prop in renpy.atl.PROPERTIES and (not prefix or prefix in Transform.DEFAULT_ARGUMENTS):
                        if prefix not in self.arguments:
                            self.arguments[prefix] = {}
                        self.arguments[prefix][prop] = v
                        break
                    new_prefix, _, prop = prop.partition("_")
                    if not prop:
                        raise Exception("Unknown transform property: %r" % k)
                    if prefix:
                        prefix = prefix + "_" + new_prefix
                    else:
                        prefix = new_prefix
            if "" in self.arguments:
                for k, v in self.arguments[""].items():
                    setattr(self.state, k, v)
        else:
            self.arguments = None
        self.forward = None
        self.active = False
        self.hide_request = False
        self.hide_response = True
        self.replaced_request = False
        self.replaced_response = True
        self.st = 0
        self.at = 0
        self.st_offset = 0
        self.at_offset = 0
        self.child_st_base = 0


class ATLTransform(Transform):
    """An ATL transform: the ATL tree already in the bundle, named by the
    node of the statement that defined it, and the context and parameters
    it's bound to."""

    def __init__(self, atl, child=None, context={}, parameters=None, **properties):
        self.atl = atl
        self.context = renpy.atl.Context(context)
        self.parameters = parameters  # the harvested signature, or None
        Transform.__init__(self, child=child, **properties)
        self.raw_child = self.child

    def _show(self):
        # Ren'Py computes the starting state here; that's the ATL VM's job,
        # when the transform is shown.
        pass


def __getattr__(name):
    return missing_attribute("renpy.display.transform", name)
