"""Placeholders for Ren'Py APIs the shim doesn't implement yet.

Any renpy.* name the shim lacks resolves to a Missing, which records each use
(with the init statement running at the time) and keeps going, so one run
lists everything a game needs instead of stopping at the first gap. Nothing
about a Missing is meant to behave like the real API; the report is the point.
"""

uses = {}  # "renpy.x.y" -> [count, [(file, line), ...]]
where = None  # (file, line) of the statement being run, set by the driver


def record(path):
    entry = uses.get(path)
    if entry is None:
        entry = uses[path] = [0, []]
    entry[0] += 1
    if where is not None and len(entry[1]) < 5 and where not in entry[1]:
        entry[1].append(where)


class Missing:
    def __init__(self, path):
        self._path = path
        record(path)

    def __getattr__(self, name):
        return Missing(self._path + "." + name)

    def __call__(self, *args, **kwargs):
        return Missing(self._path + "()")

    def __repr__(self):
        return "<missing %s>" % self._path


def report():
    return dict((path, {"count": c, "sites": sites}) for path, (c, sites) in uses.items())
