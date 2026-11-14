"""renpy.text.text: Text, the description of a run of text. Its layout,
glyphs and typing out are the engine's (REWORK-PLAN §8.4); what's kept
here is what Ren'Py 7.0's Text keeps once substitutions are made."""
import renpy
from renpy import missing_attribute


class Text(renpy.display.core.Displayable):
    __version__ = 4
    _uses_scope = True
    _duplicatable = False
    locked = False
    language = None

    def __init__(self, text, slow=None, scope=None, substitute=None, slow_done=None, replaces=None, **properties):
        super(Text, self).__init__(**properties)
        if not isinstance(text, list):
            text = [text]
        for i in text:
            if not isinstance(i, (str, renpy.display.core.Displayable)):
                if renpy.config.developer:
                    raise Exception("Cannot display {0!r} as text.".format(i))
                text = [""]
                break
        self.substitute = substitute
        self.dirty = True
        self.text = None
        self.set_text(text, scope, substitute)
        if renpy.game.less_updates or renpy.game.preferences.self_voicing:
            slow = False
        self.slow = slow
        self.slow_done = None
        self.ctc = None
        self.start = None
        self.end = None
        if replaces is not None:
            self.slow = replaces.slow
            self.slow_done = replaces.slow_done
            self.ctc = replaces.ctc
            self.start = replaces.start
            self.end = replaces.end
        self.displayables = None
        self._duplicatable = self.slow

    def set_text(self, text, scope=None, substitute=False, update=True):
        if self.locked:
            return
        self.language = renpy.game.preferences.language
        old_text = self.text
        if not isinstance(text, list):
            text = [text]
        self.text_parameter = text
        new_text = []
        uses_scope = False
        for i in text:
            if isinstance(i, str):
                if substitute is not False:
                    i, did_sub = renpy.substitutions.substitute(i, scope, substitute)
                    uses_scope = uses_scope or did_sub
            new_text.append(i)
        self._uses_scope = uses_scope
        if new_text == old_text:
            return False
        if update:
            self.text = new_text
            # Ren'Py asks for a redraw here; the engine redraws text whose
            # description changed.
            self.dirty = True
        return True


def __getattr__(name):
    return missing_attribute("renpy.text.text", name)
