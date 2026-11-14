"""colorsys for MicroPython: conversions between RGB and HSV or HLS, all
components in 0.0-1.0, with the same arithmetic as CPython's so results
match to the last bit. YIQ is left out: its coefficients differ between
Python 2 and 3, and nothing in the corpus uses it."""

ONE_THIRD = 1.0 / 3.0
ONE_SIXTH = 1.0 / 6.0
TWO_THIRD = 2.0 / 3.0


def rgb_to_hls(r, g, b):
    maxc = max(r, g, b)
    minc = min(r, g, b)
    total = maxc + minc
    span = maxc - minc
    lightness = total / 2.0
    if minc == maxc:
        return 0.0, lightness, 0.0
    if lightness <= 0.5:
        s = span / total
    else:
        s = span / (2.0 - maxc - minc)  # not 2.0 - total, which rounds differently
    rc = (maxc - r) / span
    gc = (maxc - g) / span
    bc = (maxc - b) / span
    if r == maxc:
        h = bc - gc
    elif g == maxc:
        h = 2.0 + rc - bc
    else:
        h = 4.0 + gc - rc
    h = (h / 6.0) % 1.0
    return h, lightness, s


def hls_to_rgb(h, lightness, s):
    if s == 0.0:
        return lightness, lightness, lightness
    if lightness <= 0.5:
        m2 = lightness * (1.0 + s)
    else:
        m2 = lightness + s - (lightness * s)
    m1 = 2.0 * lightness - m2
    return (_v(m1, m2, h + ONE_THIRD), _v(m1, m2, h), _v(m1, m2, h - ONE_THIRD))


def _v(m1, m2, hue):
    hue = hue % 1.0
    if hue < ONE_SIXTH:
        return m1 + (m2 - m1) * hue * 6.0
    if hue < 0.5:
        return m2
    if hue < TWO_THIRD:
        return m1 + (m2 - m1) * (TWO_THIRD - hue) * 6.0
    return m1


def rgb_to_hsv(r, g, b):
    maxc = max(r, g, b)
    minc = min(r, g, b)
    v = maxc
    if minc == maxc:
        return 0.0, 0.0, v
    span = maxc - minc
    s = span / maxc
    rc = (maxc - r) / span
    gc = (maxc - g) / span
    bc = (maxc - b) / span
    if r == maxc:
        h = bc - gc
    elif g == maxc:
        h = 2.0 + rc - bc
    else:
        h = 4.0 + gc - rc
    h = (h / 6.0) % 1.0
    return h, s, v


def hsv_to_rgb(h, s, v):
    if s == 0.0:
        return v, v, v
    i = int(h * 6.0)
    f = (h * 6.0) - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    i = i % 6
    if i == 0:
        return v, t, p
    if i == 1:
        return q, v, p
    if i == 2:
        return p, v, t
    if i == 3:
        return p, q, v
    if i == 4:
        return t, p, v
    return v, p, q
