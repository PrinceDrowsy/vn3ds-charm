"""renpy.sound: renpy.music on the "sound" channel by default."""
from renpy import missing_attribute
from renpy.audio.music import set_mixer  # noqa: F401


def __getattr__(name):
    return missing_attribute("renpy.audio.sound", name)
