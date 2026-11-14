# Per-frame Python callbacks (REWORK-PLAN §15, phase H), timed one kind at a
# time. Built twice: as bytecode and as native ARM code (`NATIVE` is set by
# the runner), to see what native compilation buys on the Old 3DS.
import gc
import math

from charm import ticks_us

FRAMES = 600
FRAME_MS = 2.0

try:
    NATIVE
except NameError:
    NATIVE = False


class Trans:
    def __init__(self):
        self.xpos = 0.5
        self.ypos = 1.0
        self.alpha = 1.0
        self.zoom = 1.0


class Glyph:
    def __init__(self, x, y, alpha):
        self.x = x
        self.y = y
        self.alpha = alpha


def bob(trans, st, at):
    trans.ypos = 1.0 + 0.01 * math.sin(st * 2.0)
    trans.zoom = 1.0 + 0.005 * math.cos(st * 1.5)
    return 0


def clock_text(st, at):
    return "Day %d, %02d:%02d" % (3, int(st) // 60 % 24, int(st) % 60), 0.1


def bounce_offsets(st):
    # The lightest form of Mice Tea's BounceText: one offset per glyph.
    return [int(4.0 * math.sin(st * 6.0 + i * 0.6)) for i in range(60)]


def bounce_objects(st):
    # Closer to what its render() does: a placed object per glyph per frame.
    return [Glyph(i * 8, 4.0 * math.sin(st * 6.0 + i * 0.6), 1.0) for i in range(60)]


sprites = [Trans() for _ in range(3)]


def three_bobs(st):
    for t in sprites:
        bob(t, st, st)


def one_clock(st):
    clock_text(st, st)


def everything(st):
    three_bobs(st)
    one_clock(st)
    bounce_offsets(st)


def measure(name, fn, limit=None):
    # Collections are kept out of the timed calls, one per 60 frames, and
    # what each call allocates is reported instead.
    times = []
    allocated = 0
    for f in range(FRAMES):
        if f % 60 == 0:
            gc.enable()
            gc.collect()
            gc.disable()
            before = gc.mem_alloc()
        st = f / 60.0
        t0 = ticks_us()
        fn(st)
        times.append(ticks_us() - t0)
        if f % 60 == 59:
            allocated += gc.mem_alloc() - before
    gc.enable()
    tag = "nat" if NATIVE else "bc"
    worst = max(times) / 1000.0
    text = "%-15s %-3s%6.3f mean%7.3f max" % (name, tag, sum(times) / len(times) / 1000.0, worst)
    if limit is not None:
        text += " " + ("PASS" if worst <= limit else "FAIL")
    print(text)
    print("%-19s%6.2f KB allocated/frame" % ("", allocated / 1024.0 / FRAMES))


measure("3 ATL functions", three_bobs)
measure("clock text", one_clock)
measure("bounce offsets", bounce_offsets)
measure("bounce objects", bounce_objects)
measure("H.1 frame total", everything, FRAME_MS)
