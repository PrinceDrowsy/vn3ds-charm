"""The engine port (REWORK-PLAN §6.3) as Witch's init run has it: there's no
engine at convert time, so it keeps what the shim registers, and the driver
hands that to Witch for the bundle. On the device and in the desktop engine,
_charm is C."""

images = {}  # name tuple -> description
screens = {}  # name -> node of its `screen` statement
defaults = []  # (store, name, node) of each `default` the game starts with
strings = {}  # language -> {old: new}


def image(name, d):
    images[name] = d


def get_image(name):
    return images.get(name)


def has_image(name):
    return name in images


def screen(name, node):
    screens[name] = node


def has_screen(name):
    return name in screens


def default(store, name, node):
    defaults.append((store, name, node))


def translate_string(language, old, new):
    strings.setdefault(language, {})[old] = new
