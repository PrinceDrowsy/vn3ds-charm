"""Characters (renpy.character). The constructor is Ren'Py 7.0's: it
computes the who/what/window/show/cb argument sets from the character's
kind, which is all a Character is until it speaks. Speaking is native
(REWORK-PLAN §8.2)."""
import collections

import renpy
from renpy import missing_attribute

NotSet = renpy.object.Sentinel("NotSet")


class ADVCharacter(object):
    special_properties = [
        'what_prefix',
        'what_suffix',
        'who_prefix',
        'who_suffix',
        'show_function',
    ]

    voice_tag = None
    properties = {}

    def __init__(self, name=NotSet, kind=None, **properties):
        if kind is None:
            kind = renpy.store.adv
        if name is not NotSet:
            properties["name"] = name

        def v(n):
            if n in properties:
                return properties.pop(n)
            return getattr(kind, n)

        def d(n):
            if n in properties:
                return properties.pop(n)
            return kind.display_args[n]

        self.name = v('name')
        self.who_prefix = v('who_prefix')
        self.who_suffix = v('who_suffix')
        self.what_prefix = v('what_prefix')
        self.what_suffix = v('what_suffix')
        self.show_function = v('show_function')
        self.predict_function = v('predict_function')
        self.condition = v('condition')
        self.dynamic = v('dynamic')
        self.screen = v('screen')
        self.mode = v('mode')
        self.voice_tag = v('voice_tag')

        if renpy.config.new_character_image_argument:
            if "image" in properties:
                self.image_tag = properties.pop("image")
            else:
                self.image_tag = kind.image_tag
        else:
            self.image_tag = None

        self.display_args = dict(
            interact=d('interact'),
            slow=d('slow'),
            afm=d('afm'),
            ctc=renpy.easy.displayable_or_none(d('ctc')),
            ctc_pause=renpy.easy.displayable_or_none(d('ctc_pause')),
            ctc_timedpause=renpy.easy.displayable_or_none(d('ctc_timedpause')),
            ctc_position=d('ctc_position'),
            all_at_once=d('all_at_once'),
            with_none=d('with_none'),
            callback=d('callback'),
            type=d('type'),
            advance=d('advance'),
        )

        self.properties = collections.defaultdict(dict)

        if kind:
            self.who_args = kind.who_args.copy()
            self.what_args = kind.what_args.copy()
            self.window_args = kind.window_args.copy()
            self.show_args = kind.show_args.copy()
            self.cb_args = kind.cb_args.copy()
            for k, val in kind.properties.items():
                self.properties[k] = dict(val)
        else:
            self.who_args = {"substitute": False}
            self.what_args = {"substitute": False}
            self.window_args = {}
            self.show_args = {}
            self.cb_args = {}

        if not renpy.config.new_character_image_argument:
            if "image" in properties:
                self.show_args["image"] = properties.pop("image")

        if "slow_abortable" in properties:
            self.what_args["slow_abortable"] = properties.pop("slow_abortable")

        prefixes = ["show", "cb", "what", "window", "who"] + renpy.config.character_id_prefixes
        split_args = [i + "_" for i in prefixes] + [""]
        split = renpy.easy.split_properties(properties, *split_args)
        for prefix, props in zip(prefixes, split):
            self.properties[prefix].update(props)
        self.properties["who"].update(split[-1])

        self.show_args.update(self.properties.pop("show"))
        self.cb_args.update(self.properties.pop("cb"))
        self.what_args.update(self.properties.pop("what"))
        self.window_args.update(self.properties.pop("window"))
        self.who_args.update(self.properties.pop("who"))


def Character(name=NotSet, kind=None, **properties):
    if kind is None:
        kind = renpy.store.adv
    return type(kind)(name, kind=kind, **properties)


def DynamicCharacter(name_expr, **properties):
    return Character(name_expr, dynamic=True, **properties)


def __getattr__(name):
    return missing_attribute("renpy.character", name)
