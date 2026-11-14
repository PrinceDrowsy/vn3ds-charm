"""Ren'Py 8's renpy.compat: Python 2 names it keeps for old game code, as
Python 3 values."""
import builtins

PY2 = False
basestring = str
unicode = str
pystr = str
str = builtins.str
chr = builtins.chr
range = builtins.range
round = builtins.round
open = builtins.open


def bchr(i):
    return bytes((i,))


def bord(b):
    return b[0] if isinstance(b, (bytes, bytearray)) else ord(b)


def tobytes(s):
    return s.encode("utf-8") if isinstance(s, builtins.str) else bytes(s)
