"""Runs a game's init on MicroPython's desktop build (D18), with Enchantment's
shim, and returns what it produced.

Needs MICROPYTHON_EXE, or MICROPYTHON_DIR with the Windows port built
(ports/windows/build-standard/micropython.exe).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .initprog import program

SHIM_DIR = Path(__file__).resolve().parents[2] / "enchantment" / "python"


def micropython() -> Path:
    if "MICROPYTHON_EXE" in os.environ:
        return Path(os.environ["MICROPYTHON_EXE"])
    return Path(os.environ["MICROPYTHON_DIR"]) / "ports" / "windows" / "build-standard" / "micropython.exe"


def run_init(harvest: dict, work: Path, timeout: float = 600) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    program_path = work / "init-program.json"
    result_path = work / "init-result.json"
    program_path.write_text(json.dumps(program(harvest)), encoding="utf-8")
    result_path.unlink(missing_ok=True)
    # The desktop run isn't the place to fit a 3DS heap (sized per game, §11).
    proc = subprocess.run([str(micropython()), "-X", "heapsize=1024M", "charm_init.py", str(program_path),
                           str(result_path)],
                          cwd=SHIM_DIR, capture_output=True, text=True, timeout=timeout)
    if not result_path.exists():
        raise RuntimeError(f"the init run produced no result (exit {proc.returncode}):\n{proc.stdout}{proc.stderr}")
    return json.loads(result_path.read_text(encoding="utf-8"))
