"""The description vocabulary (REWORK-PLAN §6.3): for each kind of record,
the classes that lower to it and the attributes that define it.

One declaration, read by both sides: the harvester lowers the objects of
the game's own Ren'Py with it (harvest.rpy), the shim lowers its
descriptions with it (charm_lower.py), and Witch compares the records
(witch/python/compare.py). An attribute is a name, or [name, tag] where
the two sides hold it differently:

- "atl": the ATL block, lowered to the node of the statement that owns it.
- "parameters": a transform's parameters, lowered to their signature.

Attributes hold what a displayable was built to show; what Ren'Py keeps
while it runs (times, sizes, caches) stays out. Classes are named as
Ren'Py 7.0 names them; a subclass lowers as its nearest listed base, with
its own class noted.
"""
from __future__ import annotations

_IM = ["style"]
_TRANSITION = ["delay", "old_widget", "new_widget"]
_ZOOM = ["time", "child", "after_child", "time_warp", "bilinear", "opaque", "anim_timebase", "repeat", "style"]
_TRANSFORM = ["child", "function", "style_arg", "arguments", "state", "style"]

# kind, classes, attributes
KINDS = (
    ("null", ["renpy.display.layout.Null"], ["width", "height", "style"]),
    ("position", ["renpy.display.layout.Position"], ["children", "style"]),
    ("multibox", ["renpy.display.layout.MultiBox"], ["children", "default_layout", "style"]),
    ("window", ["renpy.display.layout.Window"], ["children", "style"]),
    ("grid", ["renpy.display.layout.Grid"], ["children", "cols", "rows", "transpose", "style"]),
    ("side", ["renpy.display.layout.Side"], ["children", "positions", "style"]),
    ("alpha", ["renpy.display.layout.Alpha"],
     ["start", "end", "time", "child", "repeat", "anim_timebase", "time_warp", "style"]),
    ("tile", ["renpy.display.layout.Tile"], ["children", "style"]),
    ("flatten", ["renpy.display.layout.Flatten"], ["children", "style"]),
    ("alpha_mask", ["renpy.display.layout.AlphaMask"], ["children", "mask", "style"]),
    ("dynamic", ["renpy.display.layout.DynamicDisplayable"], ["function", "args", "kwargs", "style"]),

    ("solid", ["renpy.display.imagelike.Solid"], ["color", "style"]),
    ("frame", ["renpy.display.imagelike.Frame"], ["image", "left", "top", "right", "bottom", "tile", "style"]),

    ("im_image", ["renpy.display.im.Image"], ["filename"] + _IM),
    ("im_composite", ["renpy.display.im.Composite"], ["size", "positions", "images"] + _IM),
    ("im_scale", ["renpy.display.im.Scale"], ["image", "width", "height", "bilinear"] + _IM),
    ("im_factor_scale", ["renpy.display.im.FactorScale"], ["image", "width", "height", "bilinear"] + _IM),
    ("im_flip", ["renpy.display.im.Flip"], ["image", "horizontal", "vertical"] + _IM),
    ("im_rotozoom", ["renpy.display.im.Rotozoom"], ["image", "angle", "zoom"] + _IM),
    ("im_crop", ["renpy.display.im.Crop"], ["image", "x", "y", "w", "h"] + _IM),
    ("im_map", ["renpy.display.im.Map"], ["image", "rmap", "gmap", "bmap", "amap", "force_alpha"] + _IM),
    ("im_twocolor", ["renpy.display.im.Twocolor"], ["image", "white", "black", "force_alpha"] + _IM),
    ("im_recolor", ["renpy.display.im.Recolor"], ["image", "rmul", "gmul", "bmul", "amul", "force_alpha"] + _IM),
    ("im_matrix_color", ["renpy.display.im.MatrixColor"], ["image", "matrix"] + _IM),
    ("im_tile", ["renpy.display.im.Tile"], ["image", "size"] + _IM),
    ("im_alpha_mask", ["renpy.display.im.AlphaMask"], ["base", "mask"] + _IM),

    ("image_reference", ["renpy.display.image.ImageReference"], ["name", "style"]),
    ("dynamic_image", ["renpy.display.image.DynamicImage"], ["name", "style"]),

    ("text", ["renpy.text.text.Text"], ["text", "slow", "substitute", "style"]),
    ("parameterized_text", ["renpy.text.extras.ParameterizedText"], ["style", "properties"]),

    ("transform", ["renpy.display.transform.Transform"], _TRANSFORM),
    ("atl_transform", ["renpy.display.transform.ATLTransform"],
     _TRANSFORM + [["atl", "atl"], "context", ["parameters", "parameters"]]),
    ("transform_state", ["renpy.display.transform.TransformState"],
     ["alpha", "nearest", "additive", "rotate", "rotate_pad", "transform_anchor", "zoom", "xzoom", "yzoom", "xpos",
      "ypos", "xanchor", "yanchor", "xoffset", "yoffset", "xaround", "yaround", "xanchoraround", "yanchoraround",
      "xpan", "ypan", "xtile", "ytile", "subpixel", "crop", "crop_relative", "corner1", "corner2", "size",
      "maxsize", "delay", "debug", "events"]),
    ("atl_context", ["renpy.atl.Context"], ["context"]),

    ("no_transition", ["renpy.display.transition.NoTransition"], _TRANSITION),
    ("multiple_transition", ["renpy.display.transition.MultipleTransition"],
     ["delay", "transitions", "screens", "new_widget"]),
    ("pixellate", ["renpy.display.transition.Pixellate"], _TRANSITION + ["time", "steps", "quantum"]),
    ("dissolve", ["renpy.display.transition.Dissolve"], _TRANSITION + ["time", "alpha", "time_warp"]),
    ("image_dissolve", ["renpy.display.transition.ImageDissolve"],
     _TRANSITION + ["image", "ramplen", "alpha", "time_warp"]),
    ("alpha_dissolve", ["renpy.display.transition.AlphaDissolve"], _TRANSITION + ["control", "alpha", "reverse"]),
    ("crop_move", ["renpy.display.transition.CropMove"],
     _TRANSITION + ["time", "startpos", "endpos", "startcrop", "endcrop", "topnew", "top", "bottom"]),
    ("push_move", ["renpy.display.transition.PushMove"],
     _TRANSITION + ["time", "new_startpos", "new_startcrop", "new_endpos", "new_endcrop", "old_startpos",
                    "old_startcrop", "old_endpos", "old_endcrop"]),

    ("motion", ["renpy.display.motion.Motion"],
     ["function", "period", "children", "repeat", "bounce", "delay", "anim_timebase", "time_warp", "add_sizes",
      "style"]),
    ("interpolate", ["renpy.display.motion.Interpolate"], ["start", "end"]),
    ("revolver", ["renpy.display.motion.Revolver"], ["start", "end", "child", "around", "cor", "pos"]),
    ("zoom", ["renpy.display.motion.Zoom"], ["size", "start", "end"] + _ZOOM),
    ("factor_zoom", ["renpy.display.motion.FactorZoom"], ["start", "end"] + _ZOOM),
    ("size_zoom", ["renpy.display.motion.SizeZoom"], ["start", "end"] + _ZOOM),
    ("roto_zoom", ["renpy.display.motion.RotoZoom"],
     ["rot_start", "rot_end", "rot_delay", "zoom_start", "zoom_end", "zoom_delay", "child", "rot_repeat",
      "zoom_repeat", "rot_bounce", "zoom_bounce", "rot_anim_timebase", "zoom_anim_timebase", "rot_time_warp",
      "zoom_time_warp", "opaque", "style"]),

    ("blink", ["renpy.display.anim.Blink"],
     ["image", "on", "off", "rise", "set", "high", "low", "offset", "anim_timebase", "style"]),
    ("transition_animation", ["renpy.display.anim.TransitionAnimation"],
     ["images", "delays", "transitions", "anim_timebase", "style"]),

    ("keymap", ["renpy.display.behavior.Keymap"], ["keymap", "style"]),

    ("character", ["renpy.character.ADVCharacter"],
     ["name", "who_prefix", "who_suffix", "what_prefix", "what_suffix", "show_function", "predict_function",
      "condition", "dynamic", "screen", "mode", "voice_tag", "image_tag", "display_args", "who_args", "what_args",
      "window_args", "show_args", "cb_args", "properties"]),

    ("channel", ["renpy.audio.audio.Channel"],
     ["name", "mixer", "default_loop", "default_loop_set", "stop_on_mute", "tight", "file_prefix", "file_suffix",
      "buffer_queue"]),
)


def table() -> dict:
    """The vocabulary as plain data, for the harvester and the shim:
    {"classes": {class name: kind}, "attrs": {kind: [attribute, ...]}}."""
    return {"classes": dict((cls, kind) for kind, classes, _ in KINDS for cls in classes),
            "attrs": dict((kind, attrs) for kind, _, attrs in KINDS)}
