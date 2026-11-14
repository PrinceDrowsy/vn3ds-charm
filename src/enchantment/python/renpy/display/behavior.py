"""renpy.display.behavior: buttons, bars, timers and the other screen
widgets, as descriptions (constructors as Ren'Py 7.0's), and the action
protocol screens run in the VM (run, is_selected, is_sensitive). The
engine does focus, input and drawing (REWORK-PLAN §8.3, §8.5). Input,
whose constructor edits text, is still a placeholder."""
import renpy
from renpy import missing_attribute

adj_registered = {}


def _div(a, b):
    # This code ran on Python 2 in Ren'Py 7, where int / int floors.
    return renpy.py2.py2_div(a, b) if renpy.revertable.PY2 else a / b


def predict_action(var):
    if var is None:
        return
    if isinstance(var, renpy.ui.Action):
        var.predict()
    if isinstance(var, (list, tuple)):
        for i in var:
            predict_action(i)


def run(action, *args, **kwargs):
    if action is None:
        return None
    if isinstance(action, (list, tuple)):
        rv = None
        for i in action:
            new_rv = run(i, *args, **kwargs)
            if new_rv is not None:
                rv = new_rv
        return rv
    return action(*args, **kwargs)


def run_unhovered(var):
    if var is None:
        return None
    if isinstance(var, (list, tuple)):
        for i in var:
            run_unhovered(i)
        return
    f = getattr(var, "unhovered", None)
    if f is not None:
        f()


def run_periodic(var, st):
    if isinstance(var, (list, tuple)):
        rv = None
        for i in var:
            v = run_periodic(i, st)
            if rv is None or v < rv:
                rv = v
        return rv
    if isinstance(var, renpy.ui.Action):
        return var.periodic(st)


def is_selected(action):
    if isinstance(action, (list, tuple)):
        for i in action:
            if isinstance(i, renpy.store.SelectedIf):
                return i.get_selected()
        return any(is_selected(i) for i in action)
    elif isinstance(action, renpy.ui.Action):
        return action.get_selected()
    else:
        return False


def is_sensitive(action):
    if isinstance(action, (list, tuple)):
        for i in action:
            if isinstance(i, renpy.store.SensitiveIf):
                return i.get_sensitive()
        return all(is_sensitive(i) for i in action)
    elif isinstance(action, renpy.ui.Action):
        return action.get_sensitive()
    else:
        return True


class Keymap(renpy.display.layout.Null):
    def __init__(self, replaces=None, activate_sound=None, **keymap):
        if activate_sound is not None:
            super(Keymap, self).__init__(style='default', activate_sound=activate_sound)
        else:
            super(Keymap, self).__init__(style='default')
        self.keymap = keymap


class RollForward(renpy.display.layout.Null):
    def __init__(self, value, **properties):
        super(RollForward, self).__init__(**properties)
        self.value = value


class PauseBehavior(renpy.display.layout.Null):
    voice = False

    def __init__(self, delay, result=False, voice=False, **properties):
        super(PauseBehavior, self).__init__(**properties)
        self.delay = delay
        self.result = result
        self.voice = voice


class SoundStopBehavior(renpy.display.layout.Null):
    def __init__(self, channel, result=False, **properties):
        super(SoundStopBehavior, self).__init__(**properties)
        self.channel = channel
        self.result = result


class SayBehavior(renpy.display.layout.Null):
    focusable = True
    text = None
    dismiss_unfocused = ['dismiss_unfocused']

    def __init__(self, default=True, afm=None, dismiss=['dismiss'], allow_dismiss=None, dismiss_unfocused=['dismiss_unfocused'], **properties):
        super(SayBehavior, self).__init__(default=default, **properties)
        if not isinstance(dismiss, (list, tuple)):
            dismiss = [dismiss]
        if afm is not None:
            self.afm_length = len(afm)
        else:
            self.afm_length = None
        self.dismiss = dismiss
        self.allow_dismiss = allow_dismiss


class Button(renpy.display.layout.Window):
    keymap = {}
    action = None
    alternate = None
    longpress_start = None
    longpress_x = None
    longpress_y = None
    role_parameter = None
    keysym = None
    alternate_keysym = None

    def __init__(self, child=None, style='button', clicked=None,
                 hovered=None, unhovered=None, action=None, role=None,
                 time_policy=None, keymap={}, alternate=None,
                 selected=None, sensitive=None, keysym=None, alternate_keysym=None,
                 **properties):
        if isinstance(clicked, renpy.ui.Action):
            action = clicked
        super(Button, self).__init__(child, style=style, **properties)
        self.action = action
        self.selected = selected
        self.sensitive = sensitive
        self.clicked = clicked
        self.hovered = hovered
        self.unhovered = unhovered
        self.alternate = alternate
        self.focusable = True  # (clicked is not None) or (action is not None)
        self.role_parameter = role
        self.keymap = keymap
        self.keysym = keysym
        self.alternate_keysym = alternate_keysym
        self.time_policy_data = None
        self._duplicatable = False


def TextButton(text, style='button', text_style='button_text',
               clicked=None, **properties):
    text = renpy.text.text.Text(text, style=text_style)
    return Button(text, style=style, clicked=clicked, **properties)


class ImageButton(Button):
    def __init__(self,
                 idle_image,
                 hover_image=None,
                 insensitive_image=None,
                 activate_image=None,
                 selected_idle_image=None,
                 selected_hover_image=None,
                 selected_insensitive_image=None,
                 selected_activate_image=None,
                 style='image_button',
                 clicked=None,
                 hovered=None,
                 **properties):
        hover_image = hover_image or idle_image
        insensitive_image = insensitive_image or idle_image
        activate_image = activate_image or hover_image
        selected_idle_image = selected_idle_image or idle_image
        selected_hover_image = selected_hover_image or hover_image
        selected_insensitive_image = selected_insensitive_image or insensitive_image
        selected_activate_image = selected_activate_image or activate_image
        self.state_children = dict(
            idle_=renpy.easy.displayable(idle_image),
            hover_=renpy.easy.displayable(hover_image),
            insensitive_=renpy.easy.displayable(insensitive_image),
            activate_=renpy.easy.displayable(activate_image),
            selected_idle_=renpy.easy.displayable(selected_idle_image),
            selected_hover_=renpy.easy.displayable(selected_hover_image),
            selected_insensitive_=renpy.easy.displayable(selected_insensitive_image),
            selected_activate_=renpy.easy.displayable(selected_activate_image),
            )
        super(ImageButton, self).__init__(None,
                                          style=style,
                                          clicked=clicked,
                                          hovered=hovered,
                                          **properties)


class HoveredProxy(object):
    def __init__(self, a, b):
        self.a = a
        self.b = b


class Adjustment(renpy.object.Object):
    def __init__(self, range=1, value=0, step=None, page=None, changed=None, adjustable=None, ranged=None):
        super(Adjustment, self).__init__()
        if adjustable is None:
            if changed:
                adjustable = True
        self._value = value
        self._range = range
        self._page = page
        self._step = step
        self.changed = changed
        self.adjustable = adjustable
        self.ranged = ranged

    def get_value(self):
        if self._value > self._range:
            return self._range
        return self._value

    def set_value(self, v):
        self._value = v
    value = property(get_value, set_value)

    def get_range(self):
        return self._range

    def set_range(self, v):
        self._range = v
        if self.ranged:
            self.ranged(self)
    range = property(get_range, set_range)

    def get_page(self):
        if self._page is not None:
            return self._page
        return _div(self._range, 10)

    def set_page(self, v):
        self._page = v
    page = property(get_page, set_page)

    def get_step(self):
        if self._step is not None:
            return self._step
        if self._page is not None and self.page > 0:
            return _div(self._page, 10)
        if isinstance(self._range, float):
            return _div(self._range, 10)
        else:
            return 1

    def set_step(self, v):
        self._step = v
    step = property(get_step, set_step)

    def register(self, d):
        adj_registered.setdefault(self, []).append(d)

    def change(self, value):
        if value < 0:
            value = 0
        if value > self._range:
            value = self._range
        if value != self._value:
            self._value = value
            for d in adj_registered.setdefault(self, []):
                renpy.display.render.redraw(d, 0)
            if self.changed:
                return self.changed(value)
        return None

    def update(self):
        for d in adj_registered.setdefault(self, []):
            renpy.display.render.redraw(d, 0)


class Bar(renpy.display.core.Displayable):
    __version__ = 2

    def __init__(self,
                 range=None,
                 value=None,
                 width=None,
                 height=None,
                 changed=None,
                 adjustment=None,
                 step=None,
                 page=None,
                 bar=None,
                 style=None,
                 vertical=False,
                 replaces=None,
                 hovered=None,
                 unhovered=None,
                 **properties):
        self.value = None
        if adjustment is None:
            if isinstance(value, renpy.ui.BarValue):
                if isinstance(replaces, Bar):
                    value.replaces(replaces.value)
                self.value = value
                adjustment = value.get_adjustment()
                renpy.game.interface.timeout(0)
            else:
                adjustment = Adjustment(range, value, step=step, page=page, changed=changed)
        if style is None:
            if self.value is not None:
                if vertical:
                    style = self.value.get_style()[1]
                else:
                    style = self.value.get_style()[0]
            else:
                if vertical:
                    style = 'vbar'
                else:
                    style = 'bar'
        if width is not None:
            properties['xmaximum'] = width
        if height is not None:
            properties['ymaximum'] = height
        super(Bar, self).__init__(style=style, **properties)
        self.adjustment = adjustment
        self.focusable = True
        self.thumb_dim = 0
        self.height = 0
        self.width = 0
        self.hidden = False
        self.hovered = hovered
        self.unhovered = unhovered


class Conditional(renpy.display.layout.Container):
    def __init__(self, condition, *args, **properties):
        super(Conditional, self).__init__(*args, **properties)
        self.condition = condition
        self.null = renpy.display.layout.Null()
        self.state = eval(self.condition, vars(renpy.store))


class TimerState(renpy.python.RevertableObject):
    started = False
    next_event = None


class Timer(renpy.display.layout.Null):
    __version__ = 1
    started = False

    def __init__(self, delay, action=None, repeat=False, args=(), kwargs={}, replaces=None, **properties):
        super(Timer, self).__init__(**properties)
        if action is None:
            raise Exception("A timer must have an action supplied.")
        if delay <= 0:
            raise Exception("A timer's delay must be > 0.")
        self.delay = delay
        self.repeat = repeat
        self.next_event = None
        self.function = action
        self.args = args
        self.kwargs = kwargs
        self.started = False
        if replaces is not None:
            self.state = replaces.state
        else:
            self.state = TimerState()


class MouseArea(renpy.display.core.Displayable):
    at_st_offset = 0

    def __init__(self, hovered=None, unhovered=None, replaces=None, **properties):
        super(MouseArea, self).__init__(**properties)
        self.hovered = hovered
        self.unhovered = unhovered
        self.is_hovered = False
        if replaces is not None:
            self.is_hovered = replaces.is_hovered
        self.width = 0
        self.height = 0


class OnEvent(renpy.display.core.Displayable):
    def __init__(self, event, action=[]):
        super(OnEvent, self).__init__()
        self.event_name = event
        self.action = action


def __getattr__(name):
    return missing_attribute("renpy.display.behavior", name)
