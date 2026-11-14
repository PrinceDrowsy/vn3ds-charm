"""Image names: the registry lives behind the engine port (_charm), and
ImageReference resolves a name against it as Ren'Py 7.0's does, longest
registered prefix first, the rest passed down as arguments."""
import _charm
import renpy
from renpy import missing_attribute


def register_image(name, d):
    _charm.image(name, d)


def get_available_image_tags():
    tags = []
    for name in _charm.image_names():
        if name[0] not in tags:
            tags.append(name[0])
    return tags


def get_registered_image(name):
    if not isinstance(name, tuple):
        name = tuple(name.split())
    return _charm.get_image(name)


class ImageReference(renpy.display.core.Displayable):
    nosave = ['target']
    target = None
    old_transform = None
    param_target = None
    __version__ = 1

    def __init__(self, name, **properties):
        super(ImageReference, self).__init__(**properties)
        self.name = name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, o):
        if self is o:
            return True
        if not self._equals(o):
            return False
        return self.name == o.name

    def _target(self):
        if self.target is None:
            self.find_target()
        return self.target._target()

    def find_target(self):
        name = self.name
        if isinstance(name, renpy.display.core.Displayable):
            self.target = name
            return True
        if not isinstance(name, tuple):
            name = tuple(name.split())

        def error(msg):
            self.target = renpy.text.text.Text(msg, color=(255, 0, 0, 255), xanchor=0, xpos=0, yanchor=0, ypos=0)
            if renpy.config.debug:
                raise Exception(msg)

        args = []
        while name:
            target = _charm.get_image(name)
            if target is not None:
                break
            args.insert(0, name[-1])
            name = name[:-1]
        if not name:
            error("Image '%s' not found." % ' '.join(self.name))
            return False
        if name and self._args.name == name:
            error("Image '{}' refers to itself.".format(' '.join(name)))
            return False
        try:
            a = self._args.copy(name=name, args=args)
            self.target = target._duplicate(a)
        except Exception as e:
            if renpy.config.debug:
                raise
            error(str(e))
        new_transform = self.target._target()
        if isinstance(new_transform, renpy.display.transform.Transform):
            if self.old_transform is not None:
                new_transform.take_state(self.old_transform)
            self.old_transform = new_transform
        else:
            self.old_transform = None
        return True

    _duplicatable = True

    def _duplicate(self, args):
        rv = self._copy(args)
        rv.target = None
        if isinstance(rv.name, renpy.display.core.Displayable):
            if rv.name._duplicatable:
                rv.name = rv.name._duplicate(args)
        rv.find_target()
        rv._duplicatable = rv.target._duplicatable
        return rv

    def _unique(self):
        if self.target is None:
            self.find_target()
        self._duplicatable = self.target._duplicatable

    def _in_current_store(self):
        if self.target is None:
            self.find_target()
        target = self.target._in_current_store()
        if target is self.target:
            return self
        rv = self._copy()
        rv.target = target
        return rv


# Names Ren'Py keeps here for old code; looked up when used, since their
# modules import this one.
_MOVED = {"Image": ("renpy.display.im", "image"), "Solid": ("renpy.display.imagelike", "Solid"),
          "Frame": ("renpy.display.imagelike", "Frame"), "ImageButton": ("renpy.display.behavior", "ImageButton")}


def __getattr__(name):
    if name in _MOVED:
        module, attr = _MOVED[name]
        return getattr(__import__(module, None, None, [attr]), attr)
    return missing_attribute("renpy.display.image", name)
