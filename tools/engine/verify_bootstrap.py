"""Verify the Phase 0.1 engine bootstrap import is structurally intact.

This script does not replace `alfons compile`, `busted`, or `lovebrew`; it gives a
fast deterministic check on machines where the Lua/LÖVE Potion toolchain is not
yet installed.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = [
    "Alfons.moon",
    "lovebrew.toml",
    "src/engine/main.moon",
    "src/engine/conf.moon",
    "src/engine/script.moon",
    "src/engine/lib/json.lua",
    "src/engine/UPSTREAM-NOTICE.md",
    "tests/engine/upstream/vnds_spec.moon",
    "tests/engine/upstream/color_spec.moon",
    "tools/engine/3ds_convert.sh",
]

FORBIDDEN_IN_SOURCE = [
    "build/engine/vnds/main.lua",
    "vnds/main.lua",
]


def main() -> int:
    failures: list[str] = []

    for rel in REQUIRED_FILES:
        if not (ROOT / rel).is_file():
            failures.append(f"missing required file: {rel}")

    for rel in FORBIDDEN_IN_SOURCE:
        if (ROOT / rel).exists():
            failures.append(f"generated runtime artifact should not be committed: {rel}")

    source_moon = sorted((ROOT / "src/engine").rglob("*.moon"))
    if len(source_moon) < 10:
        failures.append(f"expected upstream MoonScript source files, found {len(source_moon)}")

    if not list((ROOT / "tests/engine/upstream").glob("*_spec.moon")):
        failures.append("expected upstream busted specs under tests/engine/upstream")

    tool_status = {
        "moonc": shutil.which("moonc"),
        "alfons": shutil.which("alfons"),
        "busted": shutil.which("busted"),
        "lovebrew": shutil.which("lovebrew"),
    }

    print("Phase 0.1 engine bootstrap structural check")
    print(f"root: {ROOT}")
    print(f"moon source files: {len(source_moon)}")
    for tool, path in tool_status.items():
        print(f"tool {tool}: {path or 'MISSING'}")

    if failures:
        print("FAILURES:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    missing_tools = [tool for tool, path in tool_status.items() if path is None]
    if missing_tools:
        print("WARNING: Lua/LÖVE Potion toolchain incomplete; skipped compile/test/package commands.")
        print("missing tools: " + ", ".join(missing_tools))

    print("structural check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
