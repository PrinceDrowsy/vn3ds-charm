"""renpy.arguments. Command-line commands (the launcher's lint, compile,
...) are a PC feature; registering one keeps nothing."""
from renpy import missing_attribute


def register_command(name, function, uses_display=False):
    pass


def __getattr__(name):
    return missing_attribute("renpy.arguments", name)
