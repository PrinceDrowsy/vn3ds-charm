"""renpy.display.motion: Ren'Py's older motion displayables (Motion, Pan,
Move, Revolve and the zooms), as descriptions. A Motion's function is a
callback slot (REWORK-PLAN §6.3); Interpolate and Revolver are those
functions, as Ren'Py 7.0 computes them."""
import math

import renpy
from renpy import missing_attribute
from renpy.display.layout import Container
from renpy.display.transform import ATLTransform, Transform  # noqa: F401


class Motion(Container):
    def __init__(self, function, period, child=None, new_widget=None, old_widget=None, repeat=False, bounce=False, delay=None, anim_timebase=False, tag_start=None, time_warp=None, add_sizes=False, style='motion', **properties):
        if child is None:
            child = new_widget
        if delay is None and not repeat:
            delay = period
        super(Motion, self).__init__(style=style, **properties)
        if child is not None:
            self.add(child)
        self.function = function
        self.period = period
        self.repeat = repeat
        self.bounce = bounce
        self.delay = delay
        self.anim_timebase = anim_timebase
        self.time_warp = time_warp
        self.add_sizes = add_sizes
        self.position = None



class Interpolate(object):
    anchors = {
        'top': 0.0,
        'center': 0.5,
        'bottom': 1.0,
        'left': 0.0,
        'right': 1.0,
        }
    def __init__(self, start, end):
        if len(start) != len(end):
            raise Exception("The start and end must have the same number of arguments.")
        self.start = [self.anchors.get(i, i) for i in start]
        self.end = [self.anchors.get(i, i) for i in end]
    def __call__(self, t, sizes=(None, None, None, None)):
        types = (renpy.atl.position,) * len(self.start)
        return renpy.atl.interpolate(t, tuple(self.start), tuple(self.end), types)


def Pan(startpos, endpos, time, child=None, repeat=False, bounce=False,
        anim_timebase=False, style='motion', time_warp=None, **properties):
    x0, y0 = startpos
    x1, y1 = endpos
    return Motion(Interpolate((-x0, -y0), (-x1, -y1)),
                  time,
                  child,
                  repeat=repeat,
                  bounce=bounce,
                  style=style,
                  anim_timebase=anim_timebase,
                  time_warp=time_warp,
                  **properties)


def Move(startpos, endpos, time, child=None, repeat=False, bounce=False,
         anim_timebase=False, style='motion', time_warp=None, **properties):
    return Motion(Interpolate(startpos, endpos),
                  time,
                  child,
                  repeat=repeat,
                  bounce=bounce,
                  anim_timebase=anim_timebase,
                  style=style,
                  time_warp=time_warp,
                  **properties)


class Revolver(object):
    def __init__(self, start, end, child, around=(0.5, 0.5), cor=(0.5, 0.5), pos=None):
        self.start = start
        self.end = end
        self.around = around
        self.cor = cor
        self.pos = pos
        self.child = child
    def __call__(self, t, rect):
        (w, h, cw, ch) = rect
        def fti(x, r):
            if x is None:
                x = 0
            if isinstance(x, float):
                return int(x * r)
            else:
                return x
        if self.pos is None:
            pos = self.child.get_placement()
        else:
            pos = self.pos
        xpos, ypos, xanchor, yanchor, _xoffset, _yoffset, _subpixel = pos
        xpos = fti(xpos, w)
        ypos = fti(ypos, h)
        xanchor = fti(xanchor, cw)
        yanchor = fti(yanchor, ch)
        xaround, yaround = self.around
        xaround = fti(xaround, w)
        yaround = fti(yaround, h)
        xcor, ycor = self.cor
        xcor = fti(xcor, cw)
        ycor = fti(ycor, ch)
        angle = self.start + (self.end - self.start) * t
        angle *= math.pi / 180
        x = xpos - xanchor + xcor - xaround
        y = ypos - yanchor + ycor - yaround
        nx = x * math.cos(angle) - y * math.sin(angle)
        ny = x * math.sin(angle) + y * math.cos(angle)
        nx = nx - xcor + xaround
        ny = ny - ycor + yaround
        return (renpy.display.core.absolute(nx), renpy.display.core.absolute(ny), 0, 0)


def Revolve(start, end, time, child, around=(0.5, 0.5), cor=(0.5, 0.5), pos=None, **properties):
    return Motion(Revolver(start, end, child, around=around, cor=cor, pos=pos),
                  time,
                  child,
                  add_sizes=True,
                  **properties)


class ZoomCommon(renpy.display.core.Displayable):
    def __init__(self,
                 time, child,
                 end_identity=False,
                 after_child=None,
                 time_warp=None,
                 bilinear=True,
                 opaque=True,
                 anim_timebase=False,
                 repeat=False,
                 style='motion',
                 **properties):
        super(ZoomCommon, self).__init__(style=style, **properties)
        child = renpy.easy.displayable(child)
        self.time = time
        self.child = child
        self.repeat = repeat
        if after_child:
            self.after_child = renpy.easy.displayable(after_child)
        else:
            if end_identity:
                self.after_child = child
            else:
                self.after_child = None
        self.time_warp = time_warp
        self.bilinear = bilinear
        self.opaque = opaque
        self.anim_timebase = anim_timebase



class Zoom(ZoomCommon):
    def __init__(self, size, start, end, time, child, **properties):
        end_identity = (end == (0.0, 0.0) + size)
        super(Zoom, self).__init__(time, child, end_identity=end_identity, **properties)
        self.size = size
        self.start = start
        self.end = end



class FactorZoom(ZoomCommon):
    def __init__(self, start, end, time, child, **properties):
        end_identity = (end == 1.0)
        super(FactorZoom, self).__init__(time, child, end_identity=end_identity, **properties)
        self.start = start
        self.end = end



class SizeZoom(ZoomCommon):
    def __init__(self, start, end, time, child, **properties):
        end_identity = False
        super(SizeZoom, self).__init__(time, child, end_identity=end_identity, **properties)
        self.start = start
        self.end = end



class RotoZoom(renpy.display.core.Displayable):
    transform = None
    def __init__(self,
                 rot_start,
                 rot_end,
                 rot_delay,
                 zoom_start,
                 zoom_end,
                 zoom_delay,
                 child,
                 rot_repeat=False,
                 zoom_repeat=False,
                 rot_bounce=False,
                 zoom_bounce=False,
                 rot_anim_timebase=False,
                 zoom_anim_timebase=False,
                 rot_time_warp=None,
                 zoom_time_warp=None,
                 opaque=False,
                 style='motion',
                 **properties):
        super(RotoZoom, self).__init__(style=style, **properties)
        self.rot_start = rot_start
        self.rot_end = rot_end
        self.rot_delay = rot_delay
        self.zoom_start = zoom_start
        self.zoom_end = zoom_end
        self.zoom_delay = zoom_delay
        self.child = renpy.easy.displayable(child)
        self.rot_repeat = rot_repeat
        self.zoom_repeat = zoom_repeat
        self.rot_bounce = rot_bounce
        self.zoom_bounce = zoom_bounce
        self.rot_anim_timebase = rot_anim_timebase
        self.zoom_anim_timebase = zoom_anim_timebase
        self.rot_time_warp = rot_time_warp
        self.zoom_time_warp = zoom_time_warp
        self.opaque = opaque


def __getattr__(name):
    return missing_attribute("renpy.display.motion", name)
