"""renpy.styledata.styleutil: the conversions Ren'Py's style properties
apply to their values (as Ren'Py 7.0's)."""
import renpy

ANCHORS = dict(left=0.0, right=1.0, center=0.5, top=0.0, bottom=1.0)


def none_is_null(o):
    if o is None:
        return renpy.display.layout.Null()
    return renpy.easy.displayable(o)


def expand_focus_mask(v):
    if v is None or v is False or v is True or callable(v):
        return v
    return renpy.easy.displayable(v)


def expand_outlines(l):
    rv = []
    for i in l:
        if len(i) == 2:
            rv.append((i[0], renpy.easy.color(i[1]), 0, 0))
        else:
            rv.append((i[0], renpy.easy.color(i[1]), i[2], i[3]))
    return rv


def expand_anchor(v):
    try:
        return ANCHORS.get(v, v)
    except TypeError:
        # An unhashable anchor: older Ren'Pys stored the names as objects.
        for n in ANCHORS:
            o = getattr(renpy.store, n, None)
            if o is None:
                continue
            if v is o:
                return ANCHORS[n]
        raise
