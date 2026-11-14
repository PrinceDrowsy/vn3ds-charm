"""Transitions (renpy.display.transition): descriptions the engine runs
between two scenes (REWORK-PLAN §7.4). Constructors as Ren'Py 7.0's."""
import renpy
from renpy import missing_attribute


class Transition(renpy.display.core.Displayable):
    def __init__(self, delay, **properties):
        super(Transition, self).__init__(**properties)
        self.delay = delay
        self.events = True


class NoTransition(Transition):
    def __init__(self, delay, old_widget=None, new_widget=None, **properties):
        super(NoTransition, self).__init__(delay, **properties)
        self.old_widget = old_widget
        self.new_widget = new_widget
        self.events = True


class MultipleTransition(Transition):
    def __init__(self, args, old_widget=None, new_widget=None, **properties):
        if len(args) % 2 != 1 or len(args) < 3:
            raise Exception("MultipleTransition requires an odd number of arguments, and at least 3 arguments.")
        self.transitions = []
        self.screens = [ renpy.easy.displayable(i) for i in args[0::2] ]
        def oldnew(w):
            if w is False:
                return old_widget
            if w is True:
                return new_widget
            return w
        for old, trans, new in zip(self.screens[0:], args[1::2], self.screens[1:]):
            old = oldnew(old)
            new = oldnew(new)
            self.transitions.append(trans(old_widget=old, new_widget=new))
        super(MultipleTransition, self).__init__(sum([i.delay for i in self.transitions]), **properties)
        self.new_widget = self.transitions[-1]
        self.events = False


def Fade(out_time,
         hold_time,
         in_time,
         old_widget=None,
         new_widget=None,
         color=None,
         widget=None,
         alpha=False,
         ):
    dissolve = renpy.curry.curry(Dissolve)
    notrans = renpy.curry.curry(NoTransition)
    widget = renpy.easy.displayable_or_none(widget)
    if color:
        widget = renpy.display.image.Solid(color)
    if not widget:
        widget = renpy.display.image.Solid((0, 0, 0, 255))
    args = [ False, dissolve(out_time, alpha=alpha), widget ]
    if hold_time:
        args.extend([ notrans(hold_time), widget, ])
    args.extend([dissolve(in_time, alpha=alpha), True ])
    return MultipleTransition(args, old_widget=old_widget, new_widget=new_widget)


class Pixellate(Transition):
    def __init__(self, time, steps, old_widget=None, new_widget=None, **properties):
        time = float(time)
        super(Pixellate, self).__init__(time, **properties)
        self.time = time
        self.steps = steps
        self.old_widget = old_widget
        self.new_widget = new_widget
        self.events = False
        self.quantum = time / (2 * steps)


class Dissolve(Transition):
    __version__ = 1
    def __init__(self, time, old_widget=None, new_widget=None, alpha=False, time_warp=None, **properties):
        super(Dissolve, self).__init__(time, **properties)
        self.time = time
        self.old_widget = old_widget
        self.new_widget = new_widget
        self.events = False
        self.alpha = alpha
        self.time_warp = time_warp


class ImageDissolve(Transition):
    __version__ = 1
    def __init__(
            self,
            image,
            time,
            ramplen=8,
            ramptype='linear',
            ramp=None,
            reverse=False,
            alpha=False,
            old_widget=None,
            new_widget=None,
            time_warp=None,
            **properties):
        super(ImageDissolve, self).__init__(time, **properties)
        self.old_widget = old_widget
        self.new_widget = new_widget
        self.events = False
        self.alpha = alpha
        self.time_warp = time_warp
        if not reverse:
            matrix = renpy.display.im.matrix(
                0, 0, 0, 0, 1,
                0, 0, 0, 0, 1,
                0, 0, 0, 0, 1,
                1, 0, 0, 0, 0)
        else:
            matrix = renpy.display.im.matrix(
                0, 0, 0, 0, 1,
                0, 0, 0, 0, 1,
                0, 0, 0, 0, 1,
                - 1, 0, 0, 0, 1)
        self.image = renpy.display.im.MatrixColor(image, matrix)
        if ramp is not None:
            ramplen = len(ramp)
        self.ramplen = max(ramplen, 1)


class AlphaDissolve(Transition):
    def __init__(
            self,
            control,
            delay=0.0,
            old_widget=None,
            new_widget=None,
            alpha=False,
            reverse=False,
            **properties):
        super(AlphaDissolve, self).__init__(delay, **properties)
        self.control = renpy.display.layout.Fixed()
        self.control.add(control)
        self.old_widget = renpy.easy.displayable(old_widget)
        self.new_widget = renpy.easy.displayable(new_widget)
        self.events = False
        self.alpha = alpha
        self.reverse = reverse


class CropMove(Transition):
    def __init__(self, time,
                 mode="slideright",
                 startcrop=(0.0, 0.0, 0.0, 1.0),
                 startpos=(0.0, 0.0),
                 endcrop=(0.0, 0.0, 1.0, 1.0),
                 endpos=(0.0, 0.0),
                 topnew=True,
                 old_widget=None,
                 new_widget=None,
                 **properties):
        super(CropMove, self).__init__(time, **properties)
        self.time = time
        if mode == "wiperight":
            startpos = (0.0, 0.0)
            startcrop = (0.0, 0.0, 0.0, 1.0)
            endpos = (0.0, 0.0)
            endcrop = (0.0, 0.0, 1.0, 1.0)
            topnew = True
        elif mode == "wipeleft":
            startpos = (1.0, 0.0)
            startcrop = (1.0, 0.0, 0.0, 1.0)
            endpos = (0.0, 0.0)
            endcrop = (0.0, 0.0, 1.0, 1.0)
            topnew = True
        elif mode == "wipedown":
            startpos = (0.0, 0.0)
            startcrop = (0.0, 0.0, 1.0, 0.0)
            endpos = (0.0, 0.0)
            endcrop = (0.0, 0.0, 1.0, 1.0)
            topnew = True
        elif mode == "wipeup":
            startpos = (0.0, 1.0)
            startcrop = (0.0, 1.0, 1.0, 0.0)
            endpos = (0.0, 0.0)
            endcrop = (0.0, 0.0, 1.0, 1.0)
            topnew = True
        elif mode == "slideright":
            startpos = (0.0, 0.0)
            startcrop = (1.0, 0.0, 0.0, 1.0)
            endpos = (0.0, 0.0)
            endcrop = (0.0, 0.0, 1.0, 1.0)
            topnew = True
        elif mode == "slideleft":
            startpos = (1.0, 0.0)
            startcrop = (0.0, 0.0, 0.0, 1.0)
            endpos = (0.0, 0.0)
            endcrop = (0.0, 0.0, 1.0, 1.0)
            topnew = True
        elif mode == "slideup":
            startpos = (0.0, 1.0)
            startcrop = (0.0, 0.0, 1.0, 0.0)
            endpos = (0.0, 0.0)
            endcrop = (0.0, 0.0, 1.0, 1.0)
            topnew = True
        elif mode == "slidedown":
            startpos = (0.0, 0.0)
            startcrop = (0.0, 1.0, 1.0, 0.0)
            endpos = (0.0, 0.0)
            endcrop = (0.0, 0.0, 1.0, 1.0)
            topnew = True
        elif mode == "slideawayleft":
            endpos = (0.0, 0.0)
            endcrop = (1.0, 0.0, 0.0, 1.0)
            startpos = (0.0, 0.0)
            startcrop = (0.0, 0.0, 1.0, 1.0)
            topnew = False
        elif mode == "slideawayright":
            endpos = (1.0, 0.0)
            endcrop = (0.0, 0.0, 0.0, 1.0)
            startpos = (0.0, 0.0)
            startcrop = (0.0, 0.0, 1.0, 1.0)
            topnew = False
        elif mode == "slideawaydown":
            endpos = (0.0, 1.0)
            endcrop = (0.0, 0.0, 1.0, 0.0)
            startpos = (0.0, 0.0)
            startcrop = (0.0, 0.0, 1.0, 1.0)
            topnew = False
        elif mode == "slideawayup":
            endpos = (0.0, 0.0)
            endcrop = (0.0, 1.0, 1.0, 0.0)
            startpos = (0.0, 0.0)
            startcrop = (0.0, 0.0, 1.0, 1.0)
            topnew = False
        elif mode == "irisout":
            startpos = (0.5, 0.5)
            startcrop = (0.5, 0.5, 0.0, 0.0)
            endpos = (0.0, 0.0)
            endcrop = (0.0, 0.0, 1.0, 1.0)
            topnew = True
        elif mode == "irisin":
            startpos = (0.0, 0.0)
            startcrop = (0.0, 0.0, 1.0, 1.0)
            endpos = (0.5, 0.5)
            endcrop = (0.5, 0.5, 0.0, 0.0)
            topnew = False
        elif mode == "custom":
            pass
        else:
            raise Exception("Invalid mode %s passed into CropMove." % mode)
        self.delay = time
        self.time = time
        self.startpos = startpos
        self.endpos = endpos
        self.startcrop = startcrop
        self.endcrop = endcrop
        self.topnew = topnew
        self.old_widget = old_widget
        self.new_widget = new_widget
        self.events = False
        if topnew:
            self.bottom = old_widget
            self.top = new_widget
        else:
            self.bottom = new_widget
            self.top = old_widget


class PushMove(Transition):
    def __init__(self, time,
                 mode="pushright",
                 old_widget=None,
                 new_widget=None,
                 **properties):
        super(PushMove, self).__init__(time, **properties)
        self.time = time
        if mode == "pushright":
            self.new_startpos = (0.0, 0.0)
            self.new_startcrop = (1.0, 0.0, 0.0, 1.0)
            self.new_endpos = (0.0, 0.0)
            self.new_endcrop = (0.0, 0.0, 1.0, 1.0)
            self.old_endpos = (1.0, 0.0)
            self.old_endcrop = (0.0, 0.0, 0.0, 1.0)
            self.old_startpos = (0.0, 0.0)
            self.old_startcrop = (0.0, 0.0, 1.0, 1.0)
        elif mode == "pushleft":
            self.new_startpos = (1.0, 0.0)
            self.new_startcrop = (0.0, 0.0, 0.0, 1.0)
            self.new_endpos = (0.0, 0.0)
            self.new_endcrop = (0.0, 0.0, 1.0, 1.0)
            self.old_endpos = (0.0, 0.0)
            self.old_endcrop = (1.0, 0.0, 0.0, 1.0)
            self.old_startpos = (0.0, 0.0)
            self.old_startcrop = (0.0, 0.0, 1.0, 1.0)
        elif mode == "pushup":
            self.new_startpos = (0.0, 1.0)
            self.new_startcrop = (0.0, 0.0, 1.0, 0.0)
            self.new_endpos = (0.0, 0.0)
            self.new_endcrop = (0.0, 0.0, 1.0, 1.0)
            self.old_endpos = (0.0, 0.0)
            self.old_endcrop = (0.0, 1.0, 1.0, 0.0)
            self.old_startpos = (0.0, 0.0)
            self.old_startcrop = (0.0, 0.0, 1.0, 1.0)
        elif mode == "pushdown":
            self.new_startpos = (0.0, 0.0)
            self.new_startcrop = (0.0, 1.0, 1.0, 0.0)
            self.new_endpos = (0.0, 0.0)
            self.new_endcrop = (0.0, 0.0, 1.0, 1.0)
            self.old_endpos = (0.0, 1.0)
            self.old_endcrop = (0.0, 0.0, 1.0, 0.0)
            self.old_startpos = (0.0, 0.0)
            self.old_startcrop = (0.0, 0.0, 1.0, 1.0)
        else:
            raise Exception("Invalid mode %s passed into PushMove." % mode)
        self.delay = time
        self.time = time
        self.old_widget = old_widget
        self.new_widget = new_widget
        self.events = False


def ComposeTransition(trans, before=None, after=None, new_widget=None, old_widget=None):
    if before is not None:
        old = before(new_widget=new_widget, old_widget=old_widget)
    else:
        old = old_widget
    if after is not None:
        new = after(new_widget=new_widget, old_widget=old_widget)
    else:
        new = new_widget
    return trans(new_widget=new, old_widget=old)


def SubTransition(rect, trans, old_widget=None, new_widget=None, **properties):
    x, y, _w, _h = rect
    old = renpy.display.layout.LiveCrop(rect, old_widget)
    new = renpy.display.layout.LiveCrop(rect, new_widget)
    inner = trans(old_widget=old, new_widget=new)
    delay = inner.delay
    inner = renpy.display.layout.Position(inner, xpos=x, ypos=y, xanchor=0, yanchor=0)
    f = renpy.display.layout.MultiBox(layout='fixed')
    f.add(new_widget)
    f.add(inner)
    return NoTransition(delay, old_widget=f, new_widget=f)


def __getattr__(name):
    return missing_attribute("renpy.display.transition", name)
