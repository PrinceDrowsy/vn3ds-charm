import struct
import zlib

import pytest

from witch.renpy.harvester import HarvestError, find_launcher, relaunches_through_steam

CALL = b"if sapi.SteamAPI_RestartAppIfNecessary(steam_appid):\n    raise SystemExit(3)\n"
DECLARATION = b"sapi.SteamAPI_RestartAppIfNecessary.restype = ctypes.c_bool\n"


def rpc2(body: bytes) -> bytes:
    """A Ren'Py 7/8 .rpyc: a slot table, then zlib-compressed slots."""
    data = zlib.compress(body)
    header = b"RENPY RPC2" + struct.pack("<III", 1, 34, len(data)) + struct.pack("<III", 0, 0, 0)
    return header + data


@pytest.mark.parametrize("name, content, expected", [
    ("steam.rpy", CALL, True),
    ("steam.rpyc", rpc2(DECLARATION + CALL), True),
    ("steam.rpyc", zlib.compress(CALL), True),  # Ren'Py 6's single-stream layout
    ("steam.rpyc", rpc2(DECLARATION), False),
    ("script.rpy", b"label start:\n    'Hi.'\n", False),
])
def test_relaunch_through_steam_is_found_in_loose_scripts(tmp_path, name, content, expected):
    (tmp_path / "game" / "lib").mkdir(parents=True)
    (tmp_path / "game" / "lib" / name).write_bytes(content)
    assert relaunches_through_steam(tmp_path) is expected


def test_launcher_is_the_exe_named_after_the_script(tmp_path):
    (tmp_path / "Game.py").write_text("")
    (tmp_path / "Game.exe").write_bytes(b"")
    (tmp_path / "Game-32.exe").write_bytes(b"")
    assert find_launcher(tmp_path) == tmp_path / "Game.exe"
    (tmp_path / "Game.exe").unlink()
    with pytest.raises(HarvestError):
        find_launcher(tmp_path)
