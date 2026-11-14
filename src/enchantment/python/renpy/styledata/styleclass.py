"""renpy.styledata.styleclass.Style, the class Ren'Py's styles have once its
generated property accessors are added. Reading a property resolves it,
which is lowering's job (REWORK-PLAN §6.3), so the accessors aren't here."""
from renpy.style import StyleCore


class Style(StyleCore):
    pass
