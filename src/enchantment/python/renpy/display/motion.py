"""renpy.display.motion, where Ren'Py 6.x/7.x's own code reaches ATLTransform."""
from renpy import missing_attribute
from renpy.display.transform import ATLTransform, Transform  # noqa: F401


def __getattr__(name):
    return missing_attribute("renpy.display.motion", name)
