"""Layout displayables (constructors as Ren'Py 7.0's). A DynamicDisplayable's
function is a callback slot (REWORK-PLAN §6.3): the engine asks the VM for
its child when it needs one."""
import renpy
from renpy import missing_attribute


class Null(renpy.display.core.Displayable):
    def __init__(self, width=0, height=0, **properties):
        super(Null, self).__init__(**properties)
        self.width = width
        self.height = height


class Container(renpy.display.core.Displayable):
    _list_type = list

    def __init__(self, *args, **properties):
        self.children = self._list_type()
        self.child = None
        self.offsets = self._list_type()
        for i in args:
            self.add(i)
        super(Container, self).__init__(**properties)

    def add(self, d):
        child = renpy.easy.displayable(d)
        self.children.append(child)
        self.child = child
        self.offsets = self._list_type()
        if child._duplicatable:
            self._duplicatable = True


class Position(Container):
    def __init__(self, child, style='image_placement', **properties):
        super(Position, self).__init__(style=style, **properties)
        self.add(child)


class MultiBox(Container):
    layer_name = None
    first = True
    order_reverse = False
    layout = None

    def __init__(self, spacing=None, layout=None, style='default', **properties):
        if spacing is not None:
            properties['spacing'] = spacing
        super(MultiBox, self).__init__(style=style, **properties)
        self._clipping = self.style.clipping
        self.default_layout = layout
        self.start_times = []
        self.anim_times = []
        self.layers = None
        self.scene_list = None


def Fixed(**properties):
    return MultiBox(layout='fixed', **properties)


class Window(Container):
    def __init__(self, child=None, style='window', **properties):
        super(Window, self).__init__(style=style, **properties)
        if child is not None:
            self.add(child)


def Composite(size, *args, **properties):
    properties.setdefault('style', 'image_placement')
    width, height = size
    rv = Fixed(xmaximum=width, ymaximum=height, xminimum=width, yminimum=height, **properties)
    if len(args) % 2 != 0:
        raise Exception("LiveComposite requires an odd number of arguments.")
    for pos, widget in zip(args[0::2], args[1::2]):
        xpos, ypos = pos
        rv.add(Position(widget, xpos=xpos, xanchor=0, ypos=ypos, yanchor=0))
    return rv


LiveComposite = Composite


class DynamicDisplayable(renpy.display.core.Displayable):
    def __init__(self, function, *args, **kwargs):
        super(DynamicDisplayable, self).__init__()
        self.child = None
        if isinstance(function, str):
            args = (function,)
            kwargs = {}
            function = dynamic_displayable_compat
        self.predict_function = kwargs.pop("_predict_function", None)
        self.function = function
        self.args = args
        self.kwargs = kwargs


def dynamic_displayable_compat(st, at, expr):
    child = renpy.python.py_eval(expr)
    return child, None


cond_cache = {}


def condition_switch_pick(switch):
    for cond, d in switch:
        if cond is None:
            return d
        if cond in cond_cache:
            code = cond_cache[cond]
        else:
            code = cond_cache[cond] = renpy.python.py_compile(cond, 'eval')
        if renpy.python.py_eval_bytecode(code):
            return d
    raise Exception("Switch could not choose a displayable.")


def condition_switch_show(st, at, switch, predict_all=None):
    return condition_switch_pick(switch), None


def condition_switch_predict(switch, predict_all=None):
    if predict_all is None:
        predict_all = renpy.config.conditionswitch_predict_all
    if predict_all:
        return [d for _cond, d in switch]
    return [condition_switch_pick(switch)]


def ConditionSwitch(*args, **kwargs):
    predict_all = kwargs.pop("predict_all", None)
    kwargs.setdefault('style', 'default')
    switch = []
    if len(args) % 2 != 0:
        raise Exception('ConditionSwitch takes an even number of arguments')
    for cond, d in zip(args[0::2], args[1::2]):
        if cond not in cond_cache:
            cond_cache[cond] = renpy.python.py_compile(cond, 'eval')
        switch.append((cond, renpy.easy.displayable(d)))
    rv = DynamicDisplayable(condition_switch_show, switch, predict_all, _predict_function=condition_switch_predict)
    return Position(rv, **kwargs)


class Grid(Container):
    def __init__(self, cols, rows, padding=None,
                 transpose=False,
                 style='grid', **properties):
        if padding is not None:
            properties.setdefault('spacing', padding)
        super(Grid, self).__init__(style=style, **properties)
        cols = int(cols)
        rows = int(rows)
        self.cols = cols
        self.rows = rows
        self.transpose = transpose


def ShowingSwitch(*args, **kwargs):
    layer = kwargs.pop('layer', 'master')
    if len(args) % 2 != 0:
        raise Exception('ShowingSwitch takes an even number of positional arguments')
    condargs = []
    for name, d in zip(args[0::2], args[1::2]):
        if name is not None:
            if not isinstance(name, tuple):
                name = tuple(name.split())
            cond = "renpy.showing(%r, layer=%r)" % (name, layer)
        else:
            cond = None
        condargs.append(cond)
        condargs.append(d)
    return ConditionSwitch(*condargs, **kwargs)


def Crop(rect, child, **properties):
    return renpy.display.motion.Transform(child, crop=rect, **properties)


class Side(Container):
    possible_positions = set(['tl', 't', 'tr', 'r', 'br', 'b', 'bl', 'l', 'c'])
    def __init__(self, positions, style='side', **properties):
        super(Side, self).__init__(style=style, **properties)
        if isinstance(positions, str):
            positions = positions.split()
        seen = set()
        for i in positions:
            if not i in Side.possible_positions:
                raise Exception("Side used with impossible position '%s'." % (i,))
            if i in seen:
                raise Exception("Side used with duplicate position '%s'." % (i,))
            seen.add(i)
        self.positions = tuple(positions)
        self.sized = False


class Alpha(renpy.display.core.Displayable):
    def __init__(self, start, end, time, child=None, repeat=False, bounce=False,
                 anim_timebase=False, time_warp=None, **properties):
        super(Alpha, self).__init__(**properties)
        self.start = start
        self.end = end
        self.time = time
        self.child = renpy.easy.displayable(child)
        self.repeat = repeat
        self.anim_timebase = anim_timebase
        self.time_warp = time_warp


class Tile(Container):
    def __init__(self, child, style='tile', **properties):
        super(LiveTile, self).__init__(style=style, **properties)
        self.add(child)


class Flatten(Container):
    def __init__(self, child, **properties):
        super(Flatten, self).__init__(**properties)
        self.add(child)


class AlphaMask(Container):
    def __init__(self, child, mask, **properties):
        super(AlphaMask, self).__init__(**properties)
        self.add(child)
        self.mask = renpy.easy.displayable(mask)
        self.null = None


LiveCrop = Crop
LiveTile = Tile


def __getattr__(name):
    return missing_attribute("renpy.display.layout", name)
