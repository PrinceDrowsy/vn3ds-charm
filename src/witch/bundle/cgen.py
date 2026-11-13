"""Generates Enchantment's `charm_schema.h` from the schema.

Run `python -m witch.bundle.cgen` after changing schema.py; a test fails while
the committed header is out of date.
"""
from __future__ import annotations

from pathlib import Path

from . import schema
from .schema import Kind, List, Ref, Struct

HEADER_PATH = Path(__file__).resolve().parents[2] / "enchantment" / "include" / "charm_schema.h"


def _comment(t) -> str:
    if isinstance(t, Ref):
        return f" /* {t.table} */"
    if isinstance(t, List):
        elem = t.elem
        name = f"charm_{elem.name}" if isinstance(elem, Struct) else elem.table if isinstance(elem, Ref) else elem.name
        return f" /* of {name} */"
    return ""


def _structs() -> list[Struct]:
    """Every struct the format uses, dependencies first."""
    seen: dict[str, Struct] = {}

    def visit(st: Struct):
        for _, ftype in st.fields:
            if isinstance(ftype, List) and isinstance(ftype.elem, Struct):
                visit(ftype.elem)
        if st.name in seen and seen[st.name] is not st:
            raise ValueError(f"two different structs are named {st.name}")
        seen[st.name] = st

    for st in (schema.HEADER, schema.SECTION_ENTRY):
        visit(st)
    for section in schema.SECTIONS:
        if section.record:
            visit(section.record)
    for kind in schema.NODE_KINDS + schema.DISP_KINDS:
        if kind.payload:
            visit(kind.payload)
    return list(seen.values())


def _enum(prefix: str, names: list[tuple[str, int]], count_name: str) -> list[str]:
    lines = [f"enum charm_{prefix} {{"]
    lines += [f"    CHARM_{prefix.upper()}_{name.upper()} = {value}," for name, value in names]
    lines.append("};")
    lines.append(f"#define {count_name} {max(v for _, v in names) + 1}")
    return lines


def _kinds(prefix: str, kinds: tuple[Kind, ...]) -> list[str]:
    lines = _enum(f"{prefix}_kind", [(k.name, k.id) for k in kinds], f"CHARM_{prefix.upper()}_KIND_COUNT")
    for k in kinds:
        for bit, flag in enumerate(k.flags):
            lines.append(f"#define CHARM_{k.name.upper()}_{flag.upper()} (1u << {bit})")
    by_id = {k.id: k.name for k in kinds}
    names = ", ".join(f'"{by_id.get(i, "")}"' for i in range(max(by_id) + 1))
    lines.append(f"static const char *const charm_{prefix}_kind_names[] = {{{names}}};")
    return lines


def generate() -> str:
    out = [
        "/* Generated from src/witch/bundle/schema.py by `python -m witch.bundle.cgen`. Do not edit. */",
        "#ifndef CHARM_SCHEMA_H",
        "#define CHARM_SCHEMA_H",
        "",
        "#include <stddef.h>",
        "#include <stdint.h>",
        "",
        f"#define CHARM_VERSION_MAJOR {schema.VERSION[0]}",
        f"#define CHARM_VERSION_MINOR {schema.VERSION[1]}",
        f"#define CHARM_MAGIC {schema.tag_value(schema.MAGIC.decode()):#010x}u",
        f"#define CHARM_NONE {schema.NONE:#010x}u",
        f"#define CHARM_ALIGN {schema.ALIGN}",
        "",
    ]
    out += [f"#define CHARM_TAG_{s.tag} {schema.tag_value(s.tag):#010x}u" for s in schema.SECTIONS]
    out += ["", "typedef struct { uint32_t offset; uint32_t count; } charm_list; /* words into ARGS */", ""]

    out += _kinds("node", schema.NODE_KINDS) + [""]
    out += _kinds("disp", schema.DISP_KINDS) + [""]
    for enum in schema.ENUMS:
        out += _enum(enum.name, [(m, i) for i, m in enumerate(enum.members)],
                     f"CHARM_{enum.name.upper()}_COUNT") + [""]

    structs = _structs()
    for st in structs:
        out.append("typedef struct {")
        out += [f"    {t.ctype} {name};{_comment(t)}" for name, t in st.fields]
        out.append(f"}} charm_{st.name};")
    out.append("")
    for st in structs:
        out.append(f'_Static_assert(sizeof(charm_{st.name}) == {st.size}, "charm_{st.name} size");')
        out += [f'_Static_assert(offsetof(charm_{st.name}, {name}) == {st.offsets[name]}, "charm_{st.name}.{name}");'
                for name, _ in st.fields]
    out += ["", "#endif", ""]
    return "\n".join(out)


if __name__ == "__main__":
    HEADER_PATH.parent.mkdir(parents=True, exist_ok=True)
    HEADER_PATH.write_text(generate(), encoding="utf-8", newline="\n")
    print(f"wrote {HEADER_PATH}")
