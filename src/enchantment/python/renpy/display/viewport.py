"""renpy.display.viewport: Viewport and VPGrid as descriptions; scrolling
is the engine's (REWORK-PLAN §8.3). Constructors as Ren'Py 7.0's."""
import renpy
from renpy import missing_attribute


def edgescroll_proportional(n):
    return n


class Viewport(renpy.display.layout.Container):
    __version__ = 5
    arrowkeys = False
    pagekeys = False
    def __init__(self,
                 child=None,
                 child_size=(None, None),
                 offsets=(None, None),
                 xadjustment=None,
                 yadjustment=None,
                 set_adjustments=True,
                 mousewheel=False,
                 draggable=False,
                 edgescroll=None,
                 style='viewport',
                 xinitial=None,
                 yinitial=None,
                 replaces=None,
                 arrowkeys=False,
                 pagekeys=False,
                 **properties):
        super(Viewport, self).__init__(style=style, **properties)
        if child is not None:
            self.add(child)
        self.xadjustment_param = xadjustment
        self.yadjustment_param = yadjustment
        self.offsets_param = offsets
        self.set_adjustments_param = set_adjustments
        self.xinitial_param = xinitial
        self.yinitial_param = yinitial
        self._show()
        if isinstance(replaces, Viewport):
            self.xadjustment.range = replaces.xadjustment.range
            self.yadjustment.range = replaces.yadjustment.range
            self.xadjustment.value = replaces.xadjustment.value
            self.yadjustment.value = replaces.yadjustment.value
            self.xoffset = replaces.xoffset
            self.yoffset = replaces.yoffset
            self.drag_position = replaces.drag_position
        else:
            self.drag_position = None
        self.child_width, self.child_height = child_size
        self.mousewheel = mousewheel
        self.draggable = draggable
        self.arrowkeys = arrowkeys
        self.pagekeys = pagekeys
        self.focusable = draggable or arrowkeys
        self.width = 0
        self.height = 0
        self.edge_xspeed = 0
        self.edge_yspeed = 0
        self.edge_last_st = None
        if edgescroll is not None:
            self.edge_size = edgescroll[0]
            self.edge_speed = edgescroll[1]
            if len(edgescroll) >= 3:
                self.edge_function = edgescroll[2]
            else:
                self.edge_function = edgescroll_proportional
        else:
            self.edge_size = 0
            self.edge_speed = 0
            self.edge_function = edgescroll_proportional

    def _show(self):
        if self.xadjustment_param is None:
            self.xadjustment = renpy.display.behavior.Adjustment(1, 0)
        else:
            self.xadjustment = self.xadjustment_param
        if self.yadjustment_param is None:
            self.yadjustment = renpy.display.behavior.Adjustment(1, 0)
        else:
            self.yadjustment = self.yadjustment_param
        if self.xadjustment.adjustable is None:
            self.xadjustment.adjustable = True
        if self.yadjustment.adjustable is None:
            self.yadjustment.adjustable = True
        self.set_adjustments = self.set_adjustments_param
        offsets = self.offsets_param
        self.xoffset = offsets[0] if (offsets[0] is not None) else self.xinitial_param
        self.yoffset = offsets[1] if (offsets[1] is not None) else self.yinitial_param


class VPGrid(Viewport):
    __version__ = Viewport.__version__
    def __init__(self, cols=None, rows=None, transpose=None, style="vpgrid", **properties):
        super(VPGrid, self).__init__(style=style, **properties)
        if (rows is None) and (cols is None):
            raise Exception("A VPGrid must be given the rows or cols property.")
        if (rows is not None) and (cols is None) and (transpose is None):
            transpose = True
        self.grid_cols = cols
        self.grid_rows = rows
        self.grid_transpose = transpose


def __getattr__(name):
    return missing_attribute("renpy.display.viewport", name)
