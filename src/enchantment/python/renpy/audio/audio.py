"""Audio channels (registration as Ren'Py 7.0's renpy.audio.audio). A
channel here is its description: name, mixer, looping, file prefix and
suffix. What it's playing lives in the engine, asked through _charm."""
import _charm
import renpy
from renpy import missing_attribute

channels = {}  # name or alias -> channel
all_channels = []


class Channel(object):
    def __init__(self, name, default_loop, stop_on_mute, tight, file_prefix, file_suffix, buffer_queue, movie,
                 framedrop):
        self.name = name
        self.mixer = None
        self.stop_on_mute = stop_on_mute
        self.tight = tight
        self.file_prefix = file_prefix
        self.file_suffix = file_suffix
        self.buffer_queue = buffer_queue
        self.movie = movie
        self.framedrop = framedrop
        if default_loop is None:
            self.default_loop = True
            self.default_loop_set = False
        else:
            self.default_loop = default_loop
            self.default_loop_set = True

    def get_playing(self):
        return _charm.playing(self.name)


def register_channel(name, mixer=None, loop=None, stop_on_mute=True, tight=False, file_prefix="", file_suffix="",
                     buffer_queue=True, movie=False, framedrop=True):
    if name == "movie":
        movie = True
    c = Channel(name, loop, stop_on_mute, tight, file_prefix, file_suffix, buffer_queue, movie=movie,
                framedrop=framedrop)
    c.mixer = mixer
    all_channels.append(c)
    channels[name] = c


def alias_channel(name, newname):
    channels[newname] = get_channel(name)


def get_channel(name):
    rv = channels.get(name)
    if rv is None:
        if name in renpy.config.auto_channels:
            i = 0
            while True:
                c = get_channel("{} {}".format(name, i))
                if not c.get_playing():
                    return c
                if renpy.config.skipping:
                    return c
                i += 1
        elif " " in name:
            base = name.split()[0]
            mixer, file_prefix, file_suffix = renpy.config.auto_channels[base]
            register_channel(name, loop=False, mixer=mixer, file_prefix=file_prefix, file_suffix=file_suffix)
            return channels[name]
        else:
            raise Exception("Audio channel %r is unknown." % name)
    return rv


def __getattr__(name):
    return missing_attribute("renpy.audio.audio", name)
