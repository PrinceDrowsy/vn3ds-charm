"""renpy.display.dragdrop: Drag and DragGroup as descriptions; dragging is
the engine's, by touch on the bottom screen (REWORK-PLAN §8.3).
Constructors as Ren'Py 7.0's."""
import renpy
from renpy import missing_attribute


def default_drag_group():
    sls = renpy.game.context().scene_lists
    rv = sls.drag_group
    if rv is None:
        rv = DragGroup()
        sls.drag_group = rv
    return rv


def default_drag_joined(drag):
    return [(drag, 0, 0)]


class Drag(renpy.display.core.Displayable, renpy.python.RevertableObject):
    focusable = True
    drag_group = None
    old_position = None
    drag_offscreen = False
    def __init__(self,
                 d=None,
                 drag_name=None,
                 draggable=True,
                 droppable=True,
                 drag_raise=True,
                 dragged=None,
                 dropped=None,
                 drag_handle=(0.0, 0.0, 1.0, 1.0),
                 drag_joined=default_drag_joined,
                 clicked=None,
                 hovered=None,
                 unhovered=None,
                 replaces=None,
                 drag_offscreen=False,
                 mouse_drop=False,
                 style="drag",
                 **properties):
        super(Drag, self).__init__(style=style, **properties)
        self.drag_name = drag_name
        self.draggable = draggable
        self.droppable = droppable
        self.drag_raise = drag_raise
        self.dragged = dragged
        self.dropped = dropped
        self.drag_handle = drag_handle
        self.drag_joined = drag_joined
        self.clicked = clicked
        self.hovered = hovered
        self.unhovered = unhovered
        self.drag_offscreen = drag_offscreen
        self.mouse_drop = mouse_drop
        self.focusable = draggable
        self.child = None
        if drag_name:
            self.drag_group = default_drag_group()
        self.x = None
        self.y = None
        self.w = None
        self.h = None
        self.old_position = None
        self.parent_width = None
        self.parent_height = None
        self.target_x = None
        self.target_y = None
        self.grab_x = None
        self.grab_y = None
        self.last_x = None
        self.last_y = None
        self.start_x = 0
        self.start_y = 0
        self.at = 0
        self.target_at = 0
        self.target_at_delay = 0
        self.last_drop = None
        self.drag_moved = False
        if replaces is not None:
            self.x = replaces.x
            self.y = replaces.y
            self.at = replaces.at
            self.target_x = replaces.target_x
            self.target_y = replaces.target_y
            self.target_at = replaces.target_at
            self.target_at_delay = replaces.target_at_delay
            self.grab_x = replaces.grab_x
            self.grab_y = replaces.grab_y
            self.last_x = replaces.last_x
            self.last_y = replaces.last_y
            self.old_position = replaces.old_position
            self.drag_moved = replaces.drag_moved
            self.last_drop = replaces.last_drop
            self.mouse_drop = replaces.mouse_drop
        if d is not None:
            self.add(d)

    def add(self, d):
        if self.child is not None:
            raise Exception("Drag expects either zero or one children.")
        self.child = renpy.easy.displayable(d)


class DragGroup(renpy.display.layout.MultiBox):
    _list_type = renpy.python.RevertableList
    def __init__(self, *children, **properties):
        properties.setdefault("style", "fixed")
        properties.setdefault("layout", "fixed")
        replaces = properties.pop("replaces", None)
        super(DragGroup, self).__init__(**properties)
        if replaces is not None:
            self.positions = renpy.python.RevertableDict(replaces.positions)
            self.sensitive = replaces.sensitive
        else:
            self.positions = renpy.python.RevertableDict()
            self.sensitive = True
        for i in children:
            self.add(i)


def __getattr__(name):
    return missing_attribute("renpy.display.dragdrop", name)
