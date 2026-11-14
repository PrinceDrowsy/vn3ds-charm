import ctypes
import struct
import sys

import pytest

from witch.renpy.steamstub import AMD64, I386, export_names, stub_dll

NAMES = ["SteamAPI_RestartAppIfNecessary", "SteamAPI_InitSafe", "SteamAPI_SteamRemoteStorage_v016",
         "SteamAPI_ISteamUserStats_SetAchievement"]


@pytest.mark.parametrize("machine", [I386, AMD64])
def test_export_table_round_trips(machine):
    dll = stub_dll(machine, NAMES, "steam_api.dll")
    got_machine, names = export_names(dll)
    assert got_machine == machine
    # The loader binary-searches export names, so they must be sorted.
    assert names == sorted(NAMES, key=str.encode)


def test_optional_header_matches_its_size():
    dll = stub_dll(I386, NAMES, "steam_api.dll")
    pe = struct.unpack_from("<I", dll, 0x3C)[0]
    optional_size = struct.unpack_from("<H", dll, pe + 20)[0]
    assert (optional_size, struct.unpack_from("<H", dll, pe + 24)[0]) == (224, 0x10B)


@pytest.mark.skipif(sys.platform != "win32" or sys.maxsize <= 2**32, reason="needs 64-bit Windows to load")
def test_windows_loads_it_and_every_export_returns_zero(tmp_path):
    path = tmp_path / "steam_api64.dll"
    path.write_bytes(stub_dll(AMD64, NAMES, path.name))
    lib = ctypes.CDLL(str(path))
    lib.SteamAPI_RestartAppIfNecessary.restype = ctypes.c_bool
    lib.SteamAPI_SteamRemoteStorage_v016.restype = ctypes.c_void_p
    assert lib.SteamAPI_RestartAppIfNecessary(251990) is False
    assert lib.SteamAPI_SteamRemoteStorage_v016() is None
    assert lib.SteamAPI_ISteamUserStats_SetAchievement(None, b"x") == 0
