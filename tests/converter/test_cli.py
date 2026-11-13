import io
import subprocess
from pathlib import Path

from PIL import Image

from converter import cli
from converter.cli import build_bundle, main, parse_game, scan_character_images


def test_build_bundle_puts_the_start_label_first_regardless_of_file_order(tmp_path):
    # regression: emit_script_vnds writes labels in whatever order
    # parse_game merged them (alphabetical .rpy filename order) and the
    # engine always begins executing at instruction 1 -- it has no notion
    # of Ren'Py's "start" label being special. If "start" isn't textually
    # first, the game begins mid-story. Confirmed on real hardware: Jisei's
    # merged script began at a label named "chance02" because "start" lived
    # in a later file.
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a_early.rpy").write_text(
        '''
label chapter_two:
    "This should not run first."
    return
''',
        encoding="utf-8",
    )
    (game_dir / "z_late.rpy").write_text(
        '''
label start:
    "This is the real beginning."
    return
''',
        encoding="utf-8",
    )
    output_dir = tmp_path / "bundle"
    build_bundle(game_dir, output_dir, game_name="Test Game")
    script_text = (output_dir / "script" / "main.scr").read_text(encoding="utf-8")

    first_label_pos = script_text.index("@")
    assert script_text[first_label_pos:].startswith("@start")


def test_parse_game_resolves_a_transform_declared_in_a_later_sorting_file(tmp_path):
    # regression: a plain alphabetical file sort can easily parse a file
    # that *uses* a named transform before the file that *declares* it
    # (confirmed against real content: Mice Tea's `story/*.rpy` sorts
    # before its own `transforms.rpy`). parse_game must collect every
    # transform game-wide before parsing any file's statements, not just
    # whichever transforms happened to be declared earlier in file order.
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a_story.rpy").write_text(
        '''
label start:
    show eileen happy:
        bs_centerleft3
    return
''',
        encoding="utf-8",
    )
    (game_dir / "z_transforms.rpy").write_text(
        '''
transform bs_centerleft3:
    xcenter 0.55 yalign 1.0 ypos 1.3 zoom 1.1
''',
        encoding="utf-8",
    )
    script, problems = parse_game(game_dir)
    assert problems == []
    show = script.labels[0].body[0]
    assert show.xalign == 0.55
    assert show.yalign == 1.3


def test_parse_game_resolves_a_bare_audio_alias_declared_in_a_later_sorting_file(tmp_path):
    # regression: same file-ordering problem as transforms, for
    # `NAME = "literal"` audio aliases -- confirmed against real content
    # (Mice Tea declares every `sfx_X` alias inside an `init python:`
    # block in screens/music.rpy, used bare by `story/*.rpy` files that
    # sort earlier alphabetically).
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a_story.rpy").write_text(
        '''
label start:
    play sound sfx_paper
    return
''',
        encoding="utf-8",
    )
    (game_dir / "z_audio.rpy").write_text(
        '''
init -1 python:
    sfx_paper = "audio/sfx/magazine1.mp3"
''',
        encoding="utf-8",
    )
    script, problems = parse_game(game_dir)
    # the init python block itself is still (correctly) flagged as
    # unsupported -- only the string literal *inside* it is harvested for
    # bare-identifier resolution elsewhere, same as any other init python
    # block's arbitrary Python content.
    assert len(problems) == 1
    assert problems[0].reason == "init python block has no VNDS equivalent (needs native reimplementation, if needed at all)"
    play = script.labels[0].body[0]
    assert play.file == "audio/sfx/magazine1.mp3"


def _write_game(tmp_path: Path) -> Path:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a.rpy").write_text(
        '''
define e = Character("Eileen", color="#c8ffc8")

label start:
    e "Hi from file A."
    call helper
    e "Back in A."
    return
''',
        encoding="utf-8",
    )
    (game_dir / "b.rpy").write_text(
        '''
label helper:
    "This label lives in file B."
    return
''',
        encoding="utf-8",
    )
    return game_dir


def test_parse_game_merges_labels_characters_across_files(tmp_path):
    game_dir = _write_game(tmp_path)
    script, problems = parse_game(game_dir)
    assert problems == []
    assert {label.name for label in script.labels} == {"start", "helper"}
    assert script.characters["e"].display_name == "Eileen"


def test_parse_game_resolves_namebox_borders_declared_in_a_different_file_than_the_frame_call(tmp_path):
    # regression: confirmed real content -- Mice Tea declares
    # `gui.namebox_borders`/`gui.namebox_tile` in gui.rpy but makes the
    # `Frame("gui/namebox/...", ...)` call using them in screens.rpy, a
    # *different* file. A naive per-file-only scan silently defaulted
    # borders to (0,0,0,0)/tile=False whenever the two pieces didn't
    # happen to share a file -- this must resolve across files, the same
    # way transforms/string_defines already do.
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a_gui.rpy").write_text(
        '''
init python:
    define gui.namebox_borders = Borders(5, 5, 5, 5)
    define gui.namebox_tile = True
''',
        encoding="utf-8",
    )
    (game_dir / "b_screens.rpy").write_text(
        '''
screen say(who, what):
    window:
        background Frame("gui/namebox/namebox.png", gui.namebox_borders, tile=gui.namebox_tile)
''',
        encoding="utf-8",
    )
    script, _problems = parse_game(game_dir)
    assert script.namebox.image == "gui/namebox/namebox.png"
    assert script.namebox.borders == (5, 5, 5, 5)
    assert script.namebox.tile is True


def test_build_bundle_writes_a_single_merged_script_and_resolves_cross_file_jumps(tmp_path):
    game_dir = _write_game(tmp_path)
    output_dir = tmp_path / "bundle"
    report = build_bundle(game_dir, output_dir, game_name="Test Game")

    assert report["summary"]["total"] == 0

    script_text = (output_dir / "script" / "main.scr").read_text(encoding="utf-8")
    assert "@start" in script_text
    assert "@helper" in script_text
    assert "call helper" in script_text  # cross-file call, resolved into one script

    manifest_text = (output_dir / "manifest.json").read_text(encoding="utf-8")
    assert '"entry_label": "start"' in manifest_text
    assert '"Eileen"' in manifest_text

    assert (output_dir / "problems.json").exists()
    assert (output_dir / "problems.md").exists()


def test_build_bundle_reports_blocking_items_from_merged_content(tmp_path):
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a.rpy").write_text(
        '''
label start:
    $ some_func()
    "Hi."
    return
''',
        encoding="utf-8",
    )
    report = build_bundle(game_dir, tmp_path / "bundle", game_name="Test Game")
    assert report["summary"]["blocking"] == 1


def test_build_bundle_emits_image_paths_matching_the_converted_asset_extension(tmp_path):
    # regression: emit_script_vnds used to emit bgload/setimg/clearimg with
    # no file extension at all (based on a mistaken belief that VNDS takes
    # a bare filename), but script.moon's parse() builds the lookup path
    # verbatim with no extension appended, and the asset pipeline always
    # produces ".t3x" files -- so on real hardware, no background or
    # sprite ever rendered, because the path the engine looked for never
    # matched the file that existed on disk. sound/music/voiceover already
    # appended ".ogg" correctly, which is why audio worked while images
    # never did. Every hand-written engine fixture
    # (tests/engine/fixtures/{hello-vn,stress-test,vnds-test}) confirms the
    # real convention includes the extension.
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a.rpy").write_text(
        '''
label start:
    scene bg
    show eileen happy
    hide eileen happy
    return
''',
        encoding="utf-8",
    )
    output_dir = tmp_path / "bundle"
    build_bundle(game_dir, output_dir, game_name="Test Game")
    script_text = (output_dir / "script" / "main.scr").read_text(encoding="utf-8")
    assert "bgload bg.t3x" in script_text
    assert "setimg eileen_happy.t3x" in script_text
    assert "clearslot eileen" in script_text


def test_build_bundle_resolves_composite_character_sprites(tmp_path):
    # regression: `show chance a01 grin` where `chance a01 grin` is declared
    # as `im.Composite(None, (0,0), "base.png", (0,0), "mouth.png")` (Jisei's
    # real base/eyebrows/mouth/eyes swappable-face pattern) used to resolve
    # to a guessed filename ("chance_a01_grin.t3x") that the asset pipeline
    # never produced, since composite tags were deliberately excluded from
    # `images` as unresolvable -- vnds_writer's fallback filename guess
    # doesn't know the difference between "an anonymous tag that happens to
    # match a real file" and "a dynamic displayable that was never going to
    # exist on disk". On real hardware this meant composite-based character
    # sprites silently never appeared (main.moon's path_exists check just
    # skips a setimg whose file is missing). Now the layers get
    # alpha-composited into one real image at convert time instead.
    from PIL import Image

    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a.rpy").write_text(
        '''
image chance a01 grin = im.Composite(None, (0,0), "char/chance/base01.png", (0,0), "char/chance/mouth10.png")

label start:
    show chance a01 grin
    return
''',
        encoding="utf-8",
    )
    assets_dir = tmp_path / "assets"
    (assets_dir / "char" / "chance").mkdir(parents=True)
    Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(assets_dir / "char/chance/base01.png")
    Image.new("RGBA", (32, 32), (0, 255, 0, 128)).save(assets_dir / "char/chance/mouth10.png")

    output_dir = tmp_path / "bundle"
    build_bundle(game_dir, output_dir, game_name="Test Game", assets_dir=assets_dir)

    script_text = (output_dir / "script" / "main.scr").read_text(encoding="utf-8")
    assert "setimg chance_a01_grin.t3x" in script_text
    assert (output_dir / "foreground" / "chance_a01_grin.t3x").exists()
    assert not (output_dir / "missing_assets.txt").exists()


def test_build_bundle_copies_the_games_own_default_font_into_the_bundle(tmp_path):
    # text.moon's update_font already looks for a "default.ttf" at the
    # bundle's own root and uses it in place of LÖVE's generic built-in
    # font -- previously dead code, since nothing had ever produced one.
    # The font file itself lives alongside the .rpy source (e.g.
    # game/gui/HanSrf.ttf), not inside the extracted asset archive, so
    # it's resolved against game_dir directly.
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a.rpy").write_text(
        '''
init -1 python hide:
    style.default.font = "gui/HanSrf.ttf"

label start:
    "Hi."
    return
''',
        encoding="utf-8",
    )
    (game_dir / "gui").mkdir()
    (game_dir / "gui" / "HanSrf.ttf").write_bytes(b"fake font bytes")

    output_dir = tmp_path / "bundle"
    build_bundle(game_dir, output_dir, game_name="Test Game")

    copied = output_dir / "default.ttf"
    assert copied.exists()
    assert copied.read_bytes() == b"fake font bytes"


def test_build_bundle_compiles_a_bcfnt_alongside_default_ttf_when_mkbcfnt_is_installed(tmp_path, monkeypatch):
    # real-hardware regression: LOVE Potion's 3DS font backend crashed
    # looking for "default.bcfnt" when only "default.ttf" existed (real
    # hardware error: "text/text.lua:37: Could not open file
    # novels/jisei/default.bcfnt. Does not exist.") -- love.graphics.newFont
    # on 3DS silently looks for a precompiled BCFNT next to whatever path
    # it's given, regardless of the requested extension. Mocks the actual
    # devkitPro mkbcfnt binary (a fake stand-in file is enough -- only its
    # existence and the subprocess invocation are under test here) rather
    # than requiring the real toolchain to be installed to run this test.
    fake_mkbcfnt = tmp_path / "mkbcfnt.exe"
    fake_mkbcfnt.write_bytes(b"")
    monkeypatch.setattr(cli, "_MKBCFNT", fake_mkbcfnt)
    calls = []
    monkeypatch.setattr(
        subprocess, "run",
        lambda command, **kwargs: calls.append((command, kwargs)),
    )

    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a.rpy").write_text(
        '''
init -1 python hide:
    style.default.font = "gui/HanSrf.ttf"

label start:
    "Hi."
    return
''',
        encoding="utf-8",
    )
    (game_dir / "gui").mkdir()
    (game_dir / "gui" / "HanSrf.ttf").write_bytes(b"fake font bytes")

    output_dir = tmp_path / "bundle"
    build_bundle(game_dir, output_dir, game_name="Test Game")

    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[0] == str(fake_mkbcfnt)
    assert command[1] == str(output_dir / "default.ttf")
    assert "-o" in command and command[command.index("-o") + 1] == str(output_dir / "default.bcfnt")
    assert "-s" in command and command[command.index("-s") + 1] == "20"
    assert kwargs["check"] is False


def test_build_bundle_skips_bcfnt_compilation_when_mkbcfnt_is_not_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_MKBCFNT", tmp_path / "does-not-exist" / "mkbcfnt.exe")
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append((a, k)))

    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a.rpy").write_text(
        '''
init -1 python hide:
    style.default.font = "gui/HanSrf.ttf"

label start:
    "Hi."
    return
''',
        encoding="utf-8",
    )
    (game_dir / "gui").mkdir()
    (game_dir / "gui" / "HanSrf.ttf").write_bytes(b"fake font bytes")

    output_dir = tmp_path / "bundle"
    build_bundle(game_dir, output_dir, game_name="Test Game")

    assert not calls
    assert not (output_dir / "default.bcfnt").exists()


def test_build_bundle_writes_text_cps_txt_when_the_game_declares_one(tmp_path):
    # text.moon's update_typewriter_speed checks for exactly this filename
    # at the bundle root, the same manifest.json-free convention
    # default.ttf uses (the engine doesn't read manifest.json at all).
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a.rpy").write_text(
        '''
init python:
    config.default_text_cps = 35

label start:
    "Hi."
    return
''',
        encoding="utf-8",
    )
    output_dir = tmp_path / "bundle"
    build_bundle(game_dir, output_dir, game_name="Test Game")
    assert (output_dir / "text_cps.txt").read_text(encoding="utf-8") == "35.0"


def test_build_bundle_omits_text_cps_txt_when_the_game_never_declares_one(tmp_path):
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a.rpy").write_text('label start:\n    "Hi."\n    return\n', encoding="utf-8")
    output_dir = tmp_path / "bundle"
    build_bundle(game_dir, output_dir, game_name="Test Game")
    assert not (output_dir / "text_cps.txt").exists()


def test_build_bundle_falls_back_to_assets_dir_for_a_font_not_next_to_the_rpy_source(tmp_path):
    # Mice Tea's real gui.rpy declares `define gui.default_font =
    # "VarelaRound.ttf"`, but the actual .ttf only exists inside the
    # extracted RPA asset archive (fonts.rpa) -- never as a loose file next
    # to the .rpy source the way Jisei's HanSrf.ttf is. assets_dir must be
    # tried as a fallback so real games that RPA-pack their fonts still get
    # their font copied into the bundle.
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a.rpy").write_text(
        '''
define gui.default_font = "VarelaRound.ttf"

label start:
    "Hi."
    return
''',
        encoding="utf-8",
    )
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "VarelaRound.ttf").write_bytes(b"fake rpa-packed font bytes")

    output_dir = tmp_path / "bundle"
    build_bundle(game_dir, output_dir, game_name="Test Game", assets_dir=assets_dir)

    copied = output_dir / "default.ttf"
    assert copied.exists()
    assert copied.read_bytes() == b"fake rpa-packed font bytes"


def test_build_bundle_converts_ui_chrome_and_writes_manifest_ui_section(tmp_path):
    # The custom UI-asset-import system (VN3DS-spec.md §6): textbox,
    # namebox (with real tiling), choice buttons, and a per-character
    # namebox override should all convert into a new "ui/" folder, with
    # manifest.json's "ui" section (and each character's "namebox" key)
    # pointing at the resolved bundle basenames.
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a.rpy").write_text(
        '''
init python:
    define gui.namebox_borders = Borders(5, 5, 5, 5)
    define gui.namebox_tile = True
    define gui.choice_button_borders = Borders(150, 22, 150, 8)
    define gui.choice_button_tile = False
    style.window.background = "gui/textbox.png"

define margaret = Character("Margaret", namebox_background="gui/namebox/nameboxM.png")

screen say(who, what):
    window:
        background Frame("gui/namebox/namebox.png", gui.namebox_borders, tile=gui.namebox_tile)

label start:
    margaret "Hi."
    return
''',
        encoding="utf-8",
    )
    assets_dir = tmp_path / "assets"
    for rel in (
        "gui/textbox.png",
        "gui/namebox/namebox.png",
        "gui/namebox/nameboxM.png",
        "gui/button/choice_idle_background.png",
        "gui/button/choice_hover_background.png",
    ):
        path = assets_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (16, 16), (10, 20, 30, 255)).save(path)

    output_dir = tmp_path / "bundle"
    build_bundle(game_dir, output_dir, game_name="Test Game", assets_dir=assets_dir)

    assert (output_dir / "ui" / "textbox.t3x").exists()
    assert (output_dir / "ui" / "namebox.t3x").exists()
    assert (output_dir / "ui" / "nameboxM.t3x").exists()
    assert (output_dir / "ui" / "choice_idle_background.t3x").exists()
    assert (output_dir / "ui" / "choice_hover_background.t3x").exists()

    import json

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["ui"]["textbox"] == "textbox.t3x"
    assert manifest["ui"]["namebox"] == {"image": "namebox.t3x", "borders": [5, 5, 5, 5], "tile": True}
    assert manifest["ui"]["choice_idle"]["image"] == "choice_idle_background.t3x"
    assert manifest["ui"]["choice_hover"]["image"] == "choice_hover_background.t3x"
    assert manifest["characters"]["margaret"]["namebox"] == "nameboxM.t3x"


def test_build_bundle_omits_ui_manifest_entries_when_the_game_declares_none(tmp_path):
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a.rpy").write_text('label start:\n    "Hi."\n    return\n', encoding="utf-8")
    output_dir = tmp_path / "bundle"
    build_bundle(game_dir, output_dir, game_name="Test Game")

    import json

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["ui"] == {"textbox": None, "namebox": None, "choice_idle": None, "choice_hover": None}
    assert not (output_dir / "ui").exists()


def test_build_bundle_skips_font_copy_when_declared_font_file_is_missing(tmp_path):
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a.rpy").write_text(
        '''
init -1 python hide:
    style.default.font = "gui/DoesNotExist.ttf"

label start:
    "Hi."
    return
''',
        encoding="utf-8",
    )
    output_dir = tmp_path / "bundle"
    build_bundle(game_dir, output_dir, game_name="Test Game")
    assert not (output_dir / "default.ttf").exists()


def test_build_bundle_clears_stale_missing_and_failed_asset_reports(tmp_path):
    # regression: rebuilding into the same output_dir after fixing an asset
    # (e.g. Pillow's downscale-oversized-textures fix) left the previous
    # run's missing_assets.txt/failed_assets.txt sitting there unchanged,
    # since build_bundle only ever wrote those files, never cleared them --
    # making a fixed build look like it still had the old failures.
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a.rpy").write_text(
        '''
label start:
    "Hi."
    return
''',
        encoding="utf-8",
    )
    output_dir = tmp_path / "bundle"
    output_dir.mkdir()
    (output_dir / "missing_assets.txt").write_text("stale/entry\n", encoding="utf-8")
    (output_dir / "failed_assets.txt").write_text("stale: error\n", encoding="utf-8")

    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    build_bundle(game_dir, output_dir, game_name="Test Game", assets_dir=assets_dir)

    assert not (output_dir / "missing_assets.txt").exists()
    assert not (output_dir / "failed_assets.txt").exists()


def test_build_bundle_end_to_end_renders_a_character_image_show_as_real_layers(tmp_path):
    # The whole Tier 5 point: a `show <CharacterImage tag> <attrs>` must
    # become real, converted per-layer .t3x textures driven by a genuine
    # runtime clearslot+multi-setimg sequence -- not garbage (previously
    # the tag+attrs string itself got treated as a literal, nonsense
    # filename, since CharacterImage tags were never in the plain `images`
    # dict `_resolve_image_path` looks up).
    game_dir = tmp_path / "game"
    (game_dir / "characters").mkdir(parents=True)
    (game_dir / "characters" / "afd_l.rpy").write_text(
        '''
init python:
    def afd_layer_selector(ci, attr):
        yield "Base"
        if "eyes_happy" in attr:
            yield "eyes happy"
        else:
            yield "eyes neutral"

image afd_l = CharacterImage(
    character_name="afd",
    size=(750, 1300),
    layers=("Base*", "eyes *"),
    attribute_sets=({"eyes_happy", "eyes_neutral"},),
    aliases={},
    layer_selector=afd_layer_selector,
)

label start:
    show afd_l eyes_happy
    "Hi."
    return
''',
        encoding="utf-8",
    )

    assets_dir = tmp_path / "assets"
    char_dir = assets_dir / "characters" / "afd"
    char_dir.mkdir(parents=True)
    Image.new("RGB", (750, 1300), color=(10, 20, 30)).save(char_dir / "Base.png")
    Image.new("RGB", (200, 100), color=(40, 50, 60)).save(char_dir / "eyes happy.png")
    Image.new("RGB", (200, 100), color=(70, 80, 90)).save(char_dir / "eyes neutral.png")

    output_dir = tmp_path / "bundle"
    report = build_bundle(game_dir, output_dir, game_name="Test Game", assets_dir=assets_dir)

    script_text = (output_dir / "script" / "main.scr").read_text(encoding="utf-8")
    lines = [l for l in script_text.splitlines() if l.startswith(("clearslot", "setimg"))]
    assert lines == [
        "clearslot afd_l",
        "setimg Base.t3x 200 40 afd_l:0",
        "setimg eyes_happy.t3x 200 40 afd_l:1",
    ]
    # only the layer actually resolved for this one usage (eyes_happy) gets
    # converted -- "eyes neutral.png" is never referenced by any real show
    # in this script, so it correctly stays unconverted.
    assert (output_dir / "foreground" / "Base.t3x").is_file()
    assert (output_dir / "foreground" / "eyes_happy.t3x").is_file()
    assert not (output_dir / "foreground" / "eyes_neutral.t3x").exists()
    assert not (output_dir / "missing_assets.txt").exists()
    assert not (output_dir / "failed_assets.txt").exists()
    assert report["summary"]["blocking"] == 0


def test_scan_character_images_resolves_cross_file_constant(tmp_path):
    game_dir = tmp_path / "game"
    (game_dir / "characters").mkdir(parents=True)
    (game_dir / "characters" / "margaret.rpy").write_text(
        '''
init python:
    SPECIAL_POSES = {"pose_x", "pose_y"}
''',
        encoding="utf-8",
    )
    (game_dir / "characters" / "felicia.rpy").write_text(
        '''
init python:
    def felicia_layer_selector(ci, attr):
        yield "Base"

image felicia = CharacterImage(
    character_name="felicia",
    size=(510, 1234),
    layers=("Base*",),
    attribute_sets=(SPECIAL_POSES.union({"extra"}),),
    aliases={},
    layer_selector=felicia_layer_selector,
)
''',
        encoding="utf-8",
    )
    character_images = scan_character_images(game_dir)
    assert "felicia" in character_images
    assert character_images["felicia"].attribute_sets == (frozenset({"pose_x", "pose_y", "extra"}),)


def test_main_does_not_crash_printing_non_latin1_content_on_a_cp1252_console(tmp_path, monkeypatch):
    # regression: found converting A Date with Death (real Japanese
    # dialogue quoted in the Problem Report) on a real Windows console --
    # main()'s only stdout write (print(format_report_table(report)))
    # relied on the console's default codepage (cp1252 on Windows), which
    # can't encode arbitrary source content, crashing with
    # UnicodeEncodeError instead of printing the report.
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "a.rpy").write_text(
        'label start:\n    $ unsupported_thing("こんにちは")\n',
        encoding="utf-8",
    )
    # Simulate a real Windows console's default non-UTF-8 stdout encoding
    # -- reproduces the exact crash this test guards against if main()'s
    # sys.stdout.reconfigure(encoding="utf-8") call is ever removed.
    cp1252_stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr("sys.stdout", cp1252_stdout)

    exit_code = main([str(game_dir), str(tmp_path / "bundle"), "--name", "Test Game"])

    assert exit_code == 1  # unsupported_thing() is a real blocking item
    cp1252_stdout.flush()
    printed = cp1252_stdout.buffer.getvalue().decode("utf-8")
    assert "こんにちは" in printed
