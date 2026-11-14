# Phase H workload (REWORK-PLAN §15, D21). Runs under MicroPython on the 3DS
# and on the desktop. It stands in for Mice Tea's post-init Python, sized from
# its scripts: 53 layered characters resolved through attribute-conflict sets
# like its CharacterImage, 1387 image names, 317 defines, 43 defaults, a
# 250-entry history and a rollback snapshot per interaction. Real game code
# needs the renpy shim (R2); R2's conformance suite reruns this with it.
import gc

from charm import ticks_us

_setup_start = ticks_us()

INTERACTION_MS = 50.0
HEAP_MB = 12.0
ROLLBACK_LENGTH = 128  # Ren'Py's config.rollback_length
HISTORY_LENGTH = 250  # Ren'Py's config.history_length


def line(name, value, unit, limit=None):
    # Short enough for the 50-column top-screen console.
    text = "%-24s%9.3f %-2s" % (name, value, unit)
    if limit is not None:
        text += " <=%-3g %s" % (limit, "PASS" if value <= limit else "FAIL")
    print(text)


class Seeded:
    """A small LCG, so every run builds the same data on every platform."""

    def __init__(self, seed):
        self.state = seed

    def next(self, n):
        self.state = (self.state * 1103515245 + 12345) & 0x7FFFFFFF
        return self.state % n


rng = Seeded(1)
NOTHING = frozenset()


class LayeredCharacter:
    GROUPS = (("base", 9), ("arms", 7), ("eyes", 10), ("mouth", 9), ("tail", 3), ("hat", 4), ("blush", 2))

    def __init__(self, name):
        self.name = name
        self.attribute_sets = tuple(frozenset("%s_%d" % (g, i) for i in range(n)) for g, n in self.GROUPS)
        emotions = ("happy", "sad", "angry", "surprised", "worried", "smug", "shy", "tired",
                    "neutral", "upset", "nervous", "pout", "huff", "coo", "squint", "wide")
        self.aliases = {}
        for k, emotion in enumerate(emotions):
            self.aliases[emotion] = frozenset(("eyes_%d" % (k % 10), "mouth_%d" % (k % 9)))
        self.layer_order = {}
        for attr_set in self.attribute_sets:
            for attr in sorted(attr_set):
                self.layer_order[attr] = len(self.layer_order)
        self.files = {attr: "characters/%s/%s.png" % (name, attr) for attr in self.layer_order}
        self.conflicts = {}
        for attr_set in self.attribute_sets:
            for attr in attr_set:
                self.conflicts[attr] = attr_set - {attr}
        self.alias_conflicts = {}
        for alias, attrs in self.aliases.items():
            hit = set()
            for attr_set in self.attribute_sets:
                if attr_set & attrs:
                    hit |= attr_set
            self.alias_conflicts[alias] = hit

    def banned(self, attrs):
        out = {"_"}
        for attr in attrs:
            out |= self.alias_conflicts.get(attr) or self.conflicts.get(attr, NOTHING)
        return out

    def choose(self, required, optional):
        required = set(required)
        if required & self.banned(required):
            raise ValueError("conflicting attributes")
        optional = set(optional)
        for attr in required:
            optional -= self.alias_conflicts.get(attr) or self.conflicts.get(attr, NOTHING)
        return tuple(sorted(required | optional))

    def compose(self, attrs):
        expanded = set()
        banned = self.banned(attrs)
        for attr in attrs:
            if attr in self.aliases:
                expanded |= self.aliases[attr] - banned
            else:
                expanded.add(attr)
        layers = sorted(expanded, key=lambda a: self.layer_order.get(a, 0))
        return [(self.files[a], 0, 0) for a in layers if a in self.files]


class Obj:
    pass


class Persistent:
    def __getattr__(self, name):
        return None


persistent = Persistent()
persistent.skip_sex = "prompt"
persistent.felicia_finished = True
persistent.content_warning = False
for k in range(30):
    setattr(persistent, "unlock_%d" % k, k % 3 == 0)

characters = [LayeredCharacter("char%d" % k) for k in range(53)]

images = {}
while len(images) < 1387:
    c = characters[rng.next(53)]
    attrs = (c.name,) + tuple(sorted({"eyes_%d" % rng.next(10), "mouth_%d" % rng.next(9), "base_%d" % rng.next(9)}))
    images[attrs] = Obj()
    images[attrs].file = "images/%s.png" % "_".join(attrs)

defines = {}
for k in range(317):
    kind = k % 4
    if kind == 0:
        speaker = Obj()
        speaker.name = "Speaker %d" % k
        speaker.properties = {"color": "#%06x" % (k * 4111 & 0xFFFFFF), "what_prefix": "", "what_suffix": "",
                              "who_outlines": [(2, "#000", 0, 0)], "image": "char%d" % (k % 53),
                              "ctc": "ctc_arrow", "voice_tag": "v%d" % k, "kind": "adv"}
        defines["speaker_%d" % k] = speaker
    elif kind == 1:
        defines["text_%d" % k] = "Some defined text for slot %d, long enough to be a real string." % k
    elif kind == 2:
        defines["pos_%d" % k] = (0.1 * (k % 10), 1.0, 0.5, 1.0)
    else:
        defines["table_%d" % k] = {"day%d" % d: [d, d * 2, "evening"] for d in range(8)}

player_name = "Gav"
cat_name = "Felicia"
day = 3
points = 0
cat_scratch = False
smolgaret = False
felicia_short = False
cameo = "regys"
defaults = {"flag_%d" % k: k % 2 == 0 for k in range(35)}
defaults.update({"player_name": player_name, "cat_name": cat_name, "day": day, "points": points,
                 "cat_scratch": cat_scratch, "smolgaret": smolgaret, "felicia_short": felicia_short, "cameo": cameo})

history = []

labels = {"day%d_%s" % (d, part): d * 100 + len(part) for d in range(1, 8) for part in
          ("morning", "noon", "evening", "night", "cafe", "park", "home", "shop")}

MENU = (
    ("Scratch the cat", lambda: cat_scratch),
    ("Skip the scene", lambda: persistent.skip_sex == "prompt"),
    ("Visit Felicia", lambda: persistent.felicia_finished and not felicia_short),
    ("Talk to the cameo", lambda: cameo == "regys" or cameo == "tharkis"),
    ("Go home", lambda: True),
)

LINES = (
    "[player_name] glances at [cat_name]. It's day [day] and I have [points] points.",
    "\"[cat_name], wait!\" [[not a substitution] I call out.",
    "[speaker_4.name] says the shop opens on day [day].",
)


def substitute(text, scope):
    """Ren'Py-style [field] substitution: dotted lookups, [[ escapes."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "[":
            if i + 1 < n and text[i + 1] == "[":
                out.append("[")
                i += 2
                continue
            j = text.index("]", i)
            path = text[i + 1:j].split(".")
            value = scope[path[0]] if path[0] in scope else defines[path[0]]
            for part in path[1:]:
                value = getattr(value, part)
            out.append(str(value))
            i = j + 1
        else:
            j = text.find("[", i)
            if j < 0:
                j = n
            out.append(text[i:j])
            i = j
    return "".join(out)


def serialize(value, out):
    """The shape of the D19 store serializer; written in Python here, so this
    is an upper bound on its cost."""
    t = type(value)
    if value is None or t is bool:
        out.append(0 if value is None else 1 + value)
    elif t is int:
        out.append(3)
        out.extend(value.to_bytes(8, "little", signed=True) if -0x40000000 <= value < 0x40000000 else str(value).encode())
    elif t is float:
        out.append(4)
        out.extend(repr(value).encode())
    elif t is str:
        b = value.encode()
        out.append(5)
        out.extend(len(b).to_bytes(4, "little"))
        out.extend(b)
    elif t is list or t is tuple:
        out.append(6 if t is list else 7)
        out.extend(len(value).to_bytes(4, "little"))
        for v in value:
            serialize(v, out)
    elif t is dict:
        out.append(8)
        out.extend(len(value).to_bytes(4, "little"))
        for k in sorted(value):
            serialize(k, out)
            serialize(value[k], out)
    else:
        serialize(value.__dict__, out)
    return out


rollback = []


def interaction(k):
    global points, cat_scratch
    scope = globals()
    what = substitute(LINES[k % len(LINES)], scope)
    who = defines["speaker_%d" % (4 * (k % 79))]
    history.append((who.name, what))
    if len(history) > HISTORY_LENGTH:
        history.pop(0)

    # `show charN happy base_3` twice, as most lines change a sprite or two.
    for c in (characters[k % 53], characters[(k * 7) % 53]):
        attrs = c.choose(("happy",), ("base_3", "arms_2", "tail_1"))
        c.compose(attrs)
        images.get((c.name,) + attrs[:3])

    choices = [label for label, cond in MENU if cond()]
    target = labels["day%d_%s" % (1 + k % 7, ("cafe", "park", "home")[k % 3])]

    points += 1
    cat_scratch = k % 5 == 0
    defaults["points"] = points
    defaults["cat_scratch"] = cat_scratch
    snapshot = bytes(serialize((defaults, history[-1], persistent.__dict__), bytearray()))
    rollback.append(snapshot)
    if len(rollback) > ROLLBACK_LENGTH:
        rollback.pop(0)
    return len(choices) + target


def main(setup_us):
    line("setup (build store)", setup_us / 1000.0, "ms")

    gc.collect()
    t0 = ticks_us()
    gc.collect()
    line("gc.collect, full store", (ticks_us() - t0) / 1000.0, "ms")

    # The engine collects between interactions, never during one (§6).
    times = []
    gc_times = []
    for k in range(300):
        t0 = ticks_us()
        interaction(k)
        t1 = ticks_us()
        gc.collect()
        times.append(t1 - t0)
        gc_times.append(ticks_us() - t1)
    times = times[ROLLBACK_LENGTH:]  # once the rollback ring is full
    gc_times = gc_times[ROLLBACK_LENGTH:]
    line("interaction, mean", sum(times) / len(times) / 1000.0, "ms")
    line("interaction, worst", max(times) / 1000.0, "ms", INTERACTION_MS)
    line("gc between lines, max", max(gc_times) / 1000.0, "ms")
    line("rollback snapshot", len(rollback[-1]) / 1024.0, "KB")

    gc.collect()
    line("heap in use", gc.mem_alloc() / 1048576.0, "MB", HEAP_MB)
    line("heap free", gc.mem_free() / 1048576.0, "MB")


def gc_only():
    """GC cost alone, for comparing heap sizes: fill the rollback ring
    without collecting, then time full collections."""
    for k in range(ROLLBACK_LENGTH + 10):
        interaction(k)
    gc.collect()
    worst = 0
    for _ in range(5):
        t0 = ticks_us()
        gc.collect()
        worst = max(worst, ticks_us() - t0)
    size = (gc.mem_alloc() + gc.mem_free()) / 1048576.0
    line("gc.collect @ %2d MB heap" % round(size), worst / 1000.0, "ms")


try:
    MODE
except NameError:
    MODE = "full"
if MODE == "gc":
    gc_only()
else:
    main(ticks_us() - _setup_start)
