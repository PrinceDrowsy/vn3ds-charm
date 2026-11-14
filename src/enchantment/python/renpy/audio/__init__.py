"""renpy.audio: channel descriptions; playback is the engine's (§8.6)."""
from renpy import submodule_or_missing


def __getattr__(name):
    return submodule_or_missing("renpy.audio", name)
