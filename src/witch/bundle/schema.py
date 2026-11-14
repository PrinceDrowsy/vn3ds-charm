"""The `.charm` bundle schema (ADR-007).

The single declaration of the format: Witch's writer and reader are driven by
it, and Enchantment's C header is generated from it (`cgen.py`). Kind ids are
part of the format and must never be renumbered.
"""
from __future__ import annotations

from dataclasses import dataclass

VERSION = (0, 2)
MAGIC = b"CHRM"
NONE = 0xFFFFFFFF
HEADER_SIZE = 16
SECTION_ENTRY_SIZE = 16
ALIGN = 16


@dataclass(frozen=True)
class Scalar:
    name: str
    fmt: str
    ctype: str
    size: int


U16 = Scalar("u16", "H", "uint16_t", 2)
U32 = Scalar("u32", "I", "uint32_t", 4)
I32 = Scalar("i32", "i", "int32_t", 4)
F32 = Scalar("f32", "f", "float", 4)


@dataclass(frozen=True)
class Ref:
    """A u32 index into `table`, or for STRS a byte offset; NONE means none."""

    table: str
    fmt = "I"
    ctype = "uint32_t"
    size = 4


STR = Ref("STRS")
NODE = Ref("NODE")
CODE = Ref("CODE")
ASSET = Ref("ASST")
DISP = Ref("DISP")


@dataclass(frozen=True)
class List:
    """A (word offset into ARGS, count) pair; the elements sit there back to back."""

    elem: Scalar | Ref | Struct
    fmt = "II"
    ctype = "charm_list"
    size = 8


class Struct:
    def __init__(self, name: str, fields: list[tuple[str, Scalar | Ref | List]], *, words_only: bool = True):
        self.name = name
        self.fields = tuple(fields)
        self.offsets: dict[str, int] = {}
        pos = 0
        for fname, ftype in self.fields:
            if words_only and ftype.size % 4:
                raise ValueError(f"{name}.{fname}: payload fields must be whole words")
            if pos % min(ftype.size, 4):
                raise ValueError(f"{name}.{fname} is misaligned")
            self.offsets[fname] = pos
            pos += ftype.size
        if pos % 4:
            raise ValueError(f"{name} is not a whole number of words")
        self.size = pos
        self.fmt = "<" + "".join(t.fmt for _, t in self.fields)

    def __repr__(self) -> str:
        return f"Struct({self.name})"


@dataclass(frozen=True)
class Kind:
    id: int
    name: str
    payload: Struct | None = None
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Enum:
    name: str
    members: tuple[str, ...]

    def __getitem__(self, member: str) -> int:
        return self.members.index(member)


@dataclass(frozen=True)
class Section:
    tag: str
    record: Struct | None  # None: a byte pool, or with `unit` 4 a word pool
    unit: int = 1


# Ren'Py's imspec tuple, shared by show/scene/hide.
_IMSPEC = [
    ("name", List(STR)),
    ("expression", CODE),
    ("tag", STR),
    ("at", List(CODE)),
    ("layer", STR),
    ("zorder", CODE),
    ("behind", List(STR)),
]

MENU_ITEM = Struct("menu_item", [
    ("label", STR),
    ("condition", CODE),
    ("block", NODE),  # NONE for a caption
    ("arguments", CODE),
])

IF_ENTRY = Struct("if_entry", [
    ("condition", CODE),  # NONE for else
    ("block", NODE),
])

NODE_KINDS = (
    Kind(0, "unknown", Struct("unknown", [("classname", STR)])),
    Kind(1, "label", Struct("label", [("name", STR), ("parameters", CODE)])),
    Kind(2, "say", Struct("say", [
        ("who", CODE),
        ("what", STR),
        ("attributes", List(STR)),
        ("temporary_attributes", List(STR)),
        ("with", CODE),
        ("arguments", CODE),
        ("identifier", STR),
    ]), flags=("interact",)),
    # "atl": the statement has an ATL block, which isn't carried yet (R4).
    Kind(3, "show", Struct("show", _IMSPEC), flags=("atl",)),
    Kind(4, "scene", Struct("scene", _IMSPEC), flags=("atl",)),
    Kind(5, "hide", Struct("hide", _IMSPEC)),
    Kind(6, "with", Struct("with", [("expr", CODE), ("paired", CODE)])),
    Kind(7, "jump", Struct("jump", [("target", STR)])),
    Kind(8, "jump_expression", Struct("jump_expression", [("target", CODE)])),
    Kind(9, "call", Struct("call", [("label", STR), ("arguments", CODE)])),
    Kind(10, "call_expression", Struct("call_expression", [("label", CODE), ("arguments", CODE)])),
    Kind(11, "return", Struct("return", [("expression", CODE)])),
    Kind(12, "menu", Struct("menu", [
        ("items", List(MENU_ITEM)),
        ("set", CODE),
        ("with", CODE),
        ("arguments", CODE),
    ])),
    Kind(13, "if", Struct("if", [("entries", List(IF_ENTRY))])),
    Kind(14, "while", Struct("while", [("condition", CODE), ("block", NODE)])),
    Kind(15, "python", Struct("python", [("code", CODE), ("store", STR)]), flags=("hide",)),
    Kind(16, "pass"),
    Kind(17, "user_statement", Struct("user_statement", [("name", STR), ("line", STR)])),
    Kind(18, "translate", Struct("translate", [("identifier", STR), ("language", STR), ("block", NODE)])),
    Kind(19, "end_translate"),
    Kind(20, "show_layer", Struct("show_layer", [("layer", STR), ("at", List(CODE))]), flags=("atl",)),
    Kind(21, "camera", Struct("camera", [("layer", STR), ("at", List(CODE))]), flags=("atl",)),
    # Init-time statements. D18 runs them on the PC, but the graph keeps them
    # so node names and counts match Ren'Py's.
    Kind(22, "init", Struct("init", [("priority", I32), ("block", NODE)])),
    Kind(23, "early_python", Struct("early_python", [("code", CODE), ("store", STR)]), flags=("hide",)),
    Kind(24, "define", Struct("define", [
        ("store", STR),
        ("varname", STR),
        ("operator", STR),  # "=", or e.g. "+=" / "|=" on Ren'Py 8
        ("index", CODE),  # `define d["k"] = v` on Ren'Py 8
        ("code", CODE),
    ])),
    Kind(25, "default", Struct("default", [("store", STR), ("varname", STR), ("code", CODE)])),
    Kind(26, "image", Struct("image", [("name", List(STR)), ("code", CODE)]), flags=("atl",)),
    Kind(27, "transform", Struct("transform", [("store", STR), ("varname", STR), ("parameters", CODE)]),
         flags=("atl",)),
    Kind(28, "style", Struct("style", [("name", STR), ("parent", STR)])),
    Kind(29, "screen", Struct("screen", [("name", STR)])),
    Kind(30, "testcase", Struct("testcase", [("label", STR)])),
    Kind(31, "translate_string", Struct("translate_string", [("language", STR), ("old", STR), ("new", STR)])),
    Kind(32, "translate_python", Struct("translate_python", [("language", STR), ("code", CODE)])),
    Kind(33, "translate_block", Struct("translate_block", [("language", STR), ("block", NODE)]),
         flags=("early",)),
)

DISP_KINDS = (
    Kind(0, "unknown", Struct("disp_unknown", [("classname", STR)])),
    Kind(1, "image", Struct("disp_image", [("asset", ASSET)])),
)

ASSET_TYPE = Enum("asset_type", ("other", "image", "audio", "font", "video"))
# "source": the file's bytes as the game ships them; converted formats come with R4/R6.
ASSET_FORMAT = Enum("asset_format", ("source",))
# "parameters" is a def's parameter list (`a, b=1, *args`), "arguments" a
# call's argument list (`x, y=2`), each as Python source without parentheses.
CODE_MODE = Enum("code_mode", ("eval", "exec", "parameters", "arguments"))
ENUMS = (ASSET_TYPE, ASSET_FORMAT, CODE_MODE)

HEADER = Struct("header", [
    ("magic", U32),
    ("major", U16),
    ("minor", U16),
    ("section_count", U32),
    ("file_size", U32),
], words_only=False)

SECTION_ENTRY = Struct("section", [
    ("tag", U32),
    ("chunk", U32),
    ("offset", U32),
    ("size", U32),
])

NODE_RECORD = Struct("node", [
    ("kind", U16),
    ("flags", U16),
    ("next", NODE),
    ("args", U32),  # word offset of the payload in ARGS
], words_only=False)

DISP_RECORD = Struct("disp", [
    ("kind", U16),
    ("flags", U16),
    ("args", U32),
], words_only=False)

SECTIONS = (
    Section("STRS", None),
    Section("ARGS", None, unit=4),
    Section("NODE", NODE_RECORD),
    Section("NAME", Struct("node_name", [("name", STR)])),  # parallel to NODE
    Section("LOCS", Struct("node_loc", [("file", STR), ("line", U32)])),  # parallel to NODE
    Section("LABL", Struct("label_entry", [("name", STR), ("node", NODE)])),  # sorted by name
    Section("CODE", Struct("code", [
        ("source", STR),
        ("mode", U32),
        ("mpy", U32),  # byte offset in MPYB
        ("mpy_size", U32),
    ])),
    Section("MPYB", None),
    Section("ASST", Struct("asset", [
        ("path", STR),
        ("type", U32),
        ("format", U32),
        ("offset", U32),  # byte offset in DATA
        ("size", U32),
        ("width", U32),
        ("height", U32),
    ])),  # sorted by path
    Section("DATA", None),
    Section("IMGS", Struct("image_entry", [("name", STR), ("disp", DISP)])),  # sorted by name
    Section("DISP", DISP_RECORD),
)

SECTION_BY_TAG = {s.tag: s for s in SECTIONS}
NODE_KIND_BY_NAME = {k.name: k for k in NODE_KINDS}
DISP_KIND_BY_NAME = {k.name: k for k in DISP_KINDS}


def tag_value(tag: str) -> int:
    """A section tag as the little-endian u32 it is stored as."""
    return int.from_bytes(tag.encode("ascii"), "little")
