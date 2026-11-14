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
import struct
import subprocess
import time
import zlib
from datetime import datetime
from pathlib import Path

HARVEST_RPY = Path(__file__).with_name("harvest.rpy")
INSTALLED_NAME = "zzz_witch_harvest.rpy"


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


def _script_bodies(path: Path):
    """The decompressed contents of a .rpyc (both of Ren'Py's layouts), or a .rpy's text."""
    data = path.read_bytes()
    if path.suffix == ".rpy":
        yield data
        return
    chunks = []
    if data.startswith(b"RENPY RPC2"):
        pos = 10
        while True:
            slot, start, length = struct.unpack_from("<III", data, pos)
            pos += 12
            if slot == 0:
                break
            chunks.append(data[start:start + length])
    else:
        chunks.append(data)
    for chunk in chunks:
        try:
            yield zlib.decompress(chunk)
        except zlib.error:
            pass


def relaunches_through_steam(game_dir: Path) -> bool:
    """Whether the game's loose scripts call SteamAPI_RestartAppIfNecessary:
    started outside Steam, such a game has Steam launch the installed copy
    and exits."""
    return any(b"RestartAppIfNecessary(" in body
               for path in (game_dir / "game").rglob("*.rpy*") if path.suffix in (".rpy", ".rpyc")
               for body in _script_bodies(path))


def harvest(game_dir: Path, scratch: Path, timeout: float = 600) -> dict:
    if relaunches_through_steam(game_dir):
        raise HarvestError(f"{game_dir.name} relaunches itself through Steam when started directly, "
                           "so it can't be harvested from a copy as it is")
    copy = prepare(game_dir, scratch)
    out = scratch / f"{game_dir.name}.harvest.json"
    error = out.with_name(out.name + ".error")  # written by harvest.rpy itself
    traceback = copy / "traceback.txt"  # written by Ren'Py
    for stale in (out, error, traceback):
        stale.unlink(missing_ok=True)

    # RENPY_NO_STEAM is Ren'Py's own switch: without it, a harvest would sign
    # in to Steam as the game and count as playtime.
    env = dict(os.environ, WITCH_HARVEST_OUT=str(out), RENPY_NO_STEAM="1")
    # The environment variable starts the harvest (see harvest.rpy), so no
    # positional arguments are needed; launchers differ in which they add.
    # Ren'Py's .exe may hand off to the real engine process and return at
    # once, so completion is detected by the output file appearing.
    launched = datetime.now()
    subprocess.Popen([str(find_launcher(copy)), "--savedir", str(scratch / "saves" / game_dir.name)],
                     cwd=copy, env=env)
    deadline = time.monotonic() + timeout
    polls = 0
    while time.monotonic() < deadline:
        if out.exists():
            return json.loads(out.read_text(encoding="utf-8"))
        for report in (error, traceback):
            if report.exists():
                time.sleep(0.5)  # let it finish writing
                _stop(copy)
                raise HarvestError(f"Ren'Py failed while harvesting {game_dir.name}:\n"
                                   + report.read_text(encoding="utf-8", errors="replace"))
        # Some games, started outside Steam, ask Steam to relaunch the
        # installed copy (SteamAPI_RestartAppIfNecessary) and exit. That copy
        # is closed again at once; anything started before the harvest is
        # left alone.
        polls += 1
        if polls % 8 == 0 and _stop(game_dir, since=launched):
            _stop(copy)
            raise HarvestError(f"{game_dir.name} asked Steam to relaunch it from its installed folder "
                               "(closed again); it can't be harvested from a copy as it is")
        time.sleep(0.25)
    # A game can stop on its own error screen without writing a traceback.
    _stop(copy)
    raise HarvestError(f"no harvest from {game_dir.name} after {timeout:.0f} s; see {copy / 'log.txt'}")


def _stop(folder: Path, since: datetime | None = None) -> bool:
    """Ends the processes running from `folder` (started at or after `since`,
    if given). True if there were any."""
    prefix = str(folder.resolve()).replace("'", "''")
    started = f" -and $_.CreationDate -ge [datetime]'{since:%Y-%m-%dT%H:%M:%S}'" if since else ""
    result = subprocess.run(["powershell", "-NoProfile", "-Command",
                             f"Get-CimInstance Win32_Process | Where-Object {{ $_.ExecutablePath -like '{prefix}\\*'"
                             f"{started} }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force; $_.ProcessId }}"],
                            check=False, capture_output=True, text=True)
    return bool(result.stdout.strip())
