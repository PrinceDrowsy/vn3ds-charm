import struct

import pytest

from witch.bundle import schema
from witch.bundle.reader import Bundle, FormatError
from witch.bundle.schema import NONE
from witch.bundle.writer import Writer


def _script():
    w = Writer()
    cond = w.code("points > 2")
    start = w.node("label", {"name": "start"}, node_id="start", file="game/script.rpy", line=1)
    who = w.code("e")
    say = w.node("say", {"who": who, "what": "Hello, 世界", "attributes": ["happy"]}, node_id="say1", flags={"interact"})
    yes = w.node("jump", {"target": "good"})
    menu = w.node("menu", {"items": [
        {"label": "Pick one"},
        {"label": "Yes", "condition": cond, "block": yes},
    ]})
    good = w.node("label", {"name": "good"}, node_id="good")
    show = w.node("show", {"name": ["eileen", "happy"], "at": [w.code("left")], "layer": "master"})
    w.link(start, say, menu)
    w.link(good, show)
    w.label("start", start)
    w.label("good", good)
    return w, dict(start=start, say=say, menu=menu, yes=yes, cond=cond, good=good, show=show)


def test_round_trip_nodes_and_payloads():
    w, ids = _script()
    b = Bundle(w.write())

    say = b.node(ids["say"])
    assert say.kind.name == "say"
    assert say.flags == {"interact"}
    assert say.next == ids["menu"]
    assert say.fields["what"] == "Hello, 世界"
    assert say.fields["attributes"] == ["happy"]
    assert say.fields["temporary_attributes"] == []
    assert say.fields["with"] == NONE

    menu = b.node(ids["menu"]).fields["items"]
    assert menu[0] == {"label": "Pick one", "condition": NONE, "block": NONE, "arguments": NONE}
    assert menu[1]["block"] == ids["yes"]
    assert b.code(menu[1]["condition"]) == ("points > 2", "eval")

    show = b.node(ids["show"]).fields
    assert show["name"] == ["eileen", "happy"]
    assert b.code(show["at"][0])[0] == "left"
    assert b.node(ids["show"]).next == NONE

    assert b.node_name(ids["say"]) == "say1"
    assert b.node_loc(ids["start"]) == ("game/script.rpy", 1)
    assert b.labels() == [("good", ids["good"]), ("start", ids["start"])]


def test_assets_are_sorted_by_path_and_references_follow():
    w = Writer()
    z = w.asset("images/z.png", b"zz", width=2, height=1)
    a = w.asset("images/a.png", b"a")
    w.image("zed", w.disp("image", {"asset": z}))
    w.image("ay", w.disp("image", {"asset": a}))
    b = Bundle(w.write())

    assert [b.asset(i).path for i in range(b.count("ASST"))] == ["images/a.png", "images/z.png"]
    images = dict(b.images())
    zed = b.asset(b.disp(images["zed"]).fields["asset"])
    assert zed.path == "images/z.png" and (zed.width, zed.height) == (2, 1)
    assert b.asset_data(zed) == b"zz"


def test_strings_are_shared():
    w = Writer()
    w.link(w.node("jump", {"target": "x"}), w.node("jump", {"target": "x"}))
    w.label("x", 0)
    data = w.write()
    assert data.count(b"x\0") == 1


def test_sections_are_aligned_and_size_matches():
    w, _ = _script()
    data = w.write()
    _, _, _, count, size = struct.unpack_from(schema.HEADER.fmt, data)
    assert size == len(data)
    for i in range(count):
        _, _, off, _ = struct.unpack_from(schema.SECTION_ENTRY.fmt, data, 16 + 16 * i)
        assert off % schema.ALIGN == 0


def test_writer_rejects_unknown_fields():
    w = Writer()
    w.node("jump", {"tagret": "x"})
    with pytest.raises(TypeError, match="tagret"):
        w.write()


def _patch(data: bytes, offset: int, fmt: str, *values) -> bytes:
    out = bytearray(data)
    struct.pack_into(fmt, out, offset, *values)
    return bytes(out)


def _section_offset(data: bytes, tag: str) -> int:
    _, _, _, count, _ = struct.unpack_from(schema.HEADER.fmt, data)
    for i in range(count):
        t, _, off, _ = struct.unpack_from(schema.SECTION_ENTRY.fmt, data, 16 + 16 * i)
        if t == schema.tag_value(tag):
            return off
    raise KeyError(tag)


@pytest.mark.parametrize("damage, message", [
    (lambda d: b"NOPE" + d[4:], "not a .charm bundle"),
    (lambda d: _patch(d, 4, "<H", 1), r"format 1\.\d+;"),
    (lambda d: d[:-16], "header says"),
    (lambda d: d[:10], "too short"),
])
def test_header_damage_is_rejected(damage, message):
    w, _ = _script()
    with pytest.raises(FormatError, match=message) as e:
        Bundle(damage(w.write()))
    assert e.value.code == "bundle-header"


def test_unknown_node_kind_is_rejected():
    w, ids = _script()
    data = w.write()
    data = _patch(data, _section_offset(data, "NODE") + 12 * ids["say"], "<H", 999)
    with pytest.raises(FormatError, match="node kind 999") as e:
        Bundle(data).node(ids["say"])
    assert e.value.code == "unknown-kind"


def test_out_of_range_next_is_rejected():
    w, ids = _script()
    data = w.write()
    data = _patch(data, _section_offset(data, "NODE") + 12 * ids["say"] + 4, "<I", 5000)
    with pytest.raises(FormatError, match="NODE index 5000") as e:
        Bundle(data).node(ids["say"])
    assert e.value.code == "bad-reference"


def test_string_offset_inside_a_string_is_rejected():
    w, ids = _script()
    data = w.write()
    name_off = _section_offset(data, "NAME") + 4 * ids["say"]
    (off,) = struct.unpack_from("<I", data, name_off)
    data = _patch(data, name_off, "<I", off + 1)
    with pytest.raises(FormatError, match="isn't the start") as e:
        Bundle(data).node_name(ids["say"])
    assert e.value.code == "bad-string"
