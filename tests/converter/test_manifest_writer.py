import json

from converter.parser import CharacterDef, FrameAsset, Label, Script, SourceLocation
from converter.emitters import build_manifest, emit_manifest_json

LOC = SourceLocation("test.rpy", 1)


def test_entry_label_defaults_to_start_when_present():
    script = Script(labels=[Label(name="intro", body=[], loc=LOC), Label(name="start", body=[], loc=LOC)])
    manifest = build_manifest(script)
    assert manifest["entry_label"] == "start"


def test_entry_label_falls_back_to_first_label_when_no_start():
    script = Script(labels=[Label(name="intro", body=[], loc=LOC), Label(name="chapter1", body=[], loc=LOC)])
    manifest = build_manifest(script)
    assert manifest["entry_label"] == "intro"


def test_entry_label_none_when_no_labels():
    manifest = build_manifest(Script())
    assert manifest["entry_label"] is None


def test_characters_included_by_variable_name():
    script = Script(
        characters={"e": CharacterDef(varname="e", display_name="Eileen", color="#c8ffc8", loc=LOC)},
        labels=[Label(name="start", body=[], loc=LOC)],
    )
    manifest = build_manifest(script)
    assert manifest["characters"] == {"e": {"name": "Eileen", "color": "#c8ffc8", "namebox": None}}


def test_character_namebox_background_resolves_via_ui_resolved_map():
    script = Script(
        characters={
            "e": CharacterDef(
                varname="e", display_name="Eileen", color=None, loc=LOC,
                namebox_background="gui/namebox/nameboxE.png",
            )
        },
        labels=[Label(name="start", body=[], loc=LOC)],
    )
    manifest = build_manifest(script, ui_resolved={"gui/namebox/nameboxE.png": "nameboxE.t3x"})
    assert manifest["characters"]["e"]["namebox"] == "nameboxE.t3x"


def test_character_namebox_background_is_none_when_unresolved():
    script = Script(
        characters={
            "e": CharacterDef(
                varname="e", display_name="Eileen", color=None, loc=LOC,
                namebox_background="gui/namebox/nameboxE.png",
            )
        },
        labels=[Label(name="start", body=[], loc=LOC)],
    )
    manifest = build_manifest(script, ui_resolved={})
    assert manifest["characters"]["e"]["namebox"] is None


def test_ui_key_present_with_all_null_when_nothing_declared():
    manifest = build_manifest(Script())
    assert manifest["ui"] == {"textbox": None, "namebox": None, "choice_idle": None, "choice_hover": None}


def test_ui_key_resolves_textbox_and_frame_assets():
    script = Script(
        textbox_image="gui/textbox.png",
        namebox=FrameAsset(image="gui/namebox.png", borders=(5, 5, 5, 5), tile=True),
        choice_idle=FrameAsset(image="gui/button/choice_idle_background.png", borders=(150, 22, 150, 8), tile=False),
        choice_hover=FrameAsset(image="gui/button/choice_hover_background.png", borders=(150, 22, 150, 8), tile=False),
    )
    ui_resolved = {
        "gui/textbox.png": "textbox.t3x",
        "gui/namebox.png": "namebox.t3x",
        "gui/button/choice_idle_background.png": "choice_idle_background.t3x",
        "gui/button/choice_hover_background.png": "choice_hover_background.t3x",
    }
    manifest = build_manifest(script, ui_resolved=ui_resolved)
    assert manifest["ui"] == {
        "textbox": "textbox.t3x",
        "namebox": {"image": "namebox.t3x", "borders": [5, 5, 5, 5], "tile": True},
        "choice_idle": {"image": "choice_idle_background.t3x", "borders": [150, 22, 150, 8], "tile": False},
        "choice_hover": {"image": "choice_hover_background.t3x", "borders": [150, 22, 150, 8], "tile": False},
    }


def test_ui_frame_asset_is_none_when_its_image_failed_to_resolve():
    script = Script(namebox=FrameAsset(image="gui/namebox.png", borders=(5, 5, 5, 5), tile=True))
    manifest = build_manifest(script, ui_resolved={})
    assert manifest["ui"]["namebox"] is None


def test_emit_manifest_json_is_sorted_and_valid_json():
    script = Script(
        characters={"e": CharacterDef(varname="e", display_name="Eileen", color=None, loc=LOC)},
        labels=[Label(name="start", body=[], loc=LOC)],
    )
    text = emit_manifest_json(script)
    parsed = json.loads(text)
    assert parsed["entry_label"] == "start"
    # sort_keys=True -> "characters" before "entry_label" alphabetically
    assert text.index('"characters"') < text.index('"entry_label"')
