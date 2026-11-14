"""The harvest → bundle mapping, on a harvest shaped like Ren'Py 7.0's real
output (field shapes copied from Jisei's harvest)."""
import pytest

from witch.bundle.reader import Bundle
from witch.bundle.schema import NONE
from witch.renpy.graph import build, source_path
from witch.verify import verify

FILE = "C:\\Users\\dev\\vn/game/script.rpy"


def node(cls, fields, next=None, name=None, line=1):
    return {"class": cls, "name": name or f"{FILE}|1|{line}", "file": FILE, "line": line, "next": next,
            "fields": fields}


def harvest():
    nodes = [
        # 0
        node("Label", {"block": {"block": [1]}, "parameters": None, "hide": False}, next=1, name="start"),
        # 1: narration
        node("Say", {"who": None, "who_fast": False, "what": "Rain.", "with_": None, "interact": True,
                     "attributes": None, "arguments": None}, next=2, line=2),
        # 2
        node("Show", {"imspec": [["eileen", "happy"], None, None, [{"expr": "left"}], None, None, []],
                      "atl": {"object": "RawBlock"}}, next=3, line=3),
        # 3
        node("Say", {"who": "e", "who_fast": True, "what": "Hi [name].", "with_": {"expr": "dissolve"},
                     "interact": True, "attributes": ["happy"], "arguments": None}, next=4, line=4),
        # 4: Ren'Py 7.0 menus hold plain-string conditions and None for captions
        node("Menu", {"items": [["Pick:", "True", None], ["Go", "points > 1", {"block": [5]}],
                                ["Stay", "True", {"block": [6]}]], "set": None, "with_": None}, line=5),
        # 5
        node("Jump", {"target": {"expr": "\"ending\""}, "expression": True}, line=6),
        # 6
        node("Call", {"label": "helper", "expression": False, "arguments": {
            "arguments": [[None, {"expr": "1"}], ["mood", {"expr": "\"sad\""}]], "extrapos": None,
            "extrakw": None}}, next=7, line=7),
        # 7
        node("If", {"entries": [[{"expr": "seen"}, {"block": [8]}], [{"expr": "True"}, {"block": [9]}]]},
             line=8),
        # 8
        node("UserStatement", {"line": "play music \"a.ogg\"", "parsed": [["play", "music"], {}], "block": [],
                               "code_block": None, "translatable": False}, line=9),
        # 9
        node("Scene", {"imspec": None, "layer": "master", "atl": None}, line=10),
        # 10
        node("Label", {"block": {"block": [11]}, "parameters": {
            "parameters": [["n", None], ["mood", {"expr": "\"ok\""}]], "extrapos": "args", "extrakw": None},
            "hide": False}, next=11, name="helper", line=11),
        # 11
        node("Python", {"code": {"code": "x = 1", "mode": "hide"}, "hide": True, "store": "store"}, next=12,
             line=12),
        # 12
        node("Return", {"expression": None}, line=13),
        # 13
        node("Label", {"block": {"block": [14]}, "parameters": None, "hide": False}, next=14, name="ending",
             line=14),
        # 14
        node("Translate", {"identifier": "ending_0a1b", "language": None, "block": {"block": [15]},
                           "alternate": None, "after": {"node": 16}}, next=15, line=15),
        # 15
        node("Say", {"who": None, "what": "The end.", "with_": None, "interact": True, "attributes": None,
                     "arguments": None}, next=16, line=15),
        # 16
        node("EndTranslate", {}, line=15),
        # 17: init-time, unreachable
        node("Init", {"priority": -5, "block": {"block": [18]}}, line=20),
        # 18
        node("Define", {"varname": "e", "code": {"code": "Character(\"Eileen\")", "mode": "eval"},
                        "store": "store"}, line=21),
        # 19
        node("Testcase2000", {}, line=22),
    ]
    return {
        "renpy_version": "Ren'Py 7.0.0.196",
        "nodes": nodes,
        "labels": {"start": 0, "helper": 10, "ending": 13},
        "images": {"eileen happy": {"class": "Image", "file": "eileen happy.png"}},
        "named_nodes": len(nodes),
        "named_outside_graph": 0,
    }


@pytest.fixture(scope="module")
def bundle():
    return Bundle(build(harvest()).write())


def test_every_node_keeps_its_index_name_and_location(bundle):
    h = harvest()
    assert bundle.count("NODE") == len(h["nodes"])
    for i, n in enumerate(h["nodes"]):
        assert bundle.node_name(i) == n["name"]
        assert bundle.node_loc(i) == ("game/script.rpy", n["line"])
        assert bundle.node(i).next == (NONE if n["next"] is None else n["next"])


def test_say(bundle):
    narration, line = bundle.node(1), bundle.node(3)
    assert narration.fields["who"] == NONE and narration.flags == {"interact"}
    assert bundle.code(line.fields["who"]) == ("e", "eval")
    assert line.fields["attributes"] == ["happy"]
    assert bundle.code(line.fields["with"]) == ("dissolve", "eval")


def test_show_keeps_its_imspec_and_flags_atl(bundle):
    show = bundle.node(2)
    assert show.flags == {"atl"}
    assert show.fields["name"] == ["eileen", "happy"]
    assert [bundle.code(a)[0] for a in show.fields["at"]] == ["left"]
    assert show.fields["expression"] == NONE
    scene = bundle.node(9)
    assert scene.fields["name"] == [] and scene.fields["layer"] == "master"


def test_menu_captions_and_conditions(bundle):
    items = bundle.node(4).fields["items"]
    assert [i["label"] for i in items] == ["Pick:", "Go", "Stay"]
    assert items[0]["block"] == NONE
    assert items[1]["block"] == 5
    assert bundle.code(items[1]["condition"]) == ("points > 1", "eval")


def test_jumps_calls_and_parameters(bundle):
    jump = bundle.node(5)
    assert jump.kind.name == "jump_expression"
    assert bundle.code(jump.fields["target"]) == ('"ending"', "eval")
    call = bundle.node(6)
    assert call.fields["label"] == "helper"
    assert bundle.code(call.fields["arguments"]) == ('1, mood="sad"', "arguments")
    helper = bundle.node(10)
    assert bundle.code(helper.fields["parameters"]) == ('n, mood="ok", *args', "parameters")


def test_if_python_user_statement_translate(bundle):
    entries = bundle.node(7).fields["entries"]
    assert [e["block"] for e in entries] == [8, 9]
    python = bundle.node(11)
    assert python.flags == {"hide"} and bundle.code(python.fields["code"]) == ("x = 1", "hide")
    assert bundle.node(8).fields == {"name": "play music", "line": 'play music "a.ogg"'}
    translate = bundle.node(14)
    assert translate.fields == {"identifier": "ending_0a1b", "language": "", "block": 15}
    assert bundle.node(16).kind.name == "end_translate"


def test_init_time_statements_and_unknown_classes(bundle):
    init = bundle.node(17)
    assert init.fields == {"priority": -5, "block": 18}
    define = bundle.node(18).fields
    assert (define["varname"], define["operator"], define["index"]) == ("e", "=", NONE)
    unknown = bundle.node(19)
    assert unknown.kind.name == "unknown" and unknown.fields["classname"] == "Testcase2000"


def test_verifier_sees_the_graph_whole(bundle):
    report = verify(build(harvest()).write())
    codes = sorted((p.code, p.reach) for p in report.problems)
    # The ATL block and the not-yet-harvested image are known gaps; the
    # unknown class sits outside every label, so nothing reaches it.
    assert codes == [("atl-not-carried", "static"), ("unsupported-displayable", "static"),
                     ("unsupported-statement", "none")]


@pytest.mark.parametrize("path, expected", [
    ("C:\\Users\\dev\\vn/game/chance.rpy", "game/chance.rpy"),
    ("game/dialogue02.rpyc", "game/dialogue02.rpyc"),
    ("/home/tom/renpy/renpy/common/00start.rpy", "renpy/common/00start.rpy"),
    ("odd.rpy", "odd.rpy"),
])
def test_source_path(path, expected):
    assert source_path(path) == expected
