"""Style rules derived from the harvester's probes of Ren'Py's styles."""
from witch.renpy.styles import rules

ERR = {"error": "TypeError"}


def probes(**results):
    base = {"float": ERR, "tuple": ERR, "none": ERR, "left": ERR, "color": ERR, "image": ERR, "outlines": ERR,
            "true": ERR}
    base.update(results)
    return base


def test_copies_splits_constants_and_conversions():
    all_properties = {
        "xanchor": ["xanchor"],
        "xalign": ["xpos", "xanchor"],
        "pos": ["xpos", "ypos"],
        "xcenter": ["xpos", "xanchor"],
        "background": ["background"],
        "color": ["color"],
        "xpos": ["xpos"],
    }
    found = rules({
        "xanchor": probes(float=[0.3125], left=[0.0], none=[None]),
        "xalign": probes(float=[0.3125, 0.3125], left=["left", 0.0], none=[None, None]),
        "pos": probes(tuple=[0.0625, 0.125], left=["l", "e"]),
        "xcenter": probes(float=[0.3125, 0.5], left=["left", 0.5], none=[None, 0.5]),
        "background": probes(none=[None], color=[{"object": "renpy.display.imagelike.Solid"}], true=[None]),
        "color": probes(none=[None], color=[{"tuple": [255, 0, 0, 255]}]),
        "xpos": probes(float=[0.3125], left=["left"], none=[None]),
    }, all_properties)
    assert found["xalign"] == [["xpos", "value", None], ["xanchor", "value", "expand_anchor"]]
    assert found["pos"] == [["xpos", 0, None], ["ypos", 1, None]]
    assert found["xcenter"] == [["xpos", "value", None], ["xanchor", {"const": 0.5}, None]]
    assert found["background"] == [["background", "value", "displayable_or_none"]]
    assert found["color"] == [["color", "value", "color"]]
