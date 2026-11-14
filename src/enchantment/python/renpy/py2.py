"""Python 2's built-ins and semantics for games whose Ren'Py ran Python 2.

Witch converts their code to Python 3 syntax (witch/python/py2.py) and calls
the __py2_*__ helpers here where the two languages differ in meaning; the
rest are the Python 2 built-in names such code uses.
"""
import math


def py2_div(a, b):
    """Python 2's `/`: floor division on two integers, a class's own __div__
    if it has one, true division otherwise."""
    if isinstance(a, int) and isinstance(b, int):
        return a // b
    div = getattr(type(a), "__div__", None)
    if div is not None:
        result = div(a, b)
        if result is not NotImplemented:
            return result
    rdiv = getattr(type(b), "__rdiv__", None)
    if rdiv is not None:
        result = rdiv(b, a)
        if result is not NotImplemented:
            return result
    return a / b


def py2_div_attr(obj, name, b):
    setattr(obj, name, py2_div(getattr(obj, name), b))


def py2_div_item(obj, key, b):
    obj[key] = py2_div(obj[key], b)


_DICT_FALLBACKS = {
    "iteritems": lambda d: iter(d.items()),
    "iterkeys": lambda d: iter(d.keys()),
    "itervalues": lambda d: iter(d.values()),
    "has_key": lambda d, key: key in d,
}


def py2_method(obj, name, *args):
    """A Python 2 dict method: the object's own if it has one (Ren'Py's
    revertable dicts do), else what Python 2's dict did."""
    method = getattr(obj, name, None)
    if method is not None:
        return method(*args)
    return _DICT_FALLBACKS[name](obj, *args)


def py2_round(x, digits=0):
    """Python 2 rounds halves away from zero and always returns a float."""
    scale = 10.0 ** digits
    y = abs(x) * scale
    r = math.floor(y + 0.5)
    return math.copysign(r / scale, x)


def cmp(a, b):
    return (a > b) - (a < b)


def reduce(function, iterable, *initial):
    it = iter(iterable)
    value = initial[0] if initial else next(it)
    for item in it:
        value = function(value, item)
    return value


_map, _filter, _zip, _range = map, filter, zip, range


def install(builtins):
    builtins.__py2_div__ = py2_div
    builtins.__py2_div_attr__ = py2_div_attr
    builtins.__py2_div_item__ = py2_div_item
    builtins.__py2_method__ = py2_method
    builtins.unicode = str
    builtins.basestring = str
    builtins.long = int
    builtins.unichr = chr
    builtins.xrange = _range
    builtins.cmp = cmp
    builtins.reduce = reduce
    builtins.round = py2_round
    # Python 2 returns lists from these.
    builtins.map = lambda *a: list(_map(*a))
    builtins.filter = lambda f, it: list(_filter(f, it))
    builtins.zip = lambda *a: list(_zip(*a))
    builtins.range = lambda *a: list(_range(*a))
