"""R0's exit fixtures: every crash class the 2026-11 audit found in the old
bundles has to fail verification here with the right problem."""
import json
import struct

from witch.__main__ import main
from witch.bundle import schema
from witch.bundle.writer import Writer
from witch.verify import verify


def _game(w: Writer | None = None) -> Writer:
    """A small valid game: start shows a character, says a line, offers a menu."""
    w = w or Writer()
    eileen = w.asset("images/eileen happy.png", b"png", width=10, height=20)
    w.image("eileen happy", w.disp("image", {"asset": eileen}))
    start = w.node("label", {"name": "start"}, node_id="start", file="game/script.rpy", line=1)
    show = w.node("show", {"name": ["eileen", "happy"]}, file="game/script.rpy", line=2)
    say = w.node("say", {"what": "Hi."}, file="game/script.rpy", line=3, flags={"interact"})
    left = w.node("jump", {"target": "ending"}, file="game/script.rpy", line=5)
    menu = w.node("menu", {"items": [{"label": "Leave", "block": left}]}, file="game/script.rpy", line=4)
    ending = w.node("label", {"name": "ending"}, node_id="ending", file="game/script.rpy", line=7)
    ret = w.node("return", file="game/script.rpy", line=8)
    w.link(start, show, say, menu)
    w.link(ending, ret)
    w.label("start", start)
    w.label("ending", ending)
    return w


def _codes(report, gating_only=True):
    return [p.code for p in report.problems if p.gates or not gating_only]


def test_a_clean_game_passes():
    report = verify(_game().write())
    assert report.problems == []
    assert not report.failed


def test_jump_to_missing_label_fails():
    # Cooking Companions: 203 jumps to labels the old parser dropped.
    w = _game()
    lost = w.node("label", {"name": "side"}, node_id="lost", file="game/side.rpy", line=1)
    jump = w.node("jump", {"target": "named_menu"}, file="game/side.rpy", line=2)
    w.link(lost, jump)
    w.label("side", lost)
    report = verify(w.write())
    assert report.failed
    [p] = report.problems
    assert (p.code, p.severity, p.file, p.line) == ("missing-label", "crash", "game/side.rpy", 2)
    assert p.reach == "dynamic"  # `side` isn't jumped to statically, but Python could


def test_statement_the_engine_cant_run_fails():
    # Mice Tea: all 219 transitions were silently skipped by the old engine.
    w = _game()
    start = w.node("label", {"name": "start2"}, node_id="s")
    odd = w.node("unknown", {"classname": "RPY"}, file="game/script.rpy", line=9)
    w.link(start, odd)
    w.label("start2", start)
    report = verify(w.write())
    assert report.failed
    assert _codes(report) == ["unsupported-statement"]


def test_kind_number_outside_the_format_fails():
    w = _game()
    data = bytearray(w.write())
    node_off = _section_offset(data, "NODE")
    struct.pack_into("<H", data, node_off + 12 * 1, 200)  # the show
    report = verify(bytes(data))
    assert report.failed
    assert _codes(report) == ["unknown-kind"]


def test_two_assets_with_one_path_fail():
    # Mice Tea: 46 different "Eyes Neutral.png" files collapsed into one.
    w = _game()
    other = w.asset("images/eileen sad.png", b"png2")
    w.image("eileen sad", w.disp("image", {"asset": other}))
    data = bytearray(w.write())
    asst = _section_offset(data, "ASST")
    first_path = struct.unpack_from("<I", data, asst)[0]
    struct.pack_into("<I", data, asst + schema.SECTION_BY_TAG["ASST"].record.size, first_path)
    report = verify(bytes(data))
    assert report.failed
    assert _codes(report) == ["duplicate-entry"]


def test_show_of_an_undefined_image_fails():
    w = Writer()
    start = w.node("label", {"name": "start"})
    show = w.node("show", {"name": ["lucy", "mad"]})
    w.link(start, show)
    w.label("start", start)
    report = verify(w.write())
    assert report.failed
    assert _codes(report) == ["missing-image"]


def test_menu_with_only_captions_is_stuck():
    w = Writer()
    start = w.node("label", {"name": "start"})
    menu = w.node("menu", {"items": [{"label": "Nothing to pick"}]})
    w.link(start, menu)
    w.label("start", start)
    [p] = verify(w.write()).problems
    assert (p.code, p.severity, p.reach) == ("menu-without-choices", "stuck", "static")


def test_missing_start_label_fails():
    w = Writer()
    w.label("intro", w.node("label", {"name": "intro"}))
    assert _codes(verify(w.write())) == ["missing-start"]


def test_unreachable_problems_are_listed_but_dont_fail():
    w = _game()
    w.node("jump", {"target": "nowhere"})  # no label leads here
    report = verify(w.write())
    [p] = report.problems
    assert (p.code, p.reach) == ("missing-label", "none")
    assert not report.failed


def test_image_of_unknown_displayable_is_reported_with_its_reach():
    w = _game()
    w.image("eileen odd", w.disp("unknown", {"classname": "Live2D"}))
    report = verify(w.write())
    [p] = report.problems
    assert (p.code, p.reach) == ("unsupported-displayable", "static")


def test_garbage_is_a_damaged_bundle():
    report = verify(b"not a bundle at all")
    assert report.failed
    assert _codes(report) == ["bundle-header"]


def test_cli_writes_reports_and_exits_nonzero_on_failure(tmp_path, capsys):
    w = _game()
    x = w.node("label", {"name": "x"})
    w.link(x, w.node("jump", {"target": "gone"}))
    w.label("x", x)
    bundle = tmp_path / "game.charm"
    bundle.write_bytes(w.write())

    assert main(["verify", str(bundle), "--report", str(tmp_path / "out")]) == 1
    data = json.loads((tmp_path / "out" / "problems.json").read_text(encoding="utf-8"))
    assert data["failed"] and data["problems"][0]["code"] == "missing-label"
    assert "FAILED" in (tmp_path / "out" / "problems.md").read_text(encoding="utf-8")
    assert "crash" in capsys.readouterr().out

    bundle.write_bytes(_game().write())
    assert main(["verify", str(bundle)]) == 0


def _section_offset(data, tag):
    _, _, _, count, _ = struct.unpack_from(schema.HEADER.fmt, data)
    for i in range(count):
        t, _, off, _ = struct.unpack_from(schema.SECTION_ENTRY.fmt, data, 16 + 16 * i)
        if t == schema.tag_value(tag):
            return off
    raise KeyError(tag)
