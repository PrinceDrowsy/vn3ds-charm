"""copy, which MicroPython doesn't ship: CPython's rules for shallow and deep
copies of the values game code holds (containers and plain objects)."""

_ATOMIC = (type(None), bool, int, float, complex, str, bytes, type, range)


def copy(x):
    hook = getattr(type(x), "__copy__", None)
    if hook is not None:
        return hook(x)
    if isinstance(x, _ATOMIC) or callable(x) and not hasattr(x, "__dict__"):
        return x
    if isinstance(x, (list, dict, set, bytearray)):
        return type(x)(x)
    if isinstance(x, (tuple, frozenset)):
        return x
    return _copy_object(x, lambda v: v)


def deepcopy(x, memo=None):
    if memo is None:
        memo = {}
    key = id(x)
    if key in memo:
        return memo[key]
    hook = getattr(type(x), "__deepcopy__", None)
    if hook is not None:
        y = hook(x, memo)
    elif isinstance(x, _ATOMIC) or callable(x) and not hasattr(x, "__dict__"):
        return x
    elif isinstance(x, list):
        y = memo[key] = type(x)()
        y.extend(deepcopy(v, memo) for v in x)
    elif isinstance(x, dict):
        y = memo[key] = type(x)()
        for k, v in x.items():
            y[deepcopy(k, memo)] = deepcopy(v, memo)
    elif isinstance(x, tuple):
        y = type(x)(deepcopy(v, memo) for v in x)
    elif isinstance(x, (set, frozenset)):
        y = type(x)(deepcopy(v, memo) for v in x)
    else:
        y = _copy_object(x, lambda v: deepcopy(v, memo), memo, key)
    memo[key] = y
    return y


def _copy_object(x, convert, memo=None, key=None):
    y = object.__new__(type(x))
    if memo is not None:
        memo[key] = y
    for name, value in getattr(x, "__dict__", {}).items():
        setattr(y, name, convert(value))
    return y
