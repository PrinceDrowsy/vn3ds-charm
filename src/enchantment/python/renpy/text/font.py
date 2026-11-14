"""renpy.text.font: FontGroup, which picks a font per character range.
Glyphs come from atlases baked on the PC (REWORK-PLAN §8.4)."""
from renpy import missing_attribute


class FontGroup(object):
    def __init__(self):
        self.fonts = []
        self.cache = {}
        self.patterns = []

    def add(self, font, start, end):
        if not isinstance(start, int):
            start = ord(start)
        if not isinstance(end, int):
            end = ord(end)
        if end < start:
            raise Exception("In FontGroup.add, the start of a character range must be before the end of the range.")
        if font not in self.fonts:
            self.fonts.append(font)
        index = self.fonts.index(font)
        self.patterns.append((index, start, end))
        return self


def __getattr__(name):
    return missing_attribute("renpy.text.font", name)
