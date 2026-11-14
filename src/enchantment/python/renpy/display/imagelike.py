"""Image-like displayables: Solid and Frame (constructors as Ren'Py 7.0's)."""
import renpy
from renpy import missing_attribute


class Solid(renpy.display.core.Displayable):
    def __init__(self, color, **properties):
        super(Solid, self).__init__(**properties)
        if color is not None:
            self.color = renpy.easy.color(color)
        else:
            self.color = None


class Borders(object):
    def __init__(self, left, top, right, bottom, pad_left=0, pad_top=0, pad_right=0, pad_bottom=0):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
        self.pad_left = pad_left
        self.pad_top = pad_top
        self.pad_right = pad_right
        self.pad_bottom = pad_bottom


class Frame(renpy.display.core.Displayable):
    __version__ = 1
    properties = {}

    def __init__(self, image, left=None, top=None, right=None, bottom=None, xborder=0, yborder=0, bilinear=True,
                 tile=False, **properties):
        super(Frame, self).__init__(**properties)
        self.image = renpy.easy.displayable(image)
        self._duplicatable = self.image._duplicatable
        if isinstance(left, Borders):
            insets = left
            left = insets.left
            top = insets.top
            right = insets.right
            bottom = insets.bottom
        self.tile = tile
        if left is None:
            left = xborder
        if top is None:
            top = yborder
        if right is None:
            right = left
        if bottom is None:
            bottom = top
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom


class FileCurrentScreenshot(renpy.display.core.Displayable):
    """The save screen's thumbnail of the current screen, which the engine
    captures (REWORK-PLAN §8.9)."""

    def __init__(self, empty=None, **properties):
        super(FileCurrentScreenshot, self).__init__(**properties)
        if empty is None:
            empty = renpy.display.layout.Null()
        self.empty = empty


def __getattr__(name):
    return missing_attribute("renpy.display.imagelike", name)
