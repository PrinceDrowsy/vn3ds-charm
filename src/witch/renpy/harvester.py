"""Runs harvest.rpy inside a scratch copy of a Ren'Py game (REWORK-PLAN §5).

The game's own Ren'Py does the reading, so every version's grammar, .rpyc
format and archive layout is handled by the engine that wrote it. The
installed game is never modified: Ren'Py writes caches and compiled scripts
next to its scripts (truncating them in place), so it runs from a copy.
Archives and media, which Ren'Py only reads, are hard-linked into the copy
when it's on the same drive, so a 13 GB game doesn't cost 13 GB again.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

HARVEST_RPY = Path(__file__).with_name("harvest.rpy")
INSTALLED_NAME = "zzz_witch_harvest.rpy"  # sorts last, so it runs after the game's own init 999 code


class HarvestError(Exception):
    pass


def find_launcher(game_dir: Path) -> Path:
    """The game's own .exe: Ren'Py names it after the launcher script `<name>.py`."""
    for script in sorted(game_dir.glob("*.py")):
        exe = script.with_suffix(".exe")
        if exe.exists():
            return exe
    raise HarvestError(f"{game_dir} doesn't look like a Ren'Py game: no <name>.py with a matching .exe")


READ_ONLY_SUFFIXES = {
    ".rpa", ".rpi", ".ogg", ".opus", ".mp3", ".wav", ".flac", ".png", ".jpg", ".jpeg", ".webp", ".avif",
    ".gif", ".bmp", ".webm", ".mp4", ".ogv", ".avi", ".mkv", ".mpg", ".ttf", ".otf", ".ttc",
}


def _link_or_copy(src: str, dst: str) -> None:
    if Path(src).suffix.lower() in READ_ONLY_SUFFIXES:
        try:
            os.link(src, dst)
            return
        except OSError:
            pass  # another drive, or a filesystem without hard links
    shutil.copy2(src, dst)


def prepare(game_dir: Path, scratch: Path) -> Path:
    """Copies the game into `scratch` (once) and installs the harvest script."""
    copy = scratch / game_dir.name
    if not copy.exists():
        shutil.copytree(game_dir, copy, copy_function=_link_or_copy)
    shutil.copy2(HARVEST_RPY, copy / "game" / INSTALLED_NAME)
    for stale in (copy / "game").glob(INSTALLED_NAME + "c"):
        stale.unlink()
    return copy


def harvest(game_dir: Path, scratch: Path, timeout: float = 600) -> dict:
    copy = prepare(game_dir, scratch)
    out = scratch / f"{game_dir.name}.harvest.json"
    out.unlink(missing_ok=True)
    traceback = copy / "traceback.txt"
    traceback.unlink(missing_ok=True)

    # RENPY_NO_STEAM is Ren'Py's own switch: without it, a harvest would sign
    # in to Steam as the game and count as playtime.
    env = dict(os.environ, WITCH_HARVEST_OUT=str(out), RENPY_NO_STEAM="1")
    # Ren'Py's .exe may hand off to the real engine process and return at
    # once, so completion is detected by the output file appearing.
    subprocess.Popen([str(find_launcher(copy)), ".", "witch_harvest", "--savedir", str(scratch / "saves" / game_dir.name)],
                     cwd=copy, env=env)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if out.exists():
            return json.loads(out.read_text(encoding="utf-8"))
        if traceback.exists():
            time.sleep(0.5)  # let Ren'Py finish writing it
            _close(copy)
            raise HarvestError(f"Ren'Py failed while harvesting {game_dir.name}:\n"
                               + traceback.read_text(encoding="utf-8", errors="replace"))
        time.sleep(0.25)
    # A game can stop on its own error screen without writing a traceback.
    _close(copy)
    raise HarvestError(f"no harvest from {game_dir.name} after {timeout:.0f} s; see {copy / 'log.txt'}")


def _close(copy: Path) -> None:
    """Ends every process running from the scratch copy, the only processes
    a harvest starts."""
    prefix = str(copy.resolve()).replace("'", "''")
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"Get-CimInstance Win32_Process | Where-Object {{ $_.ExecutablePath -like '{prefix}\\*' }}"
                    " | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                   check=False, capture_output=True)
