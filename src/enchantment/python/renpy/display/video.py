"""renpy.display.video: Movie, the description of a video displayable
(REWORK-PLAN §8.7). Constructor as Ren'Py 7.0's."""
import renpy
from renpy import missing_attribute


class Movie(renpy.display.core.Displayable):
    fullscreen = False
    channel = "movie"
    _play = None
    mask = None
    mask_channel = None
    image = None
    play_callback = None

    def ensure_channel(self, name):
        if name is None:
            return
        if renpy.audio.music.channel_defined(name):
            return
        framedrop = bool(self.mask)
        renpy.audio.music.register_channel(name, renpy.config.movie_mixer, loop=True, stop_on_mute=False, movie=True,
                                           framedrop=framedrop)

    def __init__(self, fps=24, size=None, channel="movie", play=None, mask=None, mask_channel=None, image=None,
                 play_callback=None, **properties):
        super(Movie, self).__init__(**properties)
        if channel == "movie" and play and renpy.config.auto_movie_channel:
            channel = "movie_{}_{}".format(play, mask)
        self.size = size
        self.channel = channel
        self._play = play
        self.mask = mask
        if mask is None:
            self.mask_channel = None
        elif mask_channel is None:
            self.mask_channel = channel + "_mask"
        else:
            self.mask_channel = mask_channel
        self.ensure_channel(self.channel)
        self.ensure_channel(self.mask_channel)
        self.image = renpy.easy.displayable_or_none(image)
        self.play_callback = play_callback
        if self.channel == "movie" and renpy.config.hw_video and renpy.mobile:
            raise Exception("Movie(channel='movie') doesn't work on mobile when config.hw_video is true. "
                            "(Use a different channel argument.)")


def __getattr__(name):
    return missing_attribute("renpy.display.video", name)
