"""Emits manifest.json: game metadata, entry label, and character table.

No formal schema exists yet in VN3DS-spec.md (confirmed absent — only prose
references to "entry label" and "character definitions (name, color)"), so
this is a minimal, deliberately small schema that later phases (asset index,
channel config) can extend without breaking this shape.
"""
from __future__ import annotations

import json

from converter.parser import CharacterDef, FrameAsset, Script


def _resolved_ui_path(path: str | None, ui_resolved: dict[str, str]) -> str | None:
    """Looks up a source-relative UI chrome path's converted bundle
    basename (assets/pipeline.py's `resolve_ui_assets` output) -- `None`
    either because the game never declared this chrome image at all, or
    because it was declared but failed to resolve/convert (missing file,
    tex3ds failure) -- both cases are the engine's existing flat-color
    fallback signal, deliberately not distinguished here."""
    if path is None:
        return None
    return ui_resolved.get(path)


def _frame_asset_dict(frame: FrameAsset | None, ui_resolved: dict[str, str]) -> dict | None:
    image = _resolved_ui_path(frame.image, ui_resolved) if frame is not None else None
    if image is None:
        return None
    return {"image": image, "borders": list(frame.borders), "tile": frame.tile}


def build_manifest(
    script: Script, *, entry_label: str | None = None, ui_resolved: dict[str, str] | None = None
) -> dict:
    if entry_label is None:
        label_names = [label.name for label in script.labels]
        entry_label = "start" if "start" in label_names else (label_names[0] if label_names else None)
    ui_resolved = ui_resolved or {}

    return {
        "entry_label": entry_label,
        "characters": {
            varname: {
                "name": cdef.display_name,
                "color": cdef.color,
                # The custom UI-asset-import system's per-character
                # nameplate skin override (VN3DS-spec.md §6) -- `None`
                # when the character has no `namebox_background=` kwarg,
                # or it didn't resolve/convert.
                "namebox": _resolved_ui_path(cdef.namebox_background, ui_resolved),
            }
            for varname, cdef in script.characters.items()
        },
        # The custom UI-asset-import system (VN3DS-spec.md §6) -- the
        # engine's first real consumer of manifest.json (confirmed nothing
        # read it before this). Always present with this exact shape (each
        # sub-key independently `None` when undeclared/unresolved) so the
        # engine never needs to guard against the whole "ui" key itself
        # being absent.
        "ui": {
            "textbox": _resolved_ui_path(script.textbox_image, ui_resolved),
            "namebox": _frame_asset_dict(script.namebox, ui_resolved),
            "choice_idle": _frame_asset_dict(script.choice_idle, ui_resolved),
            "choice_hover": _frame_asset_dict(script.choice_hover, ui_resolved),
        },
    }


def emit_manifest_json(
    script: Script, *, entry_label: str | None = None, ui_resolved: dict[str, str] | None = None
) -> str:
    manifest = build_manifest(script, entry_label=entry_label, ui_resolved=ui_resolved)
    return json.dumps(manifest, sort_keys=True, indent=2) + "\n"
