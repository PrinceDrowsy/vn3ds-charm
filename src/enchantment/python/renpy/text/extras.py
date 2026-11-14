"""renpy.text.extras: ParameterizedText, the `text` image."""
import renpy
from renpy import missing_attribute


class ParameterizedText(object):
    def __init__(self, style='default', **properties):
        self.style = style
        self.properties = properties

    _duplicatable = True

    def _duplicate(self, args):
        if len(args.args) == 0:
            raise Exception("'%s' takes a single string parameter." % ' '.join(args.name))
        param = "".join(args.args)
        string = renpy.python.py_eval(param)
        return renpy.text.text.Text(string, style=self.style, **self.properties)


def __getattr__(name):
    return missing_attribute("renpy.text.extras", name)
