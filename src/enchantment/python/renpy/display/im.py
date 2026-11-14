"""Image manipulators (renpy.display.im): descriptions of an image and the
operations on it, which the engine evaluates at runtime or Witch bakes
(REWORK-PLAN §7.2). Constructors and im.matrix follow Ren'Py 7.0's."""
import math

import renpy
from renpy import missing_attribute


class ImageBase(renpy.display.core.Displayable):
    __version__ = 1

    def __init__(self, *args, **properties):
        self.rle = properties.pop('rle', None)
        self.cache = properties.pop('cache', True)
        properties.setdefault('style', 'image')
        super(ImageBase, self).__init__(**properties)
        self.identity = (type(self).__name__,) + args

    def __hash__(self):
        return hash(self.identity)

    def __eq__(self, other):
        if not isinstance(other, ImageBase):
            return False
        return self.identity == other.identity


class Image(ImageBase):
    def __init__(self, filename, **properties):
        super(Image, self).__init__(filename, **properties)
        self.filename = filename


class Data(ImageBase):
    def __init__(self, data, filename, **properties):
        super(Data, self).__init__(data, filename, **properties)
        self.data = data
        self.filename = filename


class ZipFileImage(ImageBase):
    def __init__(self, zipfilename, filename, mtime=0, **properties):
        super(ZipFileImage, self).__init__(zipfilename, filename, mtime, **properties)
        self.zipfilename = zipfilename
        self.filename = filename


class Composite(ImageBase):
    def __init__(self, size, *args, **properties):
        super(Composite, self).__init__(size, *args, **properties)
        if len(args) % 2 != 0:
            raise Exception("Composite requires an odd number of arguments.")
        self.size = size
        self.positions = args[0::2]
        self.images = [image(i) for i in args[1::2]]


class Scale(ImageBase):
    def __init__(self, im, width, height, bilinear=True, **properties):
        im = image(im)
        super(Scale, self).__init__(im, width, height, bilinear, **properties)
        self.image = im
        self.width = int(width)
        self.height = int(height)
        self.bilinear = bilinear


class FactorScale(ImageBase):
    def __init__(self, im, width, height=None, bilinear=True, **properties):
        if height is None:
            height = width
        im = image(im)
        super(FactorScale, self).__init__(im, width, height, bilinear, **properties)
        self.image = im
        self.width = width
        self.height = height
        self.bilinear = bilinear


class Flip(ImageBase):
    def __init__(self, im, horizontal=False, vertical=False, **properties):
        if not (horizontal or vertical):
            raise Exception("im.Flip must be called with a true value for horizontal or vertical.")
        im = image(im)
        super(Flip, self).__init__(im, horizontal, vertical, **properties)
        self.image = im
        self.horizontal = horizontal
        self.vertical = vertical


class Rotozoom(ImageBase):
    def __init__(self, im, angle, zoom, **properties):
        im = image(im)
        super(Rotozoom, self).__init__(im, angle, zoom, **properties)
        self.image = im
        self.angle = angle
        self.zoom = zoom


class Crop(ImageBase):
    def __init__(self, im, x, y=None, w=None, h=None, **properties):
        im = image(im)
        if y is None:
            (x, y, w, h) = x
        super(Crop, self).__init__(im, x, y, w, h, **properties)
        self.image = im
        self.x = x
        self.y = y
        self.w = w
        self.h = h


ramp_cache = {}


def ramp(start, end):
    """A 256-character linear ramp from `start` to `end`, for im.Map."""
    rv = ramp_cache.get((start, end))
    if rv is None:
        chars = []
        for i in range(0, 256):
            i = i / 255.0
            chars.append(chr(int(end * i + start * (1.0 - i))))
        rv = ramp_cache[start, end] = "".join(chars)
    return rv


identity = ramp(0, 255)


class Map(ImageBase):
    def __init__(self, im, rmap=identity, gmap=identity, bmap=identity, amap=identity, force_alpha=False,
                 **properties):
        im = image(im)
        super(Map, self).__init__(im, rmap, gmap, bmap, amap, force_alpha, **properties)
        self.image = im
        self.rmap = rmap
        self.gmap = gmap
        self.bmap = bmap
        self.amap = amap
        self.force_alpha = force_alpha


class Twocolor(ImageBase):
    def __init__(self, im, white, black, force_alpha=False, **properties):
        white = renpy.easy.color(white)
        black = renpy.easy.color(black)
        im = image(im)
        super(Twocolor, self).__init__(im, white, black, force_alpha, **properties)
        self.image = im
        self.white = white
        self.black = black
        self.force_alpha = force_alpha


class Recolor(ImageBase):
    def __init__(self, im, rmul=255, gmul=255, bmul=255, amul=255, force_alpha=False, **properties):
        im = image(im)
        super(Recolor, self).__init__(im, rmul, gmul, bmul, amul, force_alpha, **properties)
        self.image = im
        self.rmul = rmul + 1
        self.gmul = gmul + 1
        self.bmul = bmul + 1
        self.amul = amul + 1
        self.force_alpha = force_alpha


class MatrixColor(ImageBase):
    def __init__(self, im, matrix, **properties):
        im = image(im)
        if len(matrix) != 20 and len(matrix) != 25:
            raise Exception("ColorMatrix expects a 20 or 25 element matrix, got %d elements." % len(matrix))
        matrix = tuple(matrix)
        super(MatrixColor, self).__init__(im, matrix, **properties)
        self.image = im
        self.matrix = matrix


class matrix(tuple):
    """A 5x5 colour matrix; * multiplies matrices or scales, + and -
    work element-wise."""

    def __new__(cls, *args):
        if len(args) == 1:
            args = tuple(args[0])
        if len(args) == 20:
            args = args + (0, 0, 0, 0, 1)
        if len(args) != 25:
            raise Exception("Matrix expects to be given 20 or 25 entries, not %d." % len(args))
        return tuple.__new__(cls, args)

    def mul(self, a, b):
        if not isinstance(a, matrix):
            a = matrix(a)
        if not isinstance(b, matrix):
            if isinstance(b, renpy.easy.Color):
                return NotImplemented
            b = matrix(b)
        result = [0] * 25
        for y in range(0, 5):
            for x in range(0, 5):
                for i in range(0, 5):
                    result[x + y * 5] += a[x + i * 5] * b[i + y * 5]
        return matrix(result)

    def scalar_mul(self, other):
        other = float(other)
        return matrix([i * other for i in self])

    def vector_mul(self, o):
        return (o[0] * self[0] + o[1] * self[1] + o[2] * self[2] + o[3] * self[3] + self[4],
                o[0] * self[5] + o[1] * self[6] + o[2] * self[7] + o[3] * self[8] + self[9],
                o[0] * self[10] + o[1] * self[11] + o[2] * self[12] + o[3] * self[13] + self[14],
                o[0] * self[15] + o[1] * self[16] + o[2] * self[17] + o[3] * self[18] + self[19],
                1)

    def __add__(self, other):
        if isinstance(other, (int, float)):
            other = float(other)
            return matrix([i + other for i in self])
        other = matrix(other)
        return matrix([i + j for i, j in zip(self, other)])

    __radd__ = __add__

    def __sub__(self, other):
        return self + other * -1

    def __rsub__(self, other):
        return self * -1 + other

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return self.scalar_mul(other)
        return self.mul(self, other)

    def __rmul__(self, other):
        if isinstance(other, (int, float)):
            return self.scalar_mul(other)
        return self.mul(other, self)

    @staticmethod
    def identity():
        return matrix(1, 0, 0, 0, 0,
                      0, 1, 0, 0, 0,
                      0, 0, 1, 0, 0,
                      0, 0, 0, 1, 0)

    @staticmethod
    def saturation(level, desat=(0.2126, 0.7152, 0.0722)):
        r, g, b = desat

        def I(a, b):
            return a + (b - a) * level

        return matrix(I(r, 1), I(g, 0), I(b, 0), 0, 0,
                      I(r, 0), I(g, 1), I(b, 0), 0, 0,
                      I(r, 0), I(g, 0), I(b, 1), 0, 0,
                      0, 0, 0, 1, 0)

    @staticmethod
    def desaturate():
        return matrix.saturation(0.0)

    @staticmethod
    def tint(r, g, b):
        return matrix(r, 0, 0, 0, 0,
                      0, g, 0, 0, 0,
                      0, 0, b, 0, 0,
                      0, 0, 0, 1, 0)

    @staticmethod
    def invert():
        return matrix(-1, 0, 0, 0, 1,
                      0, -1, 0, 0, 1,
                      0, 0, -1, 0, 1,
                      0, 0, 0, 1, 0)

    @staticmethod
    def brightness(b):
        return matrix(1, 0, 0, 0, b,
                      0, 1, 0, 0, b,
                      0, 0, 1, 0, b,
                      0, 0, 0, 1, 0)

    @staticmethod
    def opacity(o):
        return matrix(1, 0, 0, 0, 0,
                      0, 1, 0, 0, 0,
                      0, 0, 1, 0, 0,
                      0, 0, 0, o, 0)

    @staticmethod
    def contrast(c):
        return matrix.brightness(-.5) * matrix.tint(c, c, c) * matrix.brightness(.5)

    @staticmethod
    def hue(h):
        h = h * math.pi / 180
        cosVal = math.cos(h)
        sinVal = math.sin(h)
        lumR = 0.213
        lumG = 0.715
        lumB = 0.072
        return matrix(
            lumR + cosVal * (1 - lumR) + sinVal * (-lumR), lumG + cosVal * (-lumG) + sinVal * (-lumG),
            lumB + cosVal * (-lumB) + sinVal * (1 - lumB), 0, 0,
            lumR + cosVal * (-lumR) + sinVal * (0.143), lumG + cosVal * (1 - lumG) + sinVal * (0.140),
            lumB + cosVal * (-lumB) + sinVal * (-0.283), 0, 0,
            lumR + cosVal * (-lumR) + sinVal * (-(1 - lumR)), lumG + cosVal * (-lumG) + sinVal * (lumG),
            lumB + cosVal * (1 - lumB) + sinVal * (lumB), 0, 0,
            0, 0, 0, 1, 0,
            0, 0, 0, 0, 1)

    @staticmethod
    def colorize(black_color, white_color):
        (r0, g0, b0, _a0) = renpy.easy.color(black_color)
        (r1, g1, b1, _a1) = renpy.easy.color(white_color)
        r0 /= 255.0
        g0 /= 255.0
        b0 /= 255.0
        r1 /= 255.0
        g1 /= 255.0
        b1 /= 255.0
        return matrix((r1 - r0), 0, 0, 0, r0,
                      0, (g1 - g0), 0, 0, g0,
                      0, 0, (b1 - b0), 0, b0,
                      0, 0, 0, 1, 0)


def Grayscale(im, desat=(0.2126, 0.7152, 0.0722), **properties):
    return MatrixColor(im, matrix.saturation(0.0, desat), **properties)


def Sepia(im, tint=(1.0, .94, .76), desat=(0.2126, 0.7152, 0.0722), **properties):
    return MatrixColor(im, matrix.saturation(0.0, desat) * matrix.tint(tint[0], tint[1], tint[2]), **properties)


def Color(im, color):
    r, g, b, a = renpy.easy.color(color)
    return Recolor(im, r, g, b, a)


def Alpha(image, alpha, **properties):
    return Recolor(image, 255, 255, 255, int(255 * alpha), force_alpha=True, **properties)


class Tile(ImageBase):
    def __init__(self, im, size=None, **properties):
        im = image(im)
        super(Tile, self).__init__(im, size, **properties)
        self.image = im
        self.size = size


class AlphaMask(ImageBase):
    def __init__(self, base, mask, **properties):
        super(AlphaMask, self).__init__(base, mask, **properties)
        self.base = image(base)
        self.mask = image(mask)


def image(arg, loose=False, **properties):
    if isinstance(arg, ImageBase):
        return arg
    elif isinstance(arg, str):
        return Image(arg, **properties)
    elif isinstance(arg, renpy.display.image.ImageReference):
        arg.find_target()
        return image(arg.target, loose=loose, **properties)
    elif isinstance(arg, tuple):
        params = []
        for i in arg:
            params.append((0, 0))
            params.append(i)
        return Composite(None, *params)
    elif loose:
        return arg
    if isinstance(arg, renpy.display.core.Displayable):
        raise Exception("Expected an image, but got a general displayable.")
    raise Exception("Could not construct image from argument.")


def __getattr__(name):
    return missing_attribute("renpy.display.im", name)
