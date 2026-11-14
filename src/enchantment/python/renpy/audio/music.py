"""renpy.music (as Ren'Py 7.0's renpy.audio.music). Channel settings are
descriptions; playing, queueing and stopping go to the engine."""
import renpy
from renpy import missing_attribute
from renpy.audio.audio import alias_channel, get_channel, register_channel  # noqa: F401


def set_music(channel, flag, default=False):
    c = get_channel(channel)
    if default and c.default_loop_set:
        return
    c.default_loop = flag
    c.default_loop_set = True


def set_mixer(channel, mixer, default=False):
    try:
        c = get_channel(channel)
        if not default or c.mixer is None:
            c.mixer = mixer
    except Exception:
        if renpy.config.debug_sound:
            raise


def get_all_mixers():
    return list(set(c.mixer for c in renpy.audio.audio.all_channels))


def channel_defined(channel):
    try:
        get_channel(channel)
        return True
    except Exception:
        return False


def __getattr__(name):
    return missing_attribute("renpy.audio.music", name)
