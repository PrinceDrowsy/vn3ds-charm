"""Builds a `.charm` bundle in memory and serializes it (ADR-007)."""
from __future__ import annotations

import struct
from dataclasses import dataclass

from . import schema
from .schema import NONE, Kind, List, Ref, Struct


@dataclass
class _Record:
    kind: Kind
    flags: int
    fields: dict
    next: int = NONE
    name: str = ""
    file: str = ""
    line: int = 0


@dataclass
class _Asset:
    path: str
    data: bytes
    type: int
    width: int
    height: int


def _flag_bits(kind: Kind, flags) -> int:
    bits = 0
    for flag in flags:
        bits |= 1 << kind.flags.index(flag)
    return bits


class Writer:
    """Collects a bundle's contents. Indices returned by `node`, `code`, `asset`
    and `disp` are what other records refer to; assets are re-sorted by path at
    write time and references to them follow."""

    def __init__(self):
        self._nodes: list[_Record] = []
        self._labels: dict[str, int] = {}
        self._codes: list[tuple[str, int]] = []
        self._assets: list[_Asset] = []
        self._asset_paths: set[str] = set()
        self._disps: list[_Record] = []
        self._images: dict[str, int] = {}

    def node(self, kind: str, fields: dict | None = None, *, node_id: str = "", file: str = "", line: int = 0,
             flags=()) -> int:
        """`fields` is the kind's payload; `node_id` is Ren'Py's own node name, the id saves refer to."""
        k = schema.NODE_KIND_BY_NAME[kind]
        self._nodes.append(_Record(k, _flag_bits(k, flags), fields or {}, name=node_id, file=file, line=line))
        return len(self._nodes) - 1

    def link(self, *nodes: int) -> None:
        """Chains each node's `next` to the one after it."""
        for a, b in zip(nodes, nodes[1:]):
            self._nodes[a].next = b

    def label(self, name: str, node: int) -> None:
        if name in self._labels:
            raise ValueError(f"label {name!r} defined twice")
        self._labels[name] = node

    def code(self, source: str, mode: str = "eval") -> int:
        self._codes.append((source, schema.CODE_MODE[mode]))
        return len(self._codes) - 1

    def asset(self, path: str, data: bytes, *, type: str = "image", width: int = 0, height: int = 0) -> int:
        if path in self._asset_paths:
            raise ValueError(f"asset {path!r} added twice")
        self._asset_paths.add(path)
        self._assets.append(_Asset(path, data, schema.ASSET_TYPE[type], width, height))
        return len(self._assets) - 1

    def disp(self, kind: str, fields: dict | None = None, *, flags=()) -> int:
        k = schema.DISP_KIND_BY_NAME[kind]
        self._disps.append(_Record(k, _flag_bits(k, flags), fields or {}))
        return len(self._disps) - 1

    def image(self, name: str, disp: int) -> None:
        self._images[name] = disp

    def write(self) -> bytes:
        asset_order = sorted(range(len(self._assets)), key=lambda i: self._assets[i].path.encode("utf-8"))
        enc = _Encoder({old: new for new, old in enumerate(asset_order)})

        def payload(rec: _Record) -> int:
            return enc.payload(rec.kind.payload, rec.fields) if rec.kind.payload else 0

        bodies = {
            "NODE": [(r.kind.id, r.flags, r.next, payload(r)) for r in self._nodes],
            "NAME": [(enc.string(r.name),) for r in self._nodes],
            "LOCS": [(enc.string(r.file), r.line) for r in self._nodes],
            "LABL": [(enc.string(name), node) for name, node in
                     sorted(self._labels.items(), key=lambda item: item[0].encode("utf-8"))],
            "CODE": [(enc.string(src), mode, 0, 0) for src, mode in self._codes],
            "IMGS": [(enc.string(name), disp) for name, disp in
                     sorted(self._images.items(), key=lambda item: item[0].encode("utf-8"))],
            "DISP": [(r.kind.id, r.flags, payload(r)) for r in self._disps],
        }
        data = bytearray()
        assets = []
        for i in asset_order:
            a = self._assets[i]
            assets.append((enc.string(a.path), a.type, schema.ASSET_FORMAT["source"],
                           len(data), len(a.data), a.width, a.height))
            data += a.data
        bodies["ASST"] = assets

        blobs = {}
        for section in schema.SECTIONS:
            if section.record:
                blobs[section.tag] = b"".join(struct.pack(section.record.fmt, *row) for row in bodies[section.tag])
        blobs["STRS"] = bytes(enc.strs)
        blobs["ARGS"] = bytes(enc.args)
        blobs["DATA"] = bytes(data)
        blobs["MPYB"] = b""
        return _assemble(blobs)


class _Encoder:
    def __init__(self, asset_index: dict[int, int]):
        self._asset_index = asset_index
        self._strings = {"": 0}
        self.strs = bytearray(b"\0")
        self.args = bytearray()

    def string(self, s: str) -> int:
        off = self._strings.get(s)
        if off is None:
            off = self._strings[s] = len(self.strs)
            self.strs += s.encode("utf-8") + b"\0"
        return off

    def payload(self, st: Struct, fields: dict) -> int:
        flat = self._flatten(st, fields)
        off = len(self.args) // 4
        self.args += struct.pack(st.fmt, *flat)
        return off

    def _flatten(self, st: Struct, fields: dict) -> list:
        unknown = fields.keys() - st.offsets.keys()
        if unknown:
            raise TypeError(f"{st.name} has no field(s) {sorted(unknown)}")
        flat = []
        for fname, ftype in st.fields:
            value = fields.get(fname)
            if isinstance(ftype, List):
                flat += self._list(ftype, value or [])
            else:
                flat.append(self._value(ftype, value))
        return flat

    def _value(self, ftype, value):
        if isinstance(ftype, Ref):
            if ftype.table == "STRS":
                return self.string(value or "")
            if value is None or value == NONE:
                return NONE
            return self._asset_index[value] if ftype.table == "ASST" else value
        return value or 0

    def _list(self, ftype: List, items: list) -> list:
        elem = ftype.elem
        if isinstance(elem, Struct):
            rows = [struct.pack(elem.fmt, *self._flatten(elem, item)) for item in items]
        else:
            rows = [struct.pack("<" + elem.fmt, self._value(elem, item)) for item in items]
        off = len(self.args) // 4
        for row in rows:
            self.args += row
        return [off, len(items)]


def _pad(n: int) -> int:
    return -n % schema.ALIGN


def _assemble(blobs: dict[str, bytes]) -> bytes:
    tags = [s.tag for s in schema.SECTIONS]
    pos = schema.HEADER_SIZE + schema.SECTION_ENTRY_SIZE * len(tags)
    pos += _pad(pos)
    entries = []
    for tag in tags:
        entries.append((schema.tag_value(tag), 0, pos, len(blobs[tag])))
        pos += len(blobs[tag]) + _pad(len(blobs[tag]))
    out = bytearray(struct.pack(schema.HEADER.fmt, schema.tag_value(schema.MAGIC.decode()),
                                *schema.VERSION, len(tags), pos))
    for entry in entries:
        out += struct.pack(schema.SECTION_ENTRY.fmt, *entry)
    out += bytes(_pad(len(out)))
    for tag in tags:
        out += blobs[tag] + bytes(_pad(len(blobs[tag])))
    return bytes(out)
