"""End-to-end converter CLI: Ren'Py game folder -> a bundle the engine can
actually load.

Ties together pieces that only ever ran in isolation before (parser,
emitter, problem report, asset pipeline) into the one thing a real
hardware/emulator playthrough needs: a single merged script covering every
label in the game (Ren'Py has one flat label namespace across all `.rpy`
files — `jump`/`call` can target a label defined in any file), plus
converted assets sorted into the fixed background/foreground/sound
folders the engine's `script.moon`/`images.moon`/`audio.moon` expect.

Deliberately follows the *actually-implemented* engine loading convention
(`base_dir/script/main.scr`) rather than VN3DS-spec.md §5.2's aspirational
`script.vnds`-at-bundle-root layout — `main.moon`'s `love.load` always
loads `script/main.scr` via `script.load`'s own default, and nothing
consumes `manifest.json`'s `entry_label` yet. See GAME-PLAN.md's 1.10 notes.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from .assets import (
    required_asset_names,
    resolve_and_convert_assets,
    resolve_character_image_layers,
    resolve_composite_images,
    resolve_ui_assets,
)
from .emitters import emit_manifest_json, emit_script_vnds
from .parser import (
    CharacterImageDef,
    PortraitDef,
    Script,
    SpriteLayerCategories,
    merge_sprite_layer_categories,
    parse_character_image_declarations,
    parse_portrait_declarations,
    parse_rpy,
    scan_character_image_constants,
    scan_namebox_borders_tile,
    scan_screen_resolution,
    scan_sprite_layer_categories,
    scan_string_defines,
    scan_transform_declarations,
)
from .problem_report import build_problem_report, emit_problems_json, format_report_table, has_blocking


def parse_game(game_dir: Path) -> tuple[Script, list]:
    """Parses every `.rpy` file under game_dir and merges them into one
    Script — Ren'Py's label/character/image namespaces are global across
    files, so a real playable build needs them combined, not one
    script.vnds per source file (which is all any prior triage run did)."""
    rpy_files = sorted(game_dir.rglob("*.rpy"))
    sources = [(rpy_file, rpy_file.read_text(encoding="utf-8")) for rpy_file in rpy_files]

    # Ren'Py's `transform NAME:` namespace is flat across every file in the
    # game, same as labels/images/characters -- but unlike those (which are
    # only ever *resolved* at emission time, after every file is merged), a
    # transform is expanded into a show/scene's ATL lines during this very
    # per-file parse loop. A plain alphabetical file sort can easily parse a
    # file that *uses* a transform before the file that *declares* it
    # (confirmed against real content: Mice Tea's `story/*.rpy` sorts before
    # its own `transforms.rpy`) -- so every transform must be known before
    # any file's statements are parsed, via this separate, cheap prepass.
    all_transforms: dict[str, list[str]] = {}
    for _rpy_file, source in sources:
        all_transforms.update(scan_transform_declarations(source))

    # Same reasoning as above, for `NAME = "literal"` bindings (e.g. Mice
    # Tea's `screens/music.rpy` declaring every `sfx_X = "audio/..."` alias
    # bare `play`/`queue`/`stop` statements refer to game-wide) -- see
    # scan_string_defines's own docstring.
    all_string_defines: dict[str, str] = {}
    for _rpy_file, source in sources:
        all_string_defines.update(scan_string_defines(source))

    # Same reasoning again for the custom UI-asset-import system's
    # `gui.namebox_borders`/`gui.namebox_tile` pair (VN3DS-spec.md §6) --
    # confirmed real content: Mice Tea declares these in gui.rpy but makes
    # the `Frame("gui/namebox/...", ...)` call using them in screens.rpy,
    # a *different* file -- first-found wins, same as the others.
    namebox_borders_tile = None
    for _rpy_file, source in sources:
        namebox_borders_tile = namebox_borders_tile or scan_namebox_borders_tile(source)

    # Same reasoning again for Ren'Py's declared design/authoring
    # resolution (`config.screen_width`/`config.screen_height`, or the
    # modern-project-template `gui.init(w, h)` form) -- needed to
    # correctly rescale an *absolute-pixel* ATL position value (see
    # scan_screen_resolution's own docstring); almost always declared once
    # in options.rpy/gui.rpy, but merged the same defensive way regardless.
    screen_resolution = None
    for _rpy_file, source in sources:
        screen_resolution = screen_resolution or scan_screen_resolution(source)

    # Same reasoning again for Our Life-style ChangePortrait systems'
    # characterSpritePartsOrder/characterSpriteExpressions/characterSprite
    # Glowing/characterSpriteMagic constants (character_sprite.py) -- these
    # are almost always declared once, game-wide, in their own file
    # (confirmed real content: character_definitions.rpy), but merged the
    # same defensive way regardless.
    all_sprite_categories = SpriteLayerCategories()
    for _rpy_file, source in sources:
        all_sprite_categories = merge_sprite_layer_categories(all_sprite_categories, scan_sprite_layer_categories(source))

    combined = Script()
    all_problems: list = []
    for rpy_file, source in sources:
        rel = rpy_file.relative_to(game_dir)
        script, problems = parse_rpy(
            source,
            filename=str(rel),
            transforms=all_transforms,
            string_defines=all_string_defines,
            namebox_borders_tile=namebox_borders_tile,
            sprite_categories=all_sprite_categories,
            screen_resolution=screen_resolution,
        )
        combined.labels.extend(script.labels)
        combined.characters.update(script.characters)
        combined.images.update(script.images)
        combined.composites.update(script.composites)
        combined.top_level_sets.extend(script.top_level_sets)
        combined.screens.extend(script.screens)
        combined.default_font = combined.default_font or script.default_font
        combined.default_text_cps = combined.default_text_cps or script.default_text_cps
        combined.textbox_image = combined.textbox_image or script.textbox_image
        combined.namebox = combined.namebox or script.namebox
        combined.choice_idle = combined.choice_idle or script.choice_idle
        combined.choice_hover = combined.choice_hover or script.choice_hover
        combined.screen_resolution = combined.screen_resolution or script.screen_resolution
        all_problems.extend(problems)
    return combined, all_problems


def scan_character_images(game_dir: Path) -> dict[str, CharacterImageDef]:
    """Finds every `image TAG = CharacterImage(...)` declaration across the
    whole game -- a separate pass from `parse_game` (character_image.py
    works directly off raw source text via its own tokenizer call, not the
    Node/Script IR `parse_rpy` builds) so it can stay independent of the
    ordinary parser's per-statement flow. A module-level list/set constant
    (e.g. `SPECIAL_POSES`) referenced by one character's `attribute_sets`/
    `layer_selector` occasionally lives in a *different* character's file
    (confirmed real content: felicia.rpy's attribute_sets references
    margaret.rpy's `SPECIAL_POSES`) -- Ren'Py's own namespace for these is
    flat across files, same as transforms/string defines, so constants are
    collected game-wide before any file's declarations are parsed, exactly
    mirroring `parse_game`'s own transform/string-define prepass."""
    rpy_files = sorted(game_dir.rglob("*.rpy"))
    sources = [(rpy_file, rpy_file.read_text(encoding="utf-8")) for rpy_file in rpy_files]

    all_lists: dict[str, frozenset[str]] = {}
    for _rpy_file, source in sources:
        all_lists.update(scan_character_image_constants(source))

    character_images: dict[str, CharacterImageDef] = {}
    for rpy_file, source in sources:
        rel = rpy_file.relative_to(game_dir)
        character_images.update(parse_character_image_declarations(source, str(rel), global_lists=all_lists))
    return character_images


def scan_portrait_defs(game_dir: Path) -> dict[str, PortraitDef]:
    """Finds every `image TAG = Portrait(...)` declaration across the whole
    game (character_sprite.py) -- keyed by `name` (what `$ ChangePortrait(
    chara, ...)` calls actually reference), mirroring `scan_character_images`'s
    own separate, source-text-based pass."""
    rpy_files = sorted(game_dir.rglob("*.rpy"))
    portrait_defs: dict[str, PortraitDef] = {}
    for rpy_file in rpy_files:
        source = rpy_file.read_text(encoding="utf-8")
        rel = rpy_file.relative_to(game_dir)
        portrait_defs.update(parse_portrait_declarations(source, str(rel)))
    return portrait_defs


def _reorder_entry_label(labels: list) -> list:
    """VNDS executes top-to-bottom from the first `@label` in the emitted
    file — it has no notion of Ren'Py's `label start` being special. Since
    `parse_game` concatenates labels in `.rpy` filename order, whichever
    label happens to be textually first in the alphabetically-first file
    becomes the de facto entry point, which is essentially random relative
    to the actual story (confirmed on real hardware: Jisei's merged output
    started at `@chance02`, mid-story, because `start` lived a thousand
    lines later in a different file). Move `start` to the front if present,
    matching `manifest_writer.build_manifest`'s existing entry-label pick."""
    for i, label in enumerate(labels):
        if label.name == "start":
            return [labels[i]] + labels[:i] + labels[i + 1:]
    return labels


_MKBCFNT = Path("C:/devkitPro/tools/bin/mkbcfnt.exe")


def _compile_bcfnt(ttf_path: Path, bcfnt_path: Path) -> None:
    """Best-effort: confirmed via a real hardware crash that LÖVE Potion's
    3DS font backend needs a precompiled BCFNT bitmap font, not a raw TTF --
    `love.graphics.newFont` on real hardware silently looks for
    "<name>.bcfnt" next to whatever path it's given, regardless of the
    extension actually requested. text.moon's `update_font` always asks for
    size 20 on real 3DS hardware (the text box always renders on the bottom
    screen, which is 320px wide -- always under its own <600 threshold), so
    that's the one size worth baking in. Silently skipped if devkitPro's
    mkbcfnt isn't installed -- this is a hardware-packaging nicety on top of
    the plain-TTF copy above, not a requirement for the converter to run on
    every dev machine.
    """
    if not _MKBCFNT.is_file():
        return
    subprocess.run(
        [str(_MKBCFNT), str(ttf_path), "-o", str(bcfnt_path), "-s", "20"],
        check=False,
        capture_output=True,
    )


def build_bundle(
    game_dir: Path,
    output_dir: Path,
    *,
    game_name: str,
    assets_dir: Path | None = None,
    converter_version: str = "0.1.0",
) -> dict:
    """Parses+merges game_dir's .rpy files, emits script/main.scr +
    manifest.json + problems.json + problems.md into output_dir, and (if
    assets_dir is given) converts+sorts referenced assets into
    output_dir's background/foreground/sound folders. Returns the Problem
    Report dict."""
    output_dir.mkdir(parents=True, exist_ok=True)
    script, problems = parse_game(game_dir)
    character_images = scan_character_images(game_dir)
    character_image_layer_files: dict[str, Path] = {}
    portrait_defs = scan_portrait_defs(game_dir)
    portrait_layer_files: dict[str, Path] = {}

    text, flagged = emit_script_vnds(
        [(label.name, label.body) for label in _reorder_entry_label(script.labels)],
        script.characters,
        script.images,
        script.top_level_sets,
        script.screens,
        character_images,
        assets_dir,
        character_image_layer_files,
        portrait_defs,
        portrait_layer_files,
    )
    script_dir = output_dir / "script"
    script_dir.mkdir(parents=True, exist_ok=True)
    (script_dir / "main.scr").write_text(text, encoding="utf-8")

    if script.default_font is not None:
        # The game's real dialogue font (`style.default.font` or `define
        # gui.default_font`, recovered from raw source text -- see
        # rpy_parser.py's `_scan_default_font`) usually lives alongside the
        # .rpy source (e.g. `game/gui/HanSrf.ttf`, Jisei's case), so game_dir
        # is tried first. Some games instead RPA-pack their fonts alongside
        # images/audio (confirmed against Mice Tea's `VarelaRound.ttf`, which
        # only exists inside the extracted asset archive, never as a loose
        # file next to the .rpy source) -- assets_dir is the fallback for
        # that case. text.moon's `update_font` already looks for exactly this
        # filename at the bundle's own root -- this was previously dead code,
        # since nothing ever produced one.
        font_source = game_dir / script.default_font
        if not font_source.is_file() and assets_dir is not None:
            font_source = assets_dir / script.default_font
        if font_source.is_file():
            shutil.copy(font_source, output_dir / "default.ttf")
            _compile_bcfnt(output_dir / "default.ttf", output_dir / "default.bcfnt")

    if script.default_text_cps is not None:
        # The game's own typewriter reveal speed (`config.default_text_cps`/
        # `config.text_cps`, recovered from raw source text -- see
        # rpy_parser.py's `_scan_default_text_cps`), written the same
        # lightweight way default_font is (a bare file at the bundle root,
        # not a manifest.json field -- the engine doesn't read manifest.json
        # at all yet). text.moon checks for exactly this filename, falling
        # back to its previous hardcoded 40 cps when absent.
        (output_dir / "text_cps.txt").write_text(str(script.default_text_cps), encoding="utf-8")

    report = build_problem_report(game_name, converter_version, flagged, parser_problems=problems)
    (output_dir / "problems.json").write_text(emit_problems_json(report), encoding="utf-8")
    (output_dir / "problems.md").write_text(format_report_table(report), encoding="utf-8")

    ui_resolved: dict[str, str] = {}
    if assets_dir is not None:
        required = required_asset_names(text)
        composite_converted, composite_failed = resolve_composite_images(
            script.composites, assets_dir, output_dir, required["foreground"], script.screen_resolution or (800, 600)
        )
        # Resolved composites (base+eyebrows+mouth+eyes stacked into one real
        # image, see resolve_composite_images's docstring) are already
        # written under their resolved basename -- remove them from
        # `required` so the plain by-basename search below doesn't report
        # them "missing" just because no single source file happens to share
        # that name.
        for tag in script.composites:
            required["foreground"].discard(tag.replace(" ", "_"))
        # Same reasoning as composites: CharacterImage layer files are
        # resolved dynamically (never a declared `image NAME = "path"`), so
        # they're converted explicitly from the exact source paths the
        # emitter already resolved, then excluded from the generic
        # by-basename search below.
        ci_converted, ci_failed = resolve_character_image_layers(
            character_image_layer_files, output_dir, required["foreground"], script.screen_resolution or (800, 600)
        )
        for basename in character_image_layer_files:
            required["foreground"].discard(basename)
        # Portrait (ChangePortrait) layer files are resolved dynamically too
        # (never a declared `image NAME = "path"`) -- resolve_character_image_layers
        # is generic enough (just a basename -> real source Path map) to
        # reuse directly for these as well.
        portrait_converted, portrait_failed = resolve_character_image_layers(
            portrait_layer_files, output_dir, required["foreground"], script.screen_resolution or (800, 600)
        )
        for basename in portrait_layer_files:
            required["foreground"].discard(basename)
        # The custom UI-asset-import system (VN3DS-spec.md §6) -- GUI chrome
        # is never referenced by the emitted script at all (no bgload/setimg
        # for it), so there's no `required_*` set to filter against; every
        # distinct path rpy_parser.py's scans found relevant is collected
        # directly from `script` here.
        ui_paths: set[str] = set()
        if script.textbox_image:
            ui_paths.add(script.textbox_image)
        if script.namebox:
            ui_paths.add(script.namebox.image)
        if script.choice_idle:
            ui_paths.add(script.choice_idle.image)
        if script.choice_hover:
            ui_paths.add(script.choice_hover.image)
        for cdef in script.characters.values():
            if cdef.namebox_background:
                ui_paths.add(cdef.namebox_background)
        ui_resolved, _ui_converted, ui_failed = resolve_ui_assets(ui_paths, assets_dir, output_dir)
        _converted, missing, failed = resolve_and_convert_assets(
            assets_dir, output_dir, required, script.screen_resolution or (800, 600)
        )
        failed = (
            [(path, error) for path, error in failed]
            + [(Path(tag), error) for tag, error in composite_failed]
            + [(Path(name), error) for name, error in ci_failed]
            + [(Path(name), error) for name, error in portrait_failed]
            + [(Path(name), error) for name, error in ui_failed]
        )
        missing_path = output_dir / "missing_assets.txt"
        if missing:
            missing_path.write_text("\n".join(sorted(missing)) + "\n", encoding="utf-8")
        elif missing_path.exists():
            missing_path.unlink()  # stale from a prior run of this same output_dir
        failed_path = output_dir / "failed_assets.txt"
        if failed:
            lines = [f"{path}: {error}" for path, error in failed]
            failed_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        elif failed_path.exists():
            failed_path.unlink()  # stale from a prior run of this same output_dir

    # Written last, now that ui_resolved (needs assets_dir's conversion
    # results, if any) is known -- the manifest's "ui" section needs the
    # *converted* bundle basenames, not raw source-relative paths.
    (output_dir / "manifest.json").write_text(
        emit_manifest_json(script, ui_resolved=ui_resolved), encoding="utf-8"
    )

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_dir", type=Path, help="Path to the Ren'Py game/ folder (containing .rpy files)")
    parser.add_argument("output_dir", type=Path, help="Path to write the bundle (script/, manifest.json, ...)")
    parser.add_argument("--name", required=True, help="Game name, recorded in the Problem Report")
    parser.add_argument("--assets", type=Path, default=None, help="Path to extracted image/audio assets, if converting them too")
    args = parser.parse_args(argv)

    report = build_bundle(args.game_dir, args.output_dir, game_name=args.name, assets_dir=args.assets)
    # Windows' default console codepage (cp1252) can't encode arbitrary
    # source content (e.g. Japanese dialogue quoted in a Problem Report
    # message) -- force UTF-8 regardless of the host console so this
    # never crashes instead of printing the report.
    sys.stdout.reconfigure(encoding="utf-8")
    print(format_report_table(report))
    return 1 if has_blocking(report) else 0


if __name__ == "__main__":
    sys.exit(main())
