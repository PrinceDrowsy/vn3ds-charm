"""Reads a `.charm` bundle, checking every offset and reference it follows."""
from __future__ import annotations

import struct
from dataclasses import dataclass

from . import schema
from .schema import NONE, Kind, List, Ref, Struct


class FormatError(Exception):
    """A bundle that doesn't match the schema. `code` names the kind of damage."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class Node:
    index: int
    kind: Kind
    flags: frozenset[str]
    next: int
    fields: dict


@dataclass
class Disp:
    index: int
    kind: Kind
    flags: frozenset[str]
    fields: dict


@dataclass
class Asset:
    index: int
    path: str
    type: str
    format: str
    offset: int
    size: int
    width: int
    height: int


_NODE_KINDS = {k.id: k for k in schema.NODE_KINDS}
_DISP_KINDS = {k.id: k for k in schema.DISP_KINDS}


class Bundle:
    def __init__(self, data: bytes):
        self.data = data
        if len(data) < schema.HEADER_SIZE:
            raise FormatError("bundle-header", "file is too short to be a bundle")
        magic, major, minor, count, size = struct.unpack_from(schema.HEADER.fmt, data)
        if magic != schema.tag_value(schema.MAGIC.decode()):
            raise FormatError("bundle-header", "not a .charm bundle")
        ours = schema.VERSION
        # Major version 0 promises no compatibility, so it has to match exactly.
        if major != ours[0] or minor > ours[1] or (major == 0 and minor != ours[1]):
            raise FormatError("bundle-header", f"format {major}.{minor}; this reader reads {ours[0]}.{ours[1]}")
        if size != len(data):
            raise FormatError("bundle-header", f"header says {size} bytes, file has {len(data)}")
        table_end = schema.HEADER_SIZE + schema.SECTION_ENTRY_SIZE * count
        if table_end > len(data):
            raise FormatError("bundle-header", "section table runs past the end of the file")

        self._sections: dict[str, memoryview] = {}
        view = memoryview(data)
        for i in range(count):
            tag_v, chunk, off, length = struct.unpack_from(
                schema.SECTION_ENTRY.fmt, data, schema.HEADER_SIZE + schema.SECTION_ENTRY_SIZE * i)
            tag = tag_v.to_bytes(4, "little").decode("ascii", "replace")
            section = schema.SECTION_BY_TAG.get(tag)
            if section is None:
                raise FormatError("bundle-section", f"unknown section {tag!r}")
            if chunk != 0:
                raise FormatError("bundle-section", f"{tag} chunk {chunk}: chunked sections aren't defined yet")
            if tag in self._sections:
                raise FormatError("bundle-section", f"section {tag} appears twice")
            if off < table_end or off + length > len(data):
                raise FormatError("bundle-section", f"section {tag} lies outside the file")
            unit = section.record.size if section.record else section.unit
            if length % unit:
                raise FormatError("bundle-section", f"section {tag} isn't a whole number of records")
            self._sections[tag] = view[off:off + length]
        missing = [s.tag for s in schema.SECTIONS if s.tag not in self._sections]
        if missing:
            raise FormatError("bundle-section", f"missing sections {missing}")
        self._strs = bytes(self._sections["STRS"])
        if not self._strs or self._strs[0] != 0 or self._strs[-1] != 0:
            raise FormatError("bundle-section", "string pool must start with \"\" and end with a NUL")

    def count(self, tag: str) -> int:
        section = schema.SECTION_BY_TAG[tag]
        return len(self._sections[tag]) // (section.record.size if section.record else section.unit)

    def _row(self, tag: str, i: int) -> tuple:
        record = schema.SECTION_BY_TAG[tag].record
        return struct.unpack_from(record.fmt, self._sections[tag], i * record.size)

    def string(self, off: int) -> str:
        strs = self._strs
        if off >= len(strs) or (off and strs[off - 1] != 0):
            raise FormatError("bad-string", f"string offset {off} isn't the start of a string")
        try:
            return strs[off:strs.index(0, off)].decode("utf-8")
        except UnicodeDecodeError as e:
            raise FormatError("bad-string", f"string at {off} isn't UTF-8") from e

    def _ref(self, ref: Ref, value: int):
        if ref.table == "STRS":
            return self.string(value)
        if value != NONE and value >= self.count(ref.table):
            raise FormatError("bad-reference", f"{ref.table} index {value} is out of range")
        return value

    def payload(self, st: Struct, word: int) -> dict:
        args = self._sections["ARGS"]
        if word * 4 + st.size > len(args):
            raise FormatError("bad-reference", f"{st.name} payload at word {word} runs past ARGS")
        raw = iter(struct.unpack_from(st.fmt, args, word * 4))
        fields = {}
        for fname, ftype in st.fields:
            if isinstance(ftype, List):
                fields[fname] = self._list(ftype, next(raw), next(raw))
            elif isinstance(ftype, Ref):
                fields[fname] = self._ref(ftype, next(raw))
            else:
                fields[fname] = next(raw)
        return fields

    def _list(self, ftype: List, word: int, count: int) -> list:
        elem = ftype.elem
        size = elem.size
        if word * 4 + count * size > len(self._sections["ARGS"]):
            raise FormatError("bad-reference", f"list at word {word} runs past ARGS")
        if isinstance(elem, Struct):
            return [self.payload(elem, word + i * size // 4) for i in range(count)]
        values = struct.unpack_from(f"<{count}{elem.fmt}", self._sections["ARGS"], word * 4)
        return [self._ref(elem, v) for v in values] if isinstance(elem, Ref) else list(values)

    def _kind(self, kinds: dict[int, Kind], kind_id: int, flags: int, what: str) -> tuple[Kind, frozenset[str]]:
        kind = kinds.get(kind_id)
        if kind is None:
            raise FormatError("unknown-kind", f"{what} kind {kind_id} isn't in format {schema.VERSION[0]}.{schema.VERSION[1]}")
        if flags >> len(kind.flags):
            raise FormatError("bad-flags", f"{what} {kind.name} has undefined flag bits {flags:#x}")
        return kind, frozenset(f for bit, f in enumerate(kind.flags) if flags & (1 << bit))

    def node(self, i: int) -> Node:
        kind_id, flags, nxt, args = self._row("NODE", i)
        kind, flag_set = self._kind(_NODE_KINDS, kind_id, flags, "node")
        fields = self.payload(kind.payload, args) if kind.payload else {}
        return Node(i, kind, flag_set, self._ref(schema.NODE, nxt), fields)

    def node_name(self, i: int) -> str:
        return self.string(self._row("NAME", i)[0])

    def node_loc(self, i: int) -> tuple[str, int]:
        file, line = self._row("LOCS", i)
        return self.string(file), line

    def disp(self, i: int) -> Disp:
        kind_id, flags, args = self._row("DISP", i)
        kind, flag_set = self._kind(_DISP_KINDS, kind_id, flags, "displayable")
        fields = self.payload(kind.payload, args) if kind.payload else {}
        return Disp(i, kind, flag_set, fields)

    def labels(self) -> list[tuple[str, int]]:
        return [(self.string(n), self._ref(schema.NODE, node)) for n, node in
                (self._row("LABL", i) for i in range(self.count("LABL")))]

    def images(self) -> list[tuple[str, int]]:
        return [(self.string(n), self._ref(schema.DISP, d)) for n, d in
                (self._row("IMGS", i) for i in range(self.count("IMGS")))]

    def code(self, i: int) -> tuple[str, str]:
        source, mode, _, _ = self._row("CODE", i)
        if mode >= len(schema.CODE_MODE.members):
            raise FormatError("bad-reference", f"code {i} has an undefined mode")
        return self.string(source), schema.CODE_MODE.members[mode]

    def asset(self, i: int) -> Asset:
        path, type_, fmt, off, size, w, h = self._row("ASST", i)
        if off + size > len(self._sections["DATA"]):
            raise FormatError("bad-reference", f"asset {i}'s data runs past DATA")
        if type_ >= len(schema.ASSET_TYPE.members) or fmt >= len(schema.ASSET_FORMAT.members):
            raise FormatError("bad-reference", f"asset {i} has an undefined type or format")
        return Asset(i, self.string(path), schema.ASSET_TYPE.members[type_],
                     schema.ASSET_FORMAT.members[fmt], off, size, w, h)

    def asset_data(self, asset: Asset) -> bytes:
        return bytes(self._sections["DATA"][asset.offset:asset.offset + asset.size])
