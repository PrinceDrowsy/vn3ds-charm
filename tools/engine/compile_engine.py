#!/usr/bin/env python
"""Compile the vendored VNDS-LOVE MoonScript engine into a Lua build tree.

This helper keeps Alfons.moon small and avoids Windows/Git Bash quoting issues for
recursive copy, MoonScript compilation, and source cleanup.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "engine"
BUILD = ROOT / "build" / "engine" / "vnds"
MOONC = (
    Path.home()
    / "AppData"
    / "Local"
    / "hermes"
    / "toolchains"
    / "vnds-love-lua51"
    / "bin"
    / "moonc.bat"
)


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True, shell=sys.platform == "win32")


def main() -> int:
    if "--clean" in sys.argv[1:]:
        if BUILD.exists():
            shutil.rmtree(BUILD)
            print(f"removed {BUILD}")
        return 0

    if not SOURCE.exists():
        print(f"missing engine source: {SOURCE}", file=sys.stderr)
        return 1
    if not MOONC.exists():
        print(f"missing MoonScript compiler: {MOONC}", file=sys.stderr)
        return 1

    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, BUILD)

    moon_files = sorted(BUILD.rglob("*.moon"))
    if not moon_files:
        print(f"no MoonScript files found under {BUILD}", file=sys.stderr)
        return 1

    for moon_file in moon_files:
        run([str(MOONC), str(moon_file)])
        moon_file.unlink()

    leftovers = sorted(BUILD.rglob("*.moon"))
    if leftovers:
        print("MoonScript files left after compile:", file=sys.stderr)
        for path in leftovers:
            print(f"  {path}", file=sys.stderr)
        return 1

    lua_files = sorted(BUILD.rglob("*.lua"))
    if not lua_files:
        print(f"no Lua files produced under {BUILD}", file=sys.stderr)
        return 1

    print(f"compiled {len(moon_files)} MoonScript files into {BUILD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
