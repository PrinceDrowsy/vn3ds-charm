#!/usr/bin/env python
"""Package the compiled LOVE Potion engine into a .3dsx, entirely locally.

Follows the DDLC-LOVE Makefile pattern (smdhtool -> 3dsxtool) referenced in
base/ENVIRONMENT.md and VN3DS-spec.md Phase 0: a local devkitARM build against
a prebuilt LovePotion.elf, no network dependency on the (now-defunct) lovebrew
bundler service.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "build" / "engine" / "vnds"
OUTPUT_DIR = ROOT / "build" / "lovebrew"
SMDH = OUTPUT_DIR / "VNDS-LOVE.smdh"
OUTPUT = OUTPUT_DIR / "VNDS-LOVE.3dsx"
ICON = ROOT / "src" / "engine" / "icons" / "icon.png"

SDCARD_ROOT = OUTPUT_DIR / "sdcard" / "3ds" / "VNDS-LOVE"
SDCARD_3DSX = SDCARD_ROOT / "VNDS-LOVE.3dsx"
SDCARD_GAME = SDCARD_ROOT / "game"

# LOVE Potion's identity-based save directory (main.moon calls
# love.filesystem.setIdentity("VNDS-LOVE")) resolves to <app folder>/save/<identity>/,
# and that's where main.moon's novel picker looks for /novels — not the SD card root.
FIXTURES_DIR = ROOT / "tests" / "engine" / "fixtures"
SDCARD_NOVELS_DIR = SDCARD_ROOT / "save" / "VNDS-LOVE" / "novels"

LOVEPOTION_ELF = (
    Path.home()
    / "AppData"
    / "Local"
    / "hermes"
    / "toolchains"
    / "lovepotion-2.0.0"
    / "LOVEPotion.elf"
)

DEVKITPRO_TOOLS = Path("C:/devkitPro/tools/bin")
SMDHTOOL = DEVKITPRO_TOOLS / "smdhtool.exe"
DSXTOOL = DEVKITPRO_TOOLS / "3dsxtool.exe"

APP_TITLE = "VNDS-LOVE"
APP_DESCRIPTION = "VNDS-compatible visual novel engine targeting LOVE Potion on 3DS"
APP_AUTHOR = "VN3DS-CHARM; forked from ajusa/VNDS-LOVE"


def run(command: list[str]) -> None:
    print("+", " ".join(str(part) for part in command))
    subprocess.run(command, cwd=ROOT, check=True)


def stage_sdcard_layout() -> None:
    # LOVE Potion 2.0.0 final's boot.lua drops rc1's early-return for a
    # successful romfs fallback, so a stale invalid_game_path from the
    # default "game" folder lookup fires even when romfs loads fine —
    # ship a real external game/ folder so that lookup succeeds first.
    if SDCARD_ROOT.exists():
        shutil.rmtree(SDCARD_ROOT)
    SDCARD_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, SDCARD_GAME)
    shutil.copy2(OUTPUT, SDCARD_3DSX)

    if FIXTURES_DIR.exists():
        SDCARD_NOVELS_DIR.mkdir(parents=True, exist_ok=True)
        for fixture in sorted(FIXTURES_DIR.iterdir()):
            if fixture.is_dir():
                shutil.copytree(fixture, SDCARD_NOVELS_DIR / fixture.name)
    else:
        print(f"warning: fixtures dir not found, skipping: {FIXTURES_DIR}", file=sys.stderr)


def main() -> int:
    for tool, label in ((SMDHTOOL, "smdhtool"), (DSXTOOL, "3dsxtool")):
        if not tool.exists():
            print(f"missing devkitPro tool ({label}): {tool}", file=sys.stderr)
            return 1
    if not LOVEPOTION_ELF.exists():
        print(f"missing LovePotion.elf: {LOVEPOTION_ELF}", file=sys.stderr)
        return 1
    if not SOURCE.exists():
        print(f"missing compiled source directory: {SOURCE}", file=sys.stderr)
        return 1
    if not ICON.exists():
        print(f"missing icon: {ICON}", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    run([str(SMDHTOOL), "--create", APP_TITLE, APP_DESCRIPTION, APP_AUTHOR, str(ICON), str(SMDH)])
    run([
        str(DSXTOOL),
        str(LOVEPOTION_ELF),
        str(OUTPUT),
        f"--smdh={SMDH}",
        f"--romfs={SOURCE}",
    ])

    if not OUTPUT.exists():
        print(f"expected 3dsx output missing: {OUTPUT}", file=sys.stderr)
        return 1

    stage_sdcard_layout()

    if not SDCARD_3DSX.exists() or not (SDCARD_GAME / "main.lua").exists():
        print(f"expected sdcard staging incomplete under: {SDCARD_ROOT}", file=sys.stderr)
        return 1

    print(f"built {OUTPUT} ({OUTPUT.stat().st_size} bytes)")
    print(f"staged sdcard folder {SDCARD_ROOT} (copy contents of build/lovebrew/sdcard/ onto your SD card)")
    if SDCARD_NOVELS_DIR.exists():
        fixtures = sorted(p.name for p in SDCARD_NOVELS_DIR.iterdir() if p.is_dir())
        print(f"included fixtures: {', '.join(fixtures)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
