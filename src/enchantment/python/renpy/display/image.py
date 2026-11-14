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


class DynamicImage(renpy.display.core.Displayable):
    nosave = ['raw_target']
    target = None
    raw_target = None
    locked = False
    hash_name = None

    def __init__(self, name, scope=None, **properties):
        super(DynamicImage, self).__init__(**properties)
        self.name = name
        if scope is not None:
            self.find_target(scope)
            self._uses_scope = True
        else:
            self._uses_scope = False
        if isinstance(name, str) and ("[prefix_" in name):
            self._duplicatable = True
        if isinstance(name, list):
            for i in name:
                if ("[prefix_" in i):
                    self._duplicatable = True

    def _scope(self, scope, update):
        return self.find_target(scope, update)

    def __hash__(self):
        if self.hash_name is None:
            if isinstance(self.name, list):
                self.hash_name = tuple(self.name)
            else:
                self.hash_name = self.name
        return hash(self.hash_name)

    def __eq__(self, o):
        if self is o:
            return True
        if not self._equals(o):
            return False
        if self.name != o.name:
            return False
        return True

    def _target(self):
        if self.target:
            return self.target._target()
        else:
            return self

    def find_target(self, scope=None, update=True):
        if self.locked and (self.target is not None):
            return
        if self._args.prefix is None:
            prefix = ""
        else:
            prefix = self._args.prefix
        try:
            search = []
            target = renpy.easy.dynamic_image(self.name, scope, prefix=prefix, search=search)
        except KeyError as ke:
            raise Exception("In DynamicImage %r: Could not find substitution '%s'." % (self.name, str(ke.args[0])))
        except Exception as e:
            raise Exception("In DynamicImage %r: %r" % (self.name, e))
        if target is None:
            error = "DynamicImage %r: could not find image." % (self.name,)
            if len(search) == 1:
                error += " (%r)" % (search[0],)
            elif len(search) == 2:
                error += " (%r, %r)" % (search[0], search[1])
            elif len(search) > 2:
                error += " (%r, %r, and %d more.)" % (search[0], search[1], len(search) - 2)
            raise Exception(error)
        if self.raw_target == target:
            return False
        if not update:
            return True
        self.raw_target = target
        old_target = self.target
        if target._duplicatable:
            target = target._duplicate(self._args)
        self.target = target
        renpy.display.render.redraw(self, 0)
        if not old_target:
            return True
        if not isinstance(old_target, renpy.display.motion.Transform):
            return True
        if not isinstance(target, renpy.display.motion.Transform):
            self.target = target = renpy.display.motion.Transform(child=target)
        target.take_state(old_target)
        return True

    def _duplicate(self, args):
        rv = self._copy(args)
        rv.target = None
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
