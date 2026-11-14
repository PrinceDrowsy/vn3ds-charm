"""renpy.display.movetransition. MoveTransition and OldMoveTransition move
each tagged image from where it was to where it is, which the engine does
when the transition runs (REWORK-PLAN §7.4): here they are descriptions of
the arguments. The enter and leave factories are Ren'Py 7.0's, since a
game passes them in and they build ordinary motions."""
import renpy
from renpy import missing_attribute
from renpy.display.transition import Transition


def MoveFactory(pos1, pos2, delay, d, **kwargs):
    if pos1 == pos2:
        return d
    return renpy.display.motion.Move(pos1, pos2, delay, d, **kwargs)


def default_enter_factory(pos, delay, d, **kwargs):
    return d


def default_leave_factory(pos, delay, d, **kwargs):
    return None


def MoveIn(pos, pos1, delay, d, **kwargs):
    def aorb(a, b):
        if a is None:
            return b
        return a
    pos = tuple([aorb(a, b) for a, b in zip(pos, pos1)])
    return renpy.display.motion.Move(pos, pos1, delay, d, **kwargs)


def MoveOut(pos, pos1, delay, d, **kwargs):
    def aorb(a, b):
        if a is None:
            return b
        return a
    pos = tuple([aorb(a, b) for a, b in zip(pos, pos1)])
    return renpy.display.motion.Move(pos1, pos, delay, d, **kwargs)


def ZoomInOut(start, end, pos, delay, d, **kwargs):
    xpos, ypos, xanchor, yanchor = pos
    FactorZoom = renpy.display.motion.FactorZoom
    if end == 1.0:
        return FactorZoom(start, end, delay, d, after_child=d, opaque=False,
                          xpos=xpos, ypos=ypos, xanchor=xanchor, yanchor=yanchor, **kwargs)
    else:
        return FactorZoom(start, end, delay, d, opaque=False,
                          xpos=xpos, ypos=ypos, xanchor=xanchor, yanchor=yanchor, **kwargs)


def RevolveInOut(start, end, pos, delay, d, **kwargs):
    return renpy.display.motion.Revolve(start, end, delay, d, pos=pos, **kwargs)


class MoveTransition(Transition):
    def __init__(self, delay, old_widget=None, new_widget=None, enter=None, leave=None, old=False, layers=['master'],
                 time_warp=None, enter_time_warp=None, leave_time_warp=None):
        super(MoveTransition, self).__init__(delay)
        self.old_widget = old_widget
        self.new_widget = new_widget
        self.enter = enter
        self.leave = leave
        self.old = old
        self.layers = layers
        self.time_warp = time_warp
        self.enter_time_warp = enter_time_warp
        self.leave_time_warp = leave_time_warp
        self.events = False


class OldMoveTransition(Transition):
    def __init__(self, delay, old_widget=None, new_widget=None, factory=None, enter_factory=None, leave_factory=None,
                 old=False, layers=['master']):
        super(OldMoveTransition, self).__init__(delay)
        self.old_widget = old_widget
        self.new_widget = new_widget
        self.factory = MoveFactory if factory is None else factory
        self.enter_factory = default_enter_factory if enter_factory is None else enter_factory
        self.leave_factory = default_leave_factory if leave_factory is None else leave_factory
        self.old = old
        self.layers = layers
        self.events = False


def __getattr__(name):
    return missing_attribute("renpy.display.movetransition", name)
