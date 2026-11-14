"""Records the shim produced against the records Ren'Py lowered to."""
from witch.python.compare import check, compare, differences, normalize


def solid(color, **style):
    return {"kind": "solid", "color": color,
            "style": {"style": ["default"], "name": None, "properties": [[[k, v] for k, v in style.items()]]}}


def test_same_records_match_whatever_order_their_unordered_parts_came_in():
    a = {"kind": "character", "who_args": {"dict": [["color", "#f00"], ["style", "say_label"]]},
         "style": {"style": ["default"], "name": None, "properties": [[["xpos", 1], ["ypos", 2]]]}}
    b = {"kind": "character", "who_args": {"dict": [["style", "say_label"], ["color", "#f00"]]},
         "style": {"style": ["default"], "name": None, "properties": [[["ypos", 2], ["xpos", 1]]]}}
    assert differences(normalize(a), normalize(b)) == []


def test_a_pixel_is_not_a_fraction_and_true_is_not_one():
    assert differences(1, 1.0) == [("", 1, 1.0)]
    assert differences(True, 1) == [("", True, 1)]
    assert differences(None, 0) == [("", None, 0)]


def test_floats_agree_within_the_last_place_only():
    assert differences(4.001249804748512, 4.001249804748511) == []
    assert differences(0.5, 0.5000001) == [("", 0.5, 0.5000001)]


def test_differences_name_where_records_part():
    found = differences(normalize(solid([255, 0, 0, 255])), normalize(solid([255, 0, 0, 128])))
    assert found == [(".color[3]", 255, 128)]
    assert differences({"kind": "null", "width": 0}, {"kind": "null"}) == [(".width", 0, "<absent>")]


def test_a_registry_compares_by_name():
    oracle = [[["bg", "room"], solid([0, 0, 0, 255])], [["eileen"], solid([1, 1, 1, 255])], [["only", "pc"], None]]
    ours = [[["eileen"], solid([1, 1, 1, 255])], [["bg", "room"], solid([0, 0, 9, 255])], [["only", "3ds"], None]]
    c = compare(oracle, ours)
    assert c.same == 1 and not c.matches
    assert c.different == {'["bg", "room"]': [(".color[2]", 0, 9)]}
    assert c.only_oracle == [["only", "pc"]] and c.only_ours == [["only", "3ds"]]


def test_check_compares_every_registry_of_a_harvest():
    harvest = {"records": {"images": [[["a"], solid([0, 0, 0, 255])]], "channels": []}}
    result = {"registries": {"images": [[["a"], solid([0, 0, 0, 255])]], "channels": [], "screens": {}}}
    found = check(harvest, result)
    assert sorted(found) == ["channels", "images"] and all(c.matches for c in found.values())
