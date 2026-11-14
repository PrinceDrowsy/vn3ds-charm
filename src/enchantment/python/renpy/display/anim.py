"""renpy.display.anim: Ren'Py's older animations (Animation, Blink,
SMAnimation, Filmstrip) as descriptions; the engine runs them by time.
Constructors as Ren'Py 7.0's."""
import renpy
from renpy import missing_attribute


class State(object):
    def __init__(self, name, image, *atlist, **properties):
        if image and not isinstance(image, renpy.display.core.Displayable):
            image = renpy.easy.displayable(image)
        self.name = name
        self.image = image
        self.atlist = atlist
        self.properties = properties
    def add(self, sma):
        sma.states[self.name] = self


class Edge(object):
    def __init__(self, old, delay, new, trans=None, prob=1):
        self.old = old
        self.delay = delay
        self.new = new
        self.trans = trans
        self.prob = prob
    def add(self, sma):
        for _i in range(0, self.prob):
            sma.edges.setdefault(self.old, []).append(self)


class SMAnimation(renpy.display.core.Displayable):
    def __init__(self, initial, *args, **properties):
        if 'delay' in properties:
            self.delay = properties['delay']
            del properties['delay']
        else:
            self.delay = None
        if 'showold' in properties:
            self.showold = properties['showold']
            del properties['showold']
        else:
            self.showold = False
        if 'anim_timebase' in properties:
            self.anim_timebase = properties['anim_timebase']
            del properties['anim_timebase']
        else:
            self.anim_timebase = True
        super(SMAnimation, self).__init__(**properties)
        self.properties = properties
        self.initial = initial
        self.states = {}
        self.edges = {}
        for i in args:
            i.add(self)
        self.edge_start = None
        self.edge_cache = None
        self.edge = None
        self.state = None


def Animation(*args, **kwargs):
    newargs = []
    for i, a in enumerate(args):
        newargs.append(a)
        if i % 2 == 1:
            newargs.append(None)
    return TransitionAnimation(*newargs, **kwargs)


class TransitionAnimation(renpy.display.core.Displayable):
    def __init__(self, *args, **properties):
        properties.setdefault('style', 'animation')
        self.anim_timebase = properties.pop('anim_timebase', True)
        super(TransitionAnimation, self).__init__(**properties)
        images = []
        delays = []
        transitions = []
        for i, arg in enumerate(args):
            if i % 3 == 0:
                images.append(renpy.easy.displayable(arg))
            elif i % 3 == 1:
                delays.append(arg)
            else:
                transitions.append(arg)
        if len(images) > len(delays):
            delays.append(365.25 * 86400.0)  # One year, give or take.
        if len(images) > len(transitions):
            transitions.append(None)
        self.images = images
        self.prev_images = [images[-1]] + images[:-1]
        self.delays = delays
        self.transitions = [ transitions[-1] ] + transitions[:-1]


class Blink(renpy.display.core.Displayable):
    def __init__(self, image, on=0.5, off=0.5, rise=0.5, set=0.5,
                 high=1.0, low=0.0, offset=0.0, anim_timebase=False, **properties):
        super(Blink, self).__init__(**properties)
        self.image = renpy.easy.displayable(image)
        self.on = on
        self.off = off
        self.rise = rise
        self.set = set
        self.high = high
        self.low = low
        self.offset = offset
        self.anim_timebase = anim_timebase
        self.cycle = on + set + off + rise


def Filmstrip(image, framesize, gridsize, delay, frames=None, loop=True, **properties):
    width, height = framesize
    cols, rows = gridsize
    if frames is None:
        frames = cols * rows
    i = 0
    args = []
    for r in range(0, rows):
        for c in range(0, cols):
            x = c * width
            y = r * height
            args.append(renpy.display.im.Crop(image, x, y, width, height))
            args.append(delay)
            i += 1
            if i == frames:
                break
        if i == frames:
            break
    if not loop:
        args.pop()
    return Animation(*args, **properties)


def __getattr__(name):
    return missing_attribute("renpy.display.anim", name)
