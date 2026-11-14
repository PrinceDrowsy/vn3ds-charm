"""A stand-in for a game's steam_api DLL, used only in the harvest's scratch copy.

Some games call SteamAPI_RestartAppIfNecessary at startup and, when not
launched by Steam, have Steam start the installed game and exit. The stand-in
exports every name the real DLL does, each returning 0: Init fails,
RestartAppIfNecessary says no, interface getters return null, so the game
runs as if Steam weren't there and Steam is never contacted.

It's a minimal PE image written directly, for x86 and x64, so no compiler is
needed: one section holding the export table and a single function,
`xor eax, eax; ret`, which every export points at (cdecl on x86, so the
caller cleans up whatever arguments it passed).
"""
from __future__ import annotations

import struct

I386, AMD64 = 0x14C, 0x8664
RETURN_ZERO = b"\x31\xc0\xc3"  # xor eax, eax; ret

_SECTION_RVA = 0x1000
_FILE_ALIGN = 0x200


def _sections(data: bytes, pe: int, count: int, optional_size: int):
    table = pe + 24 + optional_size
    for i in range(count):
        _, vsize, rva, raw_size, raw_ptr = struct.unpack_from("<8sIIII", data, table + 40 * i)
        yield rva, max(vsize, raw_size), raw_ptr


def export_names(dll: bytes) -> tuple[int, list[str]]:
    """The machine type and exported function names of a PE DLL."""
    data = dll
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("not a PE image")
    machine, sections, _, _, _, optional_size, _ = struct.unpack_from("<HHIIIHH", data, pe + 4)
    optional = pe + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    directories = optional + (96 if magic == 0x10B else 112)
    export_rva, _ = struct.unpack_from("<II", data, directories)
    spans = list(_sections(data, pe, sections, optional_size))

    def offset(rva: int) -> int:
        for start, size, raw in spans:
            if start <= rva < start + size:
                return raw + rva - start
        raise ValueError(f"RVA {rva:#x} is outside every section")

    if not export_rva:
        return machine, []
    directory = offset(export_rva)
    (count,) = struct.unpack_from("<I", data, directory + 24)  # NumberOfNames
    (names_rva,) = struct.unpack_from("<I", data, directory + 32)  # AddressOfNames
    names = []
    for i in range(count):
        at = offset(struct.unpack_from("<I", data, offset(names_rva) + 4 * i)[0])
        names.append(data[at:data.index(b"\0", at)].decode("ascii"))
    return machine, names


def stub_dll(machine: int, names: list[str], dll_name: str) -> bytes:
    """A DLL exporting `names`, every one returning 0."""
    names = sorted(set(names), key=lambda n: n.encode("ascii"))  # the loader binary-searches them
    n = len(names)
    # Section layout: code, export directory, the three arrays, then strings.
    code = 0
    directory = 16
    functions = directory + 40
    name_ptrs = functions + 4 * n
    ordinals = name_ptrs + 4 * n
    strings = ordinals + 2 * n
    blob = bytearray(RETURN_ZERO.ljust(16, b"\xcc"))
    string_data = bytearray()
    string_rvas = []
    for s in [dll_name] + names:
        string_rvas.append(_SECTION_RVA + strings + len(string_data))
        string_data += s.encode("ascii") + b"\0"
    blob += struct.pack("<IIHHIIIIIII", 0, 0, 0, 0, string_rvas[0], 1, n, n,
                        _SECTION_RVA + functions, _SECTION_RVA + name_ptrs, _SECTION_RVA + ordinals)
    blob += struct.pack(f"<{n}I", *([_SECTION_RVA + code] * n))
    blob += struct.pack(f"<{n}I", *string_rvas[1:])
    blob += struct.pack(f"<{n}H", *range(n))
    blob += string_data
    export_size = len(blob) - directory

    pe32 = machine == I386
    optional_size = 224 if pe32 else 240
    headers_size = 0x40 + 24 + optional_size + 40
    headers_raw = _align(headers_size, _FILE_ALIGN)
    raw_size = _align(len(blob), _FILE_ALIGN)
    image_size = _SECTION_RVA + _align(len(blob), 0x1000)

    out = bytearray(b"MZ".ljust(0x3C, b"\0") + struct.pack("<I", 0x40))
    out += b"PE\0\0"
    characteristics = 0x2002 | (0x100 if pe32 else 0x20)  # executable DLL; 32-bit / large-address-aware
    out += struct.pack("<HHIIIHH", machine, 1, 0, 0, 0, optional_size, characteristics)
    out += struct.pack("<HBBIIIII", 0x10B if pe32 else 0x20B, 14, 0, raw_size, raw_size, 0, 0, _SECTION_RVA)
    if pe32:
        out += struct.pack("<II", _SECTION_RVA, 0x10000000)  # BaseOfData, ImageBase
    else:
        out += struct.pack("<Q", 0x180000000)
    out += struct.pack("<IIHHHHHHIIIIHH", 0x1000, _FILE_ALIGN, 6, 0, 0, 0, 6, 0, 0, image_size,
                       headers_raw, 0, 2, 0x100)  # Windows GUI subsystem, NX-compatible
    sizes = (0x100000, 0x1000, 0x100000, 0x1000)
    out += struct.pack("<IIII" if pe32 else "<QQQQ", *sizes)
    out += struct.pack("<II", 0, 16)
    out += struct.pack("<II", _SECTION_RVA + directory, export_size) + bytes(8 * 15)
    out += struct.pack("<8sIIIIIIHHI", b".text", len(blob), _SECTION_RVA, raw_size, headers_raw,
                       0, 0, 0, 0, 0x60000060)  # code, initialized data, execute, read
    out = out.ljust(headers_raw, b"\0")
    out += bytes(blob).ljust(raw_size, b"\0")
    return bytes(out)


def _align(n: int, to: int) -> int:
    return -(-n // to) * to
