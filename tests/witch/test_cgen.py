import os
import shutil
import subprocess
from pathlib import Path

import pytest

from witch.bundle import cgen
from witch.bundle.reader import Bundle
from witch.bundle.schema import NONE
from witch.bundle.writer import Writer

READ_CHARM = Path(__file__).resolve().parents[1] / "enchantment" / "read_charm.c"
DEVKITARM_GCC = Path("C:/devkitPro/devkitARM/bin/arm-none-eabi-gcc.exe")


def test_committed_header_is_up_to_date():
    assert cgen.HEADER_PATH.read_text(encoding="utf-8") == cgen.generate(), \
        "charm_schema.h is stale: run `python -m witch.bundle.cgen` from src/"


def _bundle() -> bytes:
    w = Writer()
    start = w.node("label", {"name": "start"})
    say = w.node("say", {"what": "こんにちは"}, flags={"interact"})
    after = w.node("label", {"name": "after"})
    menu = w.node("menu", {"items": [{"label": "Which?"}, {"label": "That one", "block": after}]})
    w.link(start, say, menu)
    w.label("start", start)
    w.label("after", after)
    return w.write()


def _expected(data: bytes) -> str:
    b = Bundle(data)
    lines = [f"nodes {b.count('NODE')}"]
    lines += [f"label {name} {b.node(node).kind.name}" for name, node in b.labels()]
    for i in range(b.count("NODE")):
        n = b.node(i)
        if n.kind.name == "say":
            lines.append(f"say {n.fields['what']} interact={int('interact' in n.flags)}")
        elif n.kind.name == "menu":
            lines += [f"item {item['label']} block={-1 if item['block'] == NONE else item['block']}"
                      for item in n.fields["items"]]
    return "\n".join(lines) + "\n"


def test_c_reader_sees_what_python_wrote(tmp_path):
    gcc = shutil.which("gcc")
    if gcc is None:
        pytest.skip("no desktop C compiler")
    exe = tmp_path / "read_charm.exe"
    # Git for Windows ships older DLLs under the same names as MSYS2's; if its
    # directory comes first on PATH, cc1 loads them and dies with no message.
    env = {**os.environ, "PATH": str(Path(gcc).parent) + os.pathsep + os.environ["PATH"]}
    subprocess.run([gcc, "-std=c17", "-Wall", "-Werror", "-static", "-I", str(cgen.HEADER_PATH.parent),
                    str(READ_CHARM), "-o", str(exe)], check=True, env=env)
    bundle = tmp_path / "test.charm"
    bundle.write_bytes(_bundle())
    result = subprocess.run([str(exe), str(bundle)], capture_output=True, check=True)
    assert result.stdout.decode("utf-8").replace("\r\n", "\n") == _expected(bundle.read_bytes())


def test_header_layout_holds_on_the_3ds():
    gcc = shutil.which("arm-none-eabi-gcc") or (DEVKITARM_GCC if DEVKITARM_GCC.exists() else None)
    if gcc is None:
        pytest.skip("devkitARM isn't installed")
    subprocess.run([str(gcc), "-std=c17", "-march=armv6k", "-mtune=mpcore", "-mfloat-abi=hard", "-Wall", "-Werror",
                    "-fsyntax-only", "-I", str(cgen.HEADER_PATH.parent), str(READ_CHARM)], check=True)
