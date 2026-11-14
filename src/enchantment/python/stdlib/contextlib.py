"""The parts of contextlib Ren'Py's code uses."""


class _GeneratorContextManager:
    def __init__(self, gen):
        self.gen = gen

    def __enter__(self):
        return next(self.gen)

    def __exit__(self, type, value, traceback):
        if type is None:
            try:
                next(self.gen)
            except StopIteration:
                return False
            raise RuntimeError("generator didn't stop")
        try:
            self.gen.throw(value)
        except StopIteration as e:
            return e is not value
        except BaseException as e:
            if e is value:
                return False
            raise
        raise RuntimeError("generator didn't stop after throw()")


def contextmanager(func):
    def helper(*args, **kwargs):
        return _GeneratorContextManager(func(*args, **kwargs))
    return helper


class suppress:
    def __init__(self, *exceptions):
        self.exceptions = exceptions

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        return type is not None and issubclass(type, self.exceptions)
