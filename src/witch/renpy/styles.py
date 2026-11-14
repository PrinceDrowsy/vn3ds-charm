"""Style property rules, derived from the harvester's probes of the game's
own Ren'Py (harvest.rpy, style_probes): for each property, what it sets
and how (REWORK-PLAN §6.3). Ren'Py generates and compiles this code, so the
probes are the only way to read it.

A rule is a list of [target, source, function]: `source` is "value" (the
whole value), an index into a tuple value, or {"const": c}; `function` is
the conversion Ren'Py applies (see FUNCTIONS), or None.
"""
from __future__ import annotations

# The conversions Ren'Py's style properties use (renpy/styledata/styleutil.py
# and renpy.easy), told apart by what they make of each probe.
FUNCTIONS = ("expand_anchor", "color", "displayable_or_none", "none_is_null", "expand_focus_mask", "expand_outlines")


def _ok(probe) -> bool:
    return not (isinstance(probe, dict) and "error" in probe)


def _source(prop: str, index: int, probes: dict):
    """Where a target's value comes from: an element of a tuple value, the
    whole value, or a constant whatever is set (`xcenter` sets xanchor to
    0.5, `area` sets xfill)."""
    tup = probes["tuple"]
    if _ok(tup):
        sent = [0.0625 * (i + 1) for i in range(len(tup))]
        out = tup[index]
        if out in sent:
            return sent.index(out)
    seen = [p[index] for p in probes.values() if _ok(p)]
    if len(seen) > 1 and all(v == seen[0] for v in seen):
        return {"const": seen[0]}
    return "value"


def _function(probes: dict) -> str | None:
    """The conversion a single-target property applies to its value."""
    def got(kind):
        p = probes.get(kind)
        return p[0] if _ok(p) else None

    left, color, true, none, outlines = got("left"), got("color"), got("true"), got("none"), got("outlines")
    if left == 0.0:
        return "expand_anchor"
    if color == {"tuple": [255, 0, 0, 255]}:
        return "color"
    if isinstance(color, dict) and color.get("object", "").endswith("Solid"):
        if true is True:
            return "expand_focus_mask"
        if isinstance(none, dict) and none.get("object", "").endswith("Null"):
            return "none_is_null"
        return "displayable_or_none"
    if isinstance(outlines, dict) and outlines.get("list") and len(outlines["list"][0].get("tuple", [])) == 4:
        return "expand_outlines"
    return None


def rules(probes: dict, all_properties: dict) -> dict:
    """Ren'Py converts by the property set, not the one named: a target's
    conversion is the one its own single-target property shows."""
    functions = dict((prop, _function(probes[prop])) for prop, targets in all_properties.items()
                     if targets == [prop])
    out = {}
    for prop, targets in all_properties.items():
        rule = []
        for i, target in enumerate(targets):
            source = _source(prop, i, probes[prop])
            rule.append([target, source, None if isinstance(source, dict) else functions.get(target)])
        out[prop] = rule
    return out
