from pathlib import Path

from converter.parser import Menu, Say, Scene, Show, parse_rpy

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_full.rpy"


def test_sample_full_parses_end_to_end():
    source = FIXTURE.read_text(encoding="utf-8")
    script, problems = parse_rpy(source, filename=str(FIXTURE))

    assert [label.name for label in script.labels] == [
        "start",
        "polite",
        "shy",
        "day1",
        "ending",
    ]
    assert script.characters["e"].display_name == "Eileen"

    # exactly one unsupported construct (the `if some_condition.attr:` block —
    # attribute access in a condition is outside the safe expression subset)
    assert len(problems) == 1
    assert "if some_condition.attr" in problems[0].text

    start = script.labels[0].body
    assert isinstance(start[0], Scene)
    assert isinstance(start[1], Show)
    assert isinstance(start[2], Say)
    assert isinstance(start[3], Menu)
    assert [c.text for c in start[3].choices] == ["Say hi.", "Stay quiet."]

    day1 = script.labels[3].body
    kinds = [type(node).__name__ for node in day1]
    assert kinds == ["Hide", "Unsupported", "Call", "Return"]
