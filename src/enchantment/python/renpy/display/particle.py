"""renpy.display.particle: particle systems as descriptions. The engine
runs them from Ren'Py's algorithm (REWORK-PLAN §7.5); a SpriteManager's
update and event functions are callback slots. Constructors as Ren'Py
7.0's."""
import random

import renpy
from renpy import missing_attribute


class SpriteManager(renpy.display.core.Displayable):
    def __init__(self, update=None, event=None, predict=None, ignore_time=False, **properties):
        # Ren'Py 7.0 passes itself as the focus name here; kept as it is.
        super(SpriteManager, self).__init__(self, **properties)
        self.update_function = update
        self.event_function = event
        self.predict_function = predict
        self.ignore_time = ignore_time
        self.displayable_map = {}
        self.children = []
        self.dead_child = False
        self.events = False
        self.width = None
        self.height = None


class Particles(renpy.display.core.Displayable, renpy.python.NoRollback):
    """A particle system run by a factory (SnowBlossomFactory or a game's
    own, whose create and predict methods are callback slots)."""

    __version__ = 1
    nosave = ['particles']

    def __init__(self, factory, **properties):
        super(Particles, self).__init__(**properties)
        self.factory = factory
        self.particles = None


class SnowBlossomFactory(renpy.python.NoRollback):
    rotate = False

    def __init__(self, image, count, xspeed, yspeed, border, start, fast, rotate=False):
        self.image = renpy.easy.displayable(image)
        self.count = count
        self.xspeed = xspeed
        self.yspeed = yspeed
        self.border = border
        self.start = start
        self.fast = fast
        self.rotate = rotate
        self.init()

    def init(self):
        self.starts = [random.uniform(0, self.start) for _i in range(0, self.count)]
        self.starts.append(self.start)
        self.starts.sort()


def SnowBlossom(d, count=10, border=50, xspeed=(20, 50), yspeed=(100, 200), start=0, fast=False, horizontal=False):
    if horizontal:
        xspeed, yspeed = yspeed, xspeed
    return Particles(SnowBlossomFactory(image=d, count=count, border=border, xspeed=xspeed, yspeed=yspeed,
                                        start=start, fast=fast, rotate=horizontal))


def __getattr__(name):
    return missing_attribute("renpy.display.particle", name)
