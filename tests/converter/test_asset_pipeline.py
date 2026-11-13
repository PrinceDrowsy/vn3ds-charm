from pathlib import Path

import pytest

from converter.assets import (
    AssetConversionError,
    convert_assets,
    convert_audio,
    convert_image,
    required_asset_names,
    resolve_and_convert_assets,
    resolve_composite_images,
    resolve_ui_assets,
)
from converter.assets.pipeline import find_tool

FIXTURES = Path(__file__).resolve().parents[1] / "engine" / "fixtures" / "vnds-test"


def test_convert_image_produces_a_t3x_file(tmp_path):
    dest = tmp_path / "bg.t3x"
    convert_image(FIXTURES / "background" / "bg.jpg", dest)
    assert dest.exists()
    assert dest.stat().st_size > 0


def test_convert_audio_produces_a_valid_ogg_file(tmp_path):
    dest = tmp_path / "music.ogg"
    convert_audio(FIXTURES / "sound" / "music.mp3", dest)
    assert dest.exists()
    assert dest.read_bytes()[:4] == b"OggS"  # Ogg container magic bytes


def test_convert_assets_walks_directory_and_preserves_structure(tmp_path):
    converted = convert_assets(FIXTURES, tmp_path)
    kinds = {c.kind for c in converted}
    assert kinds == {"image", "audio"}

    assert (tmp_path / "background" / "bg.t3x").exists()
    assert (tmp_path / "foreground" / "fg.t3x").exists()
    assert (tmp_path / "sound" / "test.ogg").exists()
    assert (tmp_path / "sound" / "music.ogg").exists()
    assert (tmp_path / "sound" / "cutoff.ogg").exists()
    # icon.png at the fixture root is also a recognized image extension
    assert (tmp_path / "icon.t3x").exists()

    # script/main.scr isn't an image or audio file - not converted, not present
    assert not (tmp_path / "script").exists()


def test_downscale_if_oversized_fits_within_independent_width_and_height_bounds(tmp_path):
    # regression: real hardware showed a sprite drawn at the *correct*
    # position and (after a first fix) roughly the right scale, but still
    # cropped -- a portrait CG capped only on its longest edge (e.g.
    # 1024x1536 -> 267x400) still exceeds the 240px screen height. Both
    # edges need independent bounds to actually fit the screen.
    from PIL import Image

    from converter.assets.pipeline import _downscale_if_oversized

    source_dir = tmp_path / "source"
    work_dir = tmp_path / "work"
    source_dir.mkdir()
    work_dir.mkdir()
    source = source_dir / "sprite.png"
    Image.new("RGB", (683, 1024), color=(10, 20, 30)).save(source)

    resized_path = _downscale_if_oversized(source, work_dir, max_width=400, max_height=240)
    assert resized_path != source
    with Image.open(resized_path) as resized:
        width, height = resized.size
        assert width <= 400
        assert height <= 240

    # a file already under the cap is returned untouched
    small = source_dir / "small.png"
    Image.new("RGB", (100, 50), color=(1, 2, 3)).save(small)
    assert _downscale_if_oversized(small, work_dir, max_width=400, max_height=240) == small

    # max_height defaults to max_width (a square cap, e.g. the hardware
    # texture limit, where the two edges have no independent meaning)
    square = source_dir / "square_check.png"
    Image.new("RGB", (2000, 100), color=(1, 2, 3)).save(square)
    resized_square = _downscale_if_oversized(square, work_dir, max_width=1024)
    with Image.open(resized_square) as resized:
        assert max(resized.size) <= 1024


def test_resolve_and_convert_assets_scales_foreground_by_the_games_own_resolution_ratio(tmp_path):
    # Real hardware bug #1 (older): capping foreground art to fit *both*
    # 400x240 axes shrank every character composite to whatever width fit
    # inside a 240px-tall box, rendering noticeably smaller than the PC
    # version (VN character art is authored to overflow/crop at the
    # screen's edges, not shrink to fit inside them).
    #
    # Real hardware bug #2 (this one): the fix for #1 -- capping only
    # *width* to a flat 400, leaving height free -- assumed source art is
    # always *wider* than 400px. Real content broke that assumption
    # directly: Jisei's own character layers are a genuine 286x768 (narrower
    # than 400), so that cap never triggered at all, leaving the sprite at
    # its full 768-tall native size drawn 1:1 onto the 240-tall screen --
    # wildly oversized, every option/character unselectable-looking.
    #
    # The real fix: scale foreground art by the *same* proportion the rest
    # of the game's composition uses (background art, sprite positions) --
    # derived from the game's own declared resolution, not an independent
    # per-image "fit to a fixed pixel box" guess.
    from PIL import Image

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    Image.new("RGB", (683, 1024), color=(10, 20, 30)).save(source_dir / "sprite.png")
    Image.new("RGB", (900, 700), color=(40, 50, 60)).save(source_dir / "bg.png")

    out_dir = tmp_path / "out"
    required = {"background": {"bg"}, "foreground": {"sprite"}, "sound": set()}
    # no screen_resolution passed -> the (800, 600) default fallback applies
    converted, missing, failed = resolve_and_convert_assets(source_dir, out_dir, required)

    assert failed == []
    assert missing == set()
    assert len(converted) == 2
    assert (out_dir / "foreground" / "sprite.t3x").exists()
    assert (out_dir / "background" / "bg.t3x").exists()

    from converter.assets.pipeline import _foreground_scale_for, _scale_image_by_factor

    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir()
    scale = _foreground_scale_for((800, 600))  # min(400/800, 240/600) = 0.4
    resized = _scale_image_by_factor(source_dir / "sprite.png", scratch_dir, scale)
    with Image.open(resized) as img:
        assert img.size == (round(683 * scale), round(1024 * scale))


def test_resolve_and_convert_assets_scales_a_full_resolution_background_down_to_the_screen(tmp_path):
    # real-hardware regression: background art authored at the source
    # game's own real design resolution (confirmed real content: Jisei's
    # actual background files are a genuine 1024x768, matching its
    # declared config.screen_width/config.screen_height) used to pass
    # through capped only against the 1024px hardware texture limit --
    # never actually scaled down to fit the engine's fixed 400x240
    # reference screen -- so it drew at native pixel size on real
    # hardware, appearing hugely oversized (only ~40% of its width ever
    # visible, the rest cropped off-screen).
    from PIL import Image

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    Image.new("RGB", (1024, 768), color=(10, 20, 30)).save(source_dir / "cafe.png")

    out_dir = tmp_path / "out"
    required = {"background": {"cafe"}, "foreground": set(), "sound": set()}
    converted, missing, failed = resolve_and_convert_assets(source_dir, out_dir, required)

    assert failed == []
    assert missing == set()
    assert (out_dir / "background" / "cafe.t3x").exists()

    from converter.assets.pipeline import _BACKGROUND_MAX_HEIGHT, _BACKGROUND_MAX_WIDTH, _downscale_if_oversized

    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir()
    resized = _downscale_if_oversized(
        source_dir / "cafe.png", scratch_dir, _BACKGROUND_MAX_WIDTH, _BACKGROUND_MAX_HEIGHT
    )
    with Image.open(resized) as img:
        # 1024x768 (4:3) fit within 400x240 (5:3), aspect-preserved -> 320x240
        assert img.size == (320, 240)


def test_resolve_and_convert_assets_shrinks_a_narrow_oversized_character_sprite(tmp_path):
    # the exact real-hardware bug: a character layer narrower than the old
    # flat 400px width cap (confirmed real content -- Jisei's own character
    # layers are a genuine 286x768) never triggered any resize under the
    # old "cap width only" policy at all, leaving it at its full 768-tall
    # native size drawn 1:1 onto the 240-tall target screen. The game's
    # own declared resolution (1024x768 here, matching Jisei's real
    # options.rpy) must be used to shrink it regardless of its own width.
    from PIL import Image

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    Image.new("RGBA", (286, 768), (10, 20, 30, 255)).save(source_dir / "base01.png")

    dest_dir = tmp_path / "out"
    required = {"background": set(), "foreground": {"base01"}, "sound": set()}
    resolve_and_convert_assets(source_dir, dest_dir, required, screen_resolution=(1024, 768))

    assert (dest_dir / "foreground" / "base01.t3x").exists()

    from converter.assets.pipeline import _foreground_scale_for, _scale_image_by_factor

    scale = _foreground_scale_for((1024, 768))  # min(400/1024, 240/768) = 0.3125
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir()
    resized = _scale_image_by_factor(source_dir / "base01.png", scratch_dir, scale)
    with Image.open(resized) as img:
        # 286x768 -> 89x240: correctly shrunk to fit the 240-tall target
        # screen, unlike the old width-only cap (286 < 400, never triggered)
        assert img.size == (round(286 * scale), round(768 * scale))
        assert img.size[1] <= 240


def test_convert_image_downscales_a_texture_that_exceeds_the_pica200_limit(tmp_path):
    # regression: real Jisei CGs (e.g. a 1024x1536 opening CG) exceed the
    # 3DS GPU's 1024px max texture dimension and tex3ds rejects them
    # outright ("Invalid height") -- on real hardware this meant the
    # opening scene's background/sprite silently never appeared. A source
    # image this large would previously raise AssetConversionError; it
    # should now be downscaled to fit and convert successfully.
    from PIL import Image

    oversized = tmp_path / "oversized.jpg"
    Image.new("RGB", (1024, 1536), color=(200, 50, 50)).save(oversized)

    dest = tmp_path / "oversized.t3x"
    convert_image(oversized, dest)
    assert dest.exists()
    assert dest.stat().st_size > 0


def test_find_tool_raises_a_clear_error_when_nothing_matches():
    with pytest.raises(AssetConversionError):
        find_tool("some_tool_that_does_not_exist_anywhere_xyz")


def test_required_asset_names_scans_vnds_commands():
    vnds_text = "\n".join([
        "@start",
        "bgload eileen_happy",
        "setimg sprite1 10 20",
        "sound click.ogg 1",
        "music theme.ogg",
        "voiceover line1.ogg",
        "text hello",
    ])
    required = required_asset_names(vnds_text)
    assert required["background"] == {"eileen_happy"}
    assert required["foreground"] == {"sprite1"}
    assert required["sound"] == {"click", "theme", "line1"}


def test_resolve_and_convert_assets_sorts_by_basename_regardless_of_source_folder(tmp_path):
    # the fixture already happens to have bg/fg/sound in matching folders,
    # but resolve_and_convert_assets must not rely on that -- it matches by
    # basename alone, which is the whole point (Ren'Py's own asset layout
    # is arbitrary and doesn't match VNDS's fixed background/foreground/
    # sound convention).
    required = {
        "background": {"bg"},
        "foreground": {"fg"},
        "sound": {"test", "music"},
    }
    converted, missing, failed = resolve_and_convert_assets(FIXTURES, tmp_path, required)
    assert len(converted) == 4
    assert failed == []
    assert (tmp_path / "background" / "bg.t3x").exists()
    assert (tmp_path / "foreground" / "fg.t3x").exists()
    assert (tmp_path / "sound" / "test.ogg").exists()
    assert (tmp_path / "sound" / "music.ogg").exists()
    assert missing == set()


def test_resolve_and_convert_assets_reports_missing_names(tmp_path):
    required = {"background": {"bg", "does_not_exist"}, "foreground": set(), "sound": set()}
    converted, missing, failed = resolve_and_convert_assets(FIXTURES, tmp_path, required)
    assert len(converted) == 1
    assert missing == {"background/does_not_exist"}


def test_resolve_and_convert_assets_synthesizes_black_and_white_builtin_colors(tmp_path):
    # Ren'Py's built-in solid-color images ("black"/"white") are never
    # real files -- confirmed common, general content (119 `scene black`/
    # `show black`/`white` sites across a real game) that previously
    # always landed in missing_assets.txt with no way to resolve at all.
    required = {"background": {"black", "does_not_exist"}, "foreground": {"white"}, "sound": set()}
    converted, missing, failed = resolve_and_convert_assets(FIXTURES, tmp_path, required)
    assert missing == {"background/does_not_exist"}
    assert failed == []
    kinds = {(c.dest.parent.name, c.dest.stem) for c in converted}
    assert ("background", "black") in kinds
    assert ("foreground", "white") in kinds
    assert (tmp_path / "background" / "black.t3x").exists()
    assert (tmp_path / "foreground" / "white.t3x").exists()


def test_resolve_and_convert_assets_prefers_a_real_file_over_a_builtin_color_name(tmp_path):
    # if a game genuinely ships its own "black.png" asset (overriding the
    # built-in), the real file must win -- the synthesized fallback only
    # ever fires for names the real-file scan didn't already resolve.
    source_dir = tmp_path / "source"
    (source_dir / "background").mkdir(parents=True)
    (source_dir / "background" / "black.jpg").write_bytes((FIXTURES / "background" / "bg.jpg").read_bytes())
    out_dir = tmp_path / "out"
    required = {"background": {"black"}, "foreground": set(), "sound": set()}
    converted, missing, failed = resolve_and_convert_assets(source_dir, out_dir, required)
    assert len(converted) == 1
    assert converted[0].source.name == "black.jpg"


def test_resolve_and_convert_assets_skips_a_failing_file_without_aborting_the_batch(tmp_path):
    # a batch of real assets will always have some outliers (e.g. tex3ds
    # rejecting an oversized/non-power-of-two texture) -- one bad file
    # must not prevent every other asset from converting.
    source_dir = tmp_path / "source"
    (source_dir / "background").mkdir(parents=True)
    (source_dir / "background" / "good.jpg").write_bytes((FIXTURES / "background" / "bg.jpg").read_bytes())
    (source_dir / "background" / "broken.png").write_bytes(b"not a real image")

    out_dir = tmp_path / "out"
    required = {"background": {"good", "broken"}, "foreground": set(), "sound": set()}
    converted, missing, failed = resolve_and_convert_assets(source_dir, out_dir, required)

    assert len(converted) == 1
    assert converted[0].source.name == "good.jpg"
    assert (out_dir / "background" / "good.t3x").exists()
    assert missing == set()
    assert len(failed) == 1
    assert failed[0][0].name == "broken.png"


def test_resolve_and_convert_assets_scales_a_tall_pan_image_by_the_games_resolution_ratio(tmp_path):
    # a full-bleed pan image (e.g. Jisei's tall "death" intro art) scales by
    # the same game-resolution-derived ratio as any other foreground image.
    from PIL import Image

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    Image.new("RGB", (1280, 2000)).save(source_dir / "01.jpg")

    dest_dir = tmp_path / "out"
    required = {"background": set(), "foreground": {"01"}, "sound": set()}
    resolve_and_convert_assets(source_dir, dest_dir, required)  # no screen_resolution -> (800, 600) default

    dest = dest_dir / "foreground" / "01.t3x"
    assert dest.exists()
    # tex3ds doesn't expose the resulting pixel dimensions directly, but the
    # scaling step that decides them is `_scale_image_by_factor` -- call it
    # the same way resolve_and_convert_assets does, to confirm the ratio.
    from converter.assets.pipeline import _foreground_scale_for, _scale_image_by_factor

    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir()
    scale = _foreground_scale_for((800, 600))  # min(400/800, 240/600) = 0.4
    resized = _scale_image_by_factor(source_dir / "01.jpg", scratch_dir, scale)
    from PIL import Image as PILImage

    with PILImage.open(resized) as img:
        assert img.size == (round(1280 * scale), round(2000 * scale))


def _make_layer(path, size, color):
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, color).save(path)


def test_resolve_composite_images_stacks_layers_into_one_t3x(tmp_path):
    source_dir = tmp_path / "source"
    _make_layer(source_dir / "char/chance/base01.png", (32, 32), (255, 0, 0, 255))
    _make_layer(source_dir / "char/chance/mouth10.png", (32, 32), (0, 255, 0, 128))
    composites = {"chance a01 grin": ["char/chance/base01.png", "char/chance/mouth10.png"]}

    dest_dir = tmp_path / "out"
    converted, failed = resolve_composite_images(composites, source_dir, dest_dir, {"chance_a01_grin"})

    assert failed == []
    assert len(converted) == 1
    assert (dest_dir / "foreground" / "chance_a01_grin.t3x").exists()


def test_resolve_composite_images_skips_tags_not_actually_referenced(tmp_path):
    source_dir = tmp_path / "source"
    _make_layer(source_dir / "char/chance/base01.png", (32, 32), (255, 0, 0, 255))
    composites = {"chance a01 grin": ["char/chance/base01.png"]}

    dest_dir = tmp_path / "out"
    converted, failed = resolve_composite_images(composites, source_dir, dest_dir, set())

    assert converted == []
    assert failed == []
    assert not (dest_dir / "foreground" / "chance_a01_grin.t3x").exists()


def test_resolve_composite_images_reports_a_missing_layer_without_aborting_the_batch(tmp_path):
    source_dir = tmp_path / "source"
    _make_layer(source_dir / "char/chance/base01.png", (32, 32), (255, 0, 0, 255))
    composites = {
        "chance a01 grin": ["char/chance/base01.png", "char/chance/does_not_exist.png"],
        "chance a01 sad": ["char/chance/base01.png"],
    }

    dest_dir = tmp_path / "out"
    converted, failed = resolve_composite_images(
        composites, source_dir, dest_dir, {"chance_a01_grin", "chance_a01_sad"}
    )

    assert len(failed) == 1
    assert failed[0][0] == "chance a01 grin"
    assert len(converted) == 1
    assert (dest_dir / "foreground" / "chance_a01_sad.t3x").exists()
    assert not (dest_dir / "foreground" / "chance_a01_grin.t3x").exists()


def test_resolve_ui_assets_converts_every_referenced_chrome_image(tmp_path):
    source_dir = tmp_path / "source"
    _make_layer(source_dir / "gui/textbox.png", (64, 32), (10, 10, 10, 255))
    _make_layer(source_dir / "gui/namebox/namebox.png", (16, 16), (20, 20, 20, 255))
    _make_layer(source_dir / "gui/button/choice_idle_background.png", (16, 16), (30, 30, 30, 255))

    dest_dir = tmp_path / "out"
    resolved, converted, failed = resolve_ui_assets(
        {"gui/textbox.png", "gui/namebox/namebox.png", "gui/button/choice_idle_background.png"},
        source_dir,
        dest_dir,
    )

    assert failed == []
    assert len(converted) == 3
    assert resolved == {
        "gui/textbox.png": "textbox.t3x",
        "gui/namebox/namebox.png": "namebox.t3x",
        "gui/button/choice_idle_background.png": "choice_idle_background.t3x",
    }
    assert (dest_dir / "ui" / "textbox.t3x").exists()
    assert (dest_dir / "ui" / "namebox.t3x").exists()
    assert (dest_dir / "ui" / "choice_idle_background.t3x").exists()


def test_resolve_ui_assets_reports_a_missing_file_without_aborting_the_batch(tmp_path):
    source_dir = tmp_path / "source"
    _make_layer(source_dir / "gui/textbox.png", (64, 32), (10, 10, 10, 255))

    dest_dir = tmp_path / "out"
    resolved, converted, failed = resolve_ui_assets(
        {"gui/textbox.png", "gui/does_not_exist.png"}, source_dir, dest_dir
    )

    assert len(failed) == 1
    assert failed[0][0] == "gui/does_not_exist.png"
    assert len(converted) == 1
    assert resolved == {"gui/textbox.png": "textbox.t3x"}


def test_resolve_ui_assets_with_no_paths_converts_nothing():
    resolved, converted, failed = resolve_ui_assets(set(), Path("."), Path("."))
    assert resolved == {}
    assert converted == []
    assert failed == []
