"""Runs harvest.rpy inside a scratch copy of a Ren'Py game (REWORK-PLAN §5).

The game's own Ren'Py does the reading, so every version's grammar, .rpyc
format and archive layout is handled by the engine that wrote it. The
installed game is never modified: Ren'Py writes caches and compiled files
next to its scripts, so it runs from a full copy.
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


def prepare(game_dir: Path, scratch: Path) -> Path:
    """Copies the game into `scratch` (once) and installs the harvest script."""
    copy = scratch / game_dir.name
    if not copy.exists():
        shutil.copytree(game_dir, copy)
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

    env = dict(os.environ, WITCH_HARVEST_OUT=str(out))
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
            raise HarvestError(f"Ren'Py failed while harvesting {game_dir.name}:\n"
                               + traceback.read_text(encoding="utf-8", errors="replace"))
        time.sleep(0.25)
    raise HarvestError(f"no harvest from {game_dir.name} after {timeout:.0f} s")
