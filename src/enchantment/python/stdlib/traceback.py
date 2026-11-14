"""The parts of CPython's traceback module Ren'Py's code uses, over
MicroPython's sys.print_exception."""
import io
import sys


def format_exception_only(etype, value=None):
    if value is None:
        value = etype
        etype = type(value)
    text = str(value)
    return ["%s: %s\n" % (etype.__name__, text) if text else etype.__name__ + "\n"]


def format_exception(etype, value=None, tb=None, limit=None, chain=True):
    if value is None:
        value = etype
    out = io.StringIO()
    sys.print_exception(value, out)
    return [out.getvalue()]


def format_exc(limit=None, chain=True):
    return "".join(format_exception(sys.exc_info()[1]))


def print_exc(limit=None, file=None, chain=True):
    sys.print_exception(sys.exc_info()[1], file or sys.stderr)


def print_exception(etype, value=None, tb=None, limit=None, file=None, chain=True):
    sys.print_exception(etype if value is None else value, file or sys.stderr)
