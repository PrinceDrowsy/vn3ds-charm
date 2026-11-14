"""os.path for MicroPython, with POSIX rules: paths on the 3DS's SD card,
and the ones Witch hands the desktop run, use "/"."""
import os

sep = "/"
_DIR = 0o040000
_TYPE = 0o170000


def join(a, *parts):
    path = a
    for p in parts:
        if p.startswith("/"):
            path = p
        elif not path or path.endswith("/"):
            path += p
        else:
            path += "/" + p
    return path


def split(path):
    i = path.rfind("/") + 1
    head, tail = path[:i], path[i:]
    if head and head != "/" * len(head):
        head = head.rstrip("/")
    return head, tail


def dirname(path):
    return split(path)[0]


def basename(path):
    return split(path)[1]


def splitext(path):
    dot = path.rfind(".")
    if dot <= path.rfind("/") + 1 or path[path.rfind("/") + 1:dot].strip(".") == "":
        return path, ""
    return path[:dot], path[dot:]


def normpath(path):
    if not path:
        return "."
    initial = "/" if path.startswith("/") else ""
    parts = []
    for p in path.split("/"):
        if p in ("", "."):
            continue
        if p == ".." and parts and parts[-1] != "..":
            parts.pop()
        elif p != ".." or not initial:
            parts.append(p)
    return (initial + "/".join(parts)) or "."


def abspath(path):
    if not path.startswith("/"):
        path = join(os.getcwd().replace("\\", "/"), path)
    return normpath(path)


def expanduser(path):
    return path


def _mode(path):
    try:
        return os.stat(path)[0]
    except OSError:
        return None


def exists(path):
    return _mode(path) is not None


def isdir(path):
    mode = _mode(path)
    return mode is not None and mode & _TYPE == _DIR


def isfile(path):
    mode = _mode(path)
    return mode is not None and mode & _TYPE != _DIR
