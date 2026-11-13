"""Image -> .t3x and audio -> .ogg re-encoding, invoked as subprocesses
(STACK-CONVERTER.md's asset pipeline section): tex3ds (devkitPro) for
textures, ffmpeg for audio.

Scope: this converts a *given source file* to the 3DS-ready format. Resolving
Ren'Py image tags (`show eileen happy`) to an actual source file via `image`
statement declarations is a separate, not-yet-scoped concern (noted in
Phase 1.2's GAME-PLAN.md entry) - this module doesn't need to solve that to
be useful on its own.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - exercised only in environments without Pillow
    Image = None

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
AUDIO_EXTENSIONS = {".ogg", ".mp3", ".wav", ".flac", ".m4a"}

# devkitPro's installer doesn't put tex3ds on PATH by default on this project's
# dev machine (base/ENVIRONMENT.md) - fall back to its known install location.
_TEX3DS_FALLBACKS = (Path("C:/devkitPro/tools/bin/tex3ds.exe"),)
_FFMPEG_FALLBACKS: tuple[Path, ...] = ()

# PICA200 (3DS GPU) hard texture size limit. tex3ds rejects anything larger
# with "Invalid width"/"Invalid height" -- confirmed on real Jisei CGs (e.g.
# a 1024x1536 opening CG) that are common source-game resolutions but exceed
# what the hardware can hold as a single texture. A full atlas/tiling system
# is out of scope for now (Phase 4.2) -- downscaling to fit is a cheap
# stopgap that at least makes oversized art appear instead of silently
# vanishing (real hardware symptom: the opening scene's bgload/setimg both
# referenced assets that failed this exact check, so nothing rendered).
_MAX_TEXTURE_DIMENSION = 1024

# script.moon's "setimg" coordinate system and images.moon's
# draw_foreground (positions and sizes sprites at
# `pscale = min(screenW/400, screenH/240)`) assume foreground art's pixel
# size is meaningful relative to the O3DS top screen's own resolution
# (400x240) -- this project targets 3DS hardware natively rather than the
# original DS's 256x192. Ren'Py source art is typically full desktop
# resolution (500-1500px+), several times larger than that -- on real
# hardware this meant a sprite rendered at the *correct* position but
# wildly oversized, blowing off the edge of the screen, so foreground art
# needs *some* downscale cap (separately from `_MAX_TEXTURE_DIMENSION`,
# which only prevents a hardware rejection, not an absurd on-screen size).
#
# A flat "cap width to 400, leave height free" policy (this constant's
# original approach) was itself wrong, confirmed by a second real-hardware
# regression: it only ever resizes an image whose *own* width already
# exceeds 400 -- Jisei's real character layers (e.g. a 286x768 base pose)
# are narrower than that, so the cap never triggered at all, leaving the
# sprite at its full 768-tall native size drawn 1:1 onto the 240-tall
# target screen -- wildly oversized, the opposite problem from what this
# policy was built to prevent. The real invariant a foreground image needs
# is the *same* proportional shrink the rest of the game's composition
# gets -- background art, sprite xpos/ypos (`_resolve_atl_value`) -- not
# an independent, art-shape-dependent "fit to a fixed pixel box" heuristic
# that happens to work for some games' aspect ratios and not others'.
#
# Backgrounds *do* need their own cap, unlike an earlier version of this
# comment used to claim -- confirmed wrong by a real-hardware regression.
# That claim ("images.moon's bgload handler already rescales the
# background to fill the screen based on its own actual pixel dimensions")
# described a since-*removed* bgload mechanism that used to mutate the
# engine's own device/window reference resolution to match whatever
# background last loaded -- a real bug in its own right (it corrupted
# every sprite's on-screen scale and, via a `love.resize` side effect,
# silently reverted any per-novel custom font mid-story), fixed by
# deleting that mechanism entirely. Once removed, backgrounds draw at
# their own true pixel size scaled only by the stable device-vs-target
# ratio (~1.0 on real O3DS hardware) -- meaning a background authored at
# the source game's own real design resolution (confirmed real content:
# Jisei's actual background files are a genuine 1024x768, matching its
# declared `config.screen_width`/`config.screen_height`) now draws
# hugely oversized instead of filling the screen. Cap to the engine's own
# fixed 400x240 reference resolution, aspect-preserving (same as
# `_downscale_if_oversized` already does for anything else) -- matches
# `draw_background`'s own `scale = math.min(sx, sy)` runtime draw exactly.
_BACKGROUND_MAX_WIDTH = 400
_BACKGROUND_MAX_HEIGHT = 240


# `_foreground_scale_for` derives one proportional scale factor from the
# game's own declared resolution, the same way `_BACKGROUND_MAX_WIDTH`
# derives background sizing -- applied via `convert_image`'s `scale`
# parameter (always-applied, not "only if oversized"), with `max_width`/
# `max_height` still passed as a `_MAX_TEXTURE_DIMENSION` hardware-safety
# backstop afterward (scaling down *from* the game's own resolution can
# never itself produce something exceeding it, but the backstop costs
# nothing to keep). This still naturally reproduces the original "cropped,
# not shrunk" framing for character art authored to fill/overflow the
# frame (real content confirmed: a character meant to span the full
# height of the game's own canvas still spans the full height of the
# target screen once scaled by this same ratio) — it just derives the
# right ratio from the *game's* resolution instead of guessing per-image.
def _foreground_scale_for(screen_resolution: tuple[int, int]) -> float:
    screen_width, screen_height = screen_resolution
    return min(_BACKGROUND_MAX_WIDTH / screen_width, _BACKGROUND_MAX_HEIGHT / screen_height)


class AssetConversionError(Exception):
    pass


def find_tool(name: str, *fallback_paths: Path) -> Path:
    found = shutil.which(name)
    if found:
        return Path(found)
    for candidate in fallback_paths:
        if candidate.exists():
            return candidate
    raise AssetConversionError(f"required tool not found on PATH or in fallback locations: {name}")


def _downscale_if_oversized(source: Path, work_dir: Path, max_width: int, max_height: int | None = None) -> Path:
    """Returns `source` unchanged if it already fits within `max_width` x
    `max_height` (or Pillow isn't available to check/resize); otherwise
    resizes it into `work_dir`, preserving aspect ratio so *both* edges
    fit, and returns the resized copy. `max_height` defaults to
    `max_width` (a square cap, e.g. for the hardware texture limit, where
    the two edges have no independent meaning)."""
    if max_height is None:
        max_height = max_width
    if Image is None:
        return source
    try:
        with Image.open(source) as img:
            width, height = img.size
            if width <= max_width and height <= max_height:
                return source
            scale = min(max_width / width, max_height / height)
            new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
            resized = img.convert("RGB") if img.mode not in ("RGB", "RGBA") else img
            resized = resized.resize(new_size, Image.LANCZOS)
            dest = work_dir / source.name
            resized.save(dest)
            return dest
    except Exception:
        # not a real/readable image (e.g. a corrupt file) -- let tex3ds
        # itself produce the real error rather than failing here.
        return source


def _scale_image_by_factor(source: Path, work_dir: Path, scale: float) -> Path:
    """Resizes `source` by exactly `scale`, unconditionally -- unlike
    `_downscale_if_oversized`'s "only if the box is exceeded, scale
    computed per-image" semantics, this always applies the same *given*
    ratio (real-hardware regression this fixes: see
    `_FOREGROUND_SCALE_FOR`'s own docstring for why foreground/character
    art needs a scale derived from the game's own declared resolution,
    not an independent per-image "fit to a fixed pixel box" heuristic).
    A no-op when `scale >= 1` (nothing to shrink) or Pillow isn't
    available."""
    if Image is None or scale >= 1.0:
        return source
    try:
        with Image.open(source) as img:
            width, height = img.size
            new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
            resized = img.convert("RGB") if img.mode not in ("RGB", "RGBA") else img
            resized = resized.resize(new_size, Image.LANCZOS)
            dest = work_dir / source.name
            resized.save(dest)
            return dest
    except Exception:
        return source


def convert_image(
    source: Path,
    dest: Path,
    *,
    tex3ds: Path | None = None,
    format: str = "auto-etc1",
    max_width: int = _MAX_TEXTURE_DIMENSION,
    max_height: int | None = None,
    scale: float | None = None,
) -> None:
    """format="auto-etc1" (tex3ds's own alpha-detection) matches the project's
    production texture budget: ETC1 (no alpha) or ETC1A4 (with alpha) per
    VN3DS-spec.md's O3DS stress test description, rather than uncompressed
    RGBA8. `max_width`/`max_height` default to a square hardware-texture-limit
    cap; callers placing art into VNDS's `background/` folder should pass
    `_BACKGROUND_MAX_WIDTH`/`_BACKGROUND_MAX_HEIGHT` instead (see that
    constant's own docstring). Foreground/character art should pass `scale`
    instead of `max_width` (see `_FOREGROUND_SCALE_FOR`'s docstring) —
    applied first via `_scale_image_by_factor`, then `max_width`/
    `max_height` still apply afterward as a hardware-safety backstop."""
    tool = tex3ds or find_tool("tex3ds", *_TEX3DS_FALLBACKS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        actual_source = source
        if scale is not None:
            actual_source = _scale_image_by_factor(actual_source, Path(tmp), scale)
        actual_source = _downscale_if_oversized(actual_source, Path(tmp), max_width, max_height)
        result = subprocess.run(
            [str(tool), "-f", format, "-o", str(dest), str(actual_source)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssetConversionError(f"tex3ds failed for {source}: {result.stderr.strip()}")


def convert_audio(source: Path, dest: Path, *, ffmpeg: Path | None = None) -> None:
    tool = ffmpeg or find_tool("ffmpeg", *_FFMPEG_FALLBACKS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(tool), "-y", "-i", str(source), "-c:a", "libvorbis", str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssetConversionError(f"ffmpeg failed for {source}: {result.stderr.strip()}")


@dataclass
class ConvertedAsset:
    source: Path
    dest: Path
    kind: str  # "image" | "audio"


def convert_assets(source_dir: Path, dest_dir: Path) -> list[ConvertedAsset]:
    """Walks source_dir, converting every recognized image/audio file into
    dest_dir, preserving the relative folder structure."""
    converted: list[ConvertedAsset] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source_dir)
        ext = path.suffix.lower()
        if ext in IMAGE_EXTENSIONS:
            dest = dest_dir / rel.with_suffix(".t3x")
            convert_image(path, dest)
            converted.append(ConvertedAsset(source=path, dest=dest, kind="image"))
        elif ext in AUDIO_EXTENSIONS:
            dest = dest_dir / rel.with_suffix(".ogg")
            convert_audio(path, dest)
            converted.append(ConvertedAsset(source=path, dest=dest, kind="audio"))
    return converted


def resolve_composite_images(
    composites: dict[str, list[str]],
    source_dir: Path,
    dest_dir: Path,
    required_foreground: set[str],
    screen_resolution: tuple[int, int] = (800, 600),
) -> tuple[list[ConvertedAsset], list[tuple[str, str]]]:
    """Builds a real image for each `image <tag> = im.Composite(...)`
    declaration the emitted script actually references (its resolved
    basename — `tag.replace(" ", "_")`, matching
    `vnds_writer._resolve_image_path`'s fallback — is in
    `required_foreground`), by alpha-compositing the declared layers in
    order onto a canvas sized to the first layer. Without this, `setimg`
    referenced a basename the asset pipeline never produced (real hardware
    symptom: composite-based characters' sprites silently never appeared,
    since `main.moon`'s `path_exists` check just skips a `setimg` whose
    file is missing rather than erroring).

    Returns (converted, failed); tags not present in `required_foreground`
    are skipped (no dialogue in this playthrough ever showed them), and a
    tag whose layers can't all be found/opened is reported in `failed`
    rather than raising, matching `resolve_and_convert_assets`'s
    fail-soft-per-asset behavior."""
    converted: list[ConvertedAsset] = []
    failed: list[tuple[str, str]] = []
    if Image is None:
        return converted, failed
    for tag, layers in composites.items():
        basename = tag.replace(" ", "_")
        if basename not in required_foreground:
            continue
        layer_paths = [source_dir / layer for layer in layers]
        missing = [str(p) for p in layer_paths if not p.is_file()]
        if missing:
            failed.append((tag, f"composite layer(s) not found: {', '.join(missing)}"))
            continue
        try:
            canvas = None
            for layer_path in layer_paths:
                with Image.open(layer_path) as layer_img:
                    layer_rgba = layer_img.convert("RGBA")
                    if canvas is None:
                        canvas = layer_rgba.copy()
                    else:
                        canvas.alpha_composite(layer_rgba)
        except Exception as exc:  # not a real/readable image
            failed.append((tag, str(exc)))
            continue
        with tempfile.TemporaryDirectory() as tmp:
            composited_path = Path(tmp) / f"{basename}.png"
            canvas.save(composited_path)
            dest = dest_dir / "foreground" / f"{basename}.t3x"
            try:
                convert_image(composited_path, dest, scale=_foreground_scale_for(screen_resolution))
            except AssetConversionError as exc:
                failed.append((tag, str(exc)))
                continue
        converted.append(ConvertedAsset(source=layer_paths[0], dest=dest, kind="image"))
    return converted, failed


def resolve_character_image_layers(
    layer_files: dict[str, Path],
    dest_dir: Path,
    required_foreground: set[str],
    screen_resolution: tuple[int, int] = (800, 600),
) -> tuple[list[ConvertedAsset], list[tuple[str, str]]]:
    """Converts each real per-character `CharacterImage` layer PNG the
    emitted script actually references into a plain foreground `.t3x`.

    These layers are never behind an `image NAME = "path"` declaration --
    they're resolved dynamically per attribute combination at emission
    time (see character_image.py's `resolve_layer_file`) -- so
    `resolve_and_convert_assets`'s generic whole-tree-by-exact-stem search
    would never find them (and couldn't, since the same basename can only
    map to one real file there, while a game can have same-named layers
    across different characters' own folders). `layer_files` maps a
    normalized basename (`vnds_writer._character_layer_basename`'s own
    convention, spaces replaced with underscores -- the emitted `setimg`
    line uses exactly this) to the real absolute source path the emitter
    already resolved it to, across every real `show <CharacterImage tag>
    <attrs>` usage in the game. Same fail-soft-per-asset behavior as
    `resolve_and_convert_assets`/`resolve_composite_images`."""
    converted: list[ConvertedAsset] = []
    failed: list[tuple[str, str]] = []
    for basename, source_path in sorted(layer_files.items()):
        if basename not in required_foreground:
            continue
        dest = dest_dir / "foreground" / f"{basename}.t3x"
        try:
            convert_image(source_path, dest, scale=_foreground_scale_for(screen_resolution))
        except AssetConversionError as exc:
            failed.append((basename, str(exc)))
            continue
        converted.append(ConvertedAsset(source=source_path, dest=dest, kind="image"))
    return converted, failed


def resolve_ui_assets(
    ui_paths: set[str], source_dir: Path, dest_dir: Path, *, tex3ds: Path | None = None
) -> tuple[dict[str, str], list[ConvertedAsset], list[tuple[str, str]]]:
    """Converts the custom UI-asset-import system's chrome images (textbox,
    namebox + every per-character namebox override, choice idle/hover
    button backgrounds -- VN3DS-spec.md §6, rpy_parser.py's `_scan_textbox_
    image`/`_scan_namebox_frame`/`_scan_choice_button_frames` plus
    `CharacterDef.namebox_background`) from `source_dir` into `dest_dir`'s
    new "ui/" folder, through the same tex3ds pipeline every other image
    uses. Unlike background/foreground assets, GUI chrome is never
    referenced by the emitted script at all (no bgload/setimg for it), so
    there's no `required_*` set to filter against -- `ui_paths` is already
    exactly the set of source-relative paths this system found relevant
    (the caller collects it from `Script.textbox_image`/`namebox.image`/
    `choice_idle.image`/`choice_hover.image`/every `CharacterDef.
    namebox_background`).

    Returns (resolved, converted, failed): `resolved` maps each original
    source-relative path to its converted bundle basename (e.g.
    "gui/textbox.png" -> "textbox.t3x") for manifest_writer.py's
    `build_manifest` to look up; `converted`/`failed` match every other
    resolver's fail-soft-per-asset shape (a missing/corrupt UI chrome image
    degrades to the engine's existing flat-color fallback, never a hard
    conversion failure)."""
    resolved: dict[str, str] = {}
    converted: list[ConvertedAsset] = []
    failed: list[tuple[str, str]] = []
    for rel_path in sorted(ui_paths):
        source = source_dir / rel_path
        if not source.is_file():
            failed.append((rel_path, "file not found"))
            continue
        basename = Path(rel_path).stem.replace(" ", "_")
        dest = dest_dir / "ui" / f"{basename}.t3x"
        try:
            convert_image(source, dest, tex3ds=tex3ds)
        except AssetConversionError as exc:
            failed.append((rel_path, str(exc)))
            continue
        resolved[rel_path] = f"{basename}.t3x"
        converted.append(ConvertedAsset(source=source, dest=dest, kind="image"))
    return resolved, converted, failed


def _stem(token: str) -> str:
    return token.rsplit(".", 1)[0] if "." in token else token


def required_asset_names(vnds_text: str) -> dict[str, set[str]]:
    """Scans emitted script.vnds text for bgload/setimg/sound/music/
    voiceover commands, returning the basenames (no extension) each of
    VNDS's fixed background/foreground/sound destination folders needs
    (script.moon's "background/"/"foreground/"/"sound/" prefixes) — a
    convention that rarely matches Ren'Py's own arbitrary asset folder
    layout (images/, gui/, char/, music/, voices/, ...)."""
    required: dict[str, set[str]] = {"background": set(), "foreground": set(), "sound": set()}
    for line in vnds_text.splitlines():
        parts = line.split()
        if not parts:
            continue
        cmd, rest = parts[0], parts[1:]
        if cmd == "bgload" and rest:
            required["background"].add(_stem(rest[0]))
        elif cmd == "imagemap_begin" and rest:
            # an imagemap's `ground` image is drawn exactly like a
            # background (screen.moon's show_imagemap reuses images.moon's
            # draw_background scale/center math) -- same destination
            # bucket as bgload, not the separate ui/ chrome pipeline.
            required["background"].add(_stem(rest[0]))
        elif cmd == "setimg" and rest:
            required["foreground"].add(_stem(rest[0]))
        elif cmd in ("sound", "music", "voiceover") and rest:
            required["sound"].add(_stem(rest[0]))
    return required


# Ren'Py's built-in solid-color images -- "black"/"white" (and any other
# CSS-style color literal, but these two are the only ones confirmed used
# as bare image tags in real content) are synthesized internally by
# Ren'Py from the literal name, never a real file. Confirmed as common,
# general content (119 `scene black`/`show black`/`white` sites across
# Mice Tea alone -- a real day-transition/fade-to-black idiom, not just
# this project's own synthesized title-card sequence) that previously
# always landed in missing_assets.txt with no way to resolve at all.
_BUILTIN_COLOR_IMAGES = {"black": (0, 0, 0), "white": (255, 255, 255)}


def _synthesize_builtin_color_assets(
    dest_dir: Path, remaining: dict[str, set[str]], *, tex3ds: Path | None = None
) -> list[ConvertedAsset]:
    """Generates a solid-color PNG (full O3DS top-screen size, so it never
    needs upscaling to fully cover the frame) and converts it through the
    same tex3ds pipeline as any other asset, for each built-in color name
    still unresolved in either the background or foreground required
    sets after the real-file scan. A no-op (returns []) when Pillow isn't
    available, same graceful degradation `_downscale_if_oversized` already
    uses elsewhere."""
    if Image is None:
        return []
    converted: list[ConvertedAsset] = []
    with tempfile.TemporaryDirectory() as tmp:
        for folder in ("background", "foreground"):
            for name in sorted(remaining[folder] & _BUILTIN_COLOR_IMAGES.keys()):
                png_path = Path(tmp) / f"{name}.png"
                Image.new("RGB", (400, 240), _BUILTIN_COLOR_IMAGES[name]).save(png_path)
                dest = dest_dir / folder / f"{name}.t3x"
                try:
                    convert_image(png_path, dest, tex3ds=tex3ds)
                except AssetConversionError:
                    continue
                converted.append(ConvertedAsset(source=Path(f"<builtin:{name}>"), dest=dest, kind="image"))
                remaining[folder].discard(name)
    return converted


def resolve_and_convert_assets(
    source_dir: Path,
    dest_dir: Path,
    required: dict[str, set[str]],
    screen_resolution: tuple[int, int] = (800, 600),
) -> tuple[list[ConvertedAsset], set[str], list[tuple[Path, str]]]:
    """Walks source_dir (an extracted Ren'Py asset tree, arbitrary folder
    layout) and converts only the files actually referenced by the emitted
    script.vnds (per `required_asset_names`), sorting each into VNDS's
    fixed background/foreground/sound destination folders by basename
    match — regardless of which folder Ren'Py originally kept it in. This
    is the "resolving Ren'Py image tags to an actual source file" gap this
    module's own docstring used to note as not-yet-scoped.

    A single file's conversion failure (e.g. tex3ds rejecting a texture
    that exceeds PICA200's max size or isn't power-of-two — real asset
    *pre-processing*, Phase 4.2's atlas/resize scope, not attempted here)
    is logged and skipped rather than aborting the whole batch — across a
    few hundred real assets, some failures are expected, and one bad CG
    shouldn't block every other asset from converting.

    Returns (converted, still_missing, failed) where `still_missing` is
    "<folder>/<basename>" for anything referenced but never found, and
    `failed` is (path, error message) for files found but that failed
    conversion. The engine gracefully skips any instruction whose asset
    file doesn't exist (main.moon's path_exists check), so a partial
    match is still usable for a smoke test, just missing some
    visuals/audio."""
    converted: list[ConvertedAsset] = []
    failed: list[tuple[Path, str]] = []
    remaining = {folder: set(names) for folder, names in required.items()}
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        base = path.stem
        if ext in IMAGE_EXTENSIONS:
            for folder in ("background", "foreground"):
                if base in remaining[folder]:
                    dest = dest_dir / folder / f"{base}.t3x"
                    remaining[folder].discard(base)  # found -- reported via `failed`, not `missing`, on error
                    try:
                        if folder == "foreground":
                            # scaled by the same proportion as the rest of
                            # the game's composition (see
                            # _foreground_scale_for's docstring) -- same
                            # policy for every foreground image now,
                            # character sprite or full-bleed pan alike.
                            convert_image(path, dest, scale=_foreground_scale_for(screen_resolution))
                        else:
                            # Fit within the engine's own fixed 400x240
                            # reference resolution (see _BACKGROUND_MAX_WIDTH's
                            # docstring for the real-hardware regression this
                            # fixes) -- also covers imagemap's `ground` image,
                            # which shares this same destination bucket and is
                            # drawn with the exact same scale-to-fit math.
                            convert_image(
                                path, dest, max_width=_BACKGROUND_MAX_WIDTH, max_height=_BACKGROUND_MAX_HEIGHT
                            )
                    except AssetConversionError as exc:
                        failed.append((path, str(exc)))
                        continue
                    converted.append(ConvertedAsset(source=path, dest=dest, kind="image"))
        elif ext in AUDIO_EXTENSIONS:
            if base in remaining["sound"]:
                dest = dest_dir / "sound" / f"{base}.ogg"
                remaining["sound"].discard(base)
                try:
                    convert_audio(path, dest)
                except AssetConversionError as exc:
                    failed.append((path, str(exc)))
                    continue
                converted.append(ConvertedAsset(source=path, dest=dest, kind="audio"))
    converted.extend(_synthesize_builtin_color_assets(dest_dir, remaining))
    missing = {f"{folder}/{name}" for folder, names in remaining.items() for name in names}
    return converted, missing, failed
