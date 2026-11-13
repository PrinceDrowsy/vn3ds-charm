import json

from converter.emitters import FlaggedItems
from converter.parser import SourceLocation
from converter.problem_report import build_problem_report, emit_problems_json, format_report_table, has_blocking

LOC = SourceLocation("game.rpy", 42)


def _flagged_with(reason: str, text: str = "some source line") -> FlaggedItems:
    flagged = FlaggedItems()
    flagged.add(text=text, reason=reason, loc=LOC)
    return flagged


def test_scene_position_is_approximated_not_blocking():
    report = build_problem_report("Test Game", "0.1.0", _flagged_with("scene position has no VNDS equivalent"))
    item = report["items"][0]
    assert item["severity"] == "approximated"
    assert item["category"] == "asset"


def test_unsupported_screen_is_manual_category_screen_but_still_blocking():
    flagged = _flagged_with("unsupported statement", text="screen main_menu():")
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["category"] == "screen"
    # generic "unsupported statement" rule is blocking regardless of keyword sniff
    assert item["severity"] == "blocking"


def test_unsupported_if_block_sniffed_as_flow_category():
    flagged = _flagged_with("unsupported top-level statement", text="if some_condition:")
    report = build_problem_report("Test Game", "0.1.0", flagged)
    assert report["items"][0]["category"] == "flow"


def test_day_card_and_the_end_card_are_approximated_not_blocking():
    # regression: these new reasons didn't match any classify.py rule at
    # first, so they silently fell back to "blocking" -- the exact
    # opposite of the intended "approximated" (a real, working title card,
    # just not pixel-perfect to the PC version).
    for reason in ("title-card visual style approximated", "end-card visual style approximated"):
        report = build_problem_report("Test Game", "0.1.0", _flagged_with(reason))
        item = report["items"][0]
        assert item["severity"] == "approximated"
        assert item["category"] == "screen"


def test_subchapter_backing_image_is_approximated_not_blocking():
    report = build_problem_report("Test Game", "0.1.0", _flagged_with("chapter-heading backing image not reproduced"))
    item = report["items"][0]
    assert item["severity"] == "approximated"
    assert item["category"] == "screen"


def test_placeholder_rollback_gap_is_approximated_flow():
    report = build_problem_report("Test Game", "0.1.0", _flagged_with("renpy.rollback() has no VNDS equivalent"))
    item = report["items"][0]
    assert item["severity"] == "approximated"
    assert item["category"] == "flow"


def test_character_image_bailout_and_missing_layer_are_approximated_not_blocking():
    # regression: these new emitter reasons (vnds_writer.py's
    # _emit_character_image_show) didn't match any classify.py rule at
    # first, so a real Mice Tea conversion run saw blocking jump from 556
    # to 933 -- the exact same "new reason string falls through to the
    # blocking default" bug the day/subchapter/the_end reasons hit before.
    for reason in (
        "CharacterImage layer_selector for 'margaret' couldn't be resolved for these attributes "
        "(unsupported method call: .lower(...)); falling back to its default (no-attribute) pose",
        "CharacterImage layer 'lighting_night' has no resolvable per-character asset file",
    ):
        report = build_problem_report("Test Game", "0.1.0", _flagged_with(reason))
        item = report["items"][0]
        assert item["severity"] == "approximated"
        assert item["category"] == "displayable"


def test_unknown_text_tag_is_approximated_text_tag_category():
    flagged = _flagged_with("unknown text tag {shake} stripped", text="{shake}")
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "approximated"
    assert item["category"] == "text-tag"


def test_size_and_font_tag_is_approximated_text_tag_not_blocking():
    # regression: the reason string starts with "unsupported text tag "
    # (distinct from the generic "unknown text tag " rule's prefix), which
    # must have its own classify.py rule or it silently falls through to
    # the default blocking classification.
    flagged = _flagged_with(
        "unsupported text tag {size=30} stripped (no per-run font-size/font-file support)",
        text="{size=30}",
    )
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "approximated"
    assert item["category"] == "text-tag"


def test_downgraded_transition_is_approximated_atl():
    flagged = _flagged_with(
        "transition 'wipeleft' downgraded to a plain dissolve (only dissolve/fade have a known duration)",
        text="with wipeleft",
    )
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "approximated"
    assert item["category"] == "atl"


def test_keyframe_fallback_atl_animation_is_approximated_not_blocking():
    # regression: this reason string is emitted by the new Phase 3.1 ATL
    # animation matcher for its general keyframe fallback (a real,
    # working animation, just not an exact preset match) -- it must not
    # fall through to classify.py's generic "blocking" default.
    flagged = _flagged_with(
        "ATL animation approximated to a generic keyframe sequence (no exact preset match)",
        text="show death",
    )
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "approximated"
    assert item["category"] == "atl"


def test_unsupported_custom_screen_construct_is_manual():
    flagged = _flagged_with(
        "custom screen uses constructs outside the supported subset (vbox/hbox, text, textbutton, if/elif/else) — needs native reimplementation",
        text="screen save_slots:",
    )
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "manual"
    assert item["category"] == "screen"


def test_dropped_imagemap_hotspot_is_approximated_screen():
    flagged = _flagged_with(
        "imagemap hotspot uses an unsupported action, this hotspot dropped",
        text='hotspot (300, 300, 10, 10) action Function(foo)',
    )
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "approximated"
    assert item["category"] == "screen"


def test_queue_approximation_is_approximated_audio():
    flagged = _flagged_with("queue approximated as an immediate play (no track-chaining support yet)")
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "approximated"
    assert item["category"] == "audio"


def test_bare_pause_is_info_not_blocking():
    flagged = _flagged_with("bare pause has no effect; VNDS already waits for input after each text line")
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "info"


def test_persistent_achievement_is_manual_not_blocking():
    flagged = _flagged_with(
        "persistent/achievement API has no VNDS equivalent (needs native reimplementation)",
        text="$ persistent.naoki = True",
    )
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "manual"


def test_default_renpy_screen_is_info_not_blocking():
    flagged = _flagged_with(
        "default Ren'Py screen already provided natively by the engine, no action needed",
        text="screen say(who, what):",
    )
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "info"
    assert item["category"] == "screen"


def test_custom_screen_is_manual_not_blocking():
    flagged = _flagged_with(
        "custom screen has no VNDS equivalent (needs native reimplementation)",
        text="screen notes:",
    )
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "manual"
    assert item["category"] == "screen"


def test_block_rollback_and_bare_var_are_info_flow():
    for reason in (
        "renpy.block_rollback() is a no-op (rollback isn't implemented yet)",
        "bare variable reference has no effect, treated as a no-op",
    ):
        report = build_problem_report("Test Game", "0.1.0", _flagged_with(reason))
        item = report["items"][0]
        assert item["severity"] == "info"
        assert item["category"] == "flow"


def test_with_none_is_info_atl_not_blocking():
    flagged = _flagged_with("with None has no effect, treated as a no-op")
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "info"
    assert item["category"] == "atl"


def test_movie_cutscene_is_manual_video():
    flagged = _flagged_with("movie/video playback has no VNDS equivalent (needs native reimplementation)")
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "manual"
    assert item["category"] == "video"


def test_custom_transition_definition_is_approximated_atl():
    flagged = _flagged_with(
        "custom transition definition has no VNDS equivalent (any use already downgrades to a plain dissolve)"
    )
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "approximated"
    assert item["category"] == "atl"


def test_unrecognized_reason_falls_back_to_blocking_unknown():
    flagged = _flagged_with("some brand new reason nothing matches", text="???")
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "blocking"
    assert item["category"] == "unknown"
    assert item["message"] == "some brand new reason nothing matches"


def test_long_source_snippet_is_truncated():
    long_text = "x" * 200
    flagged = _flagged_with("unsupported statement", text=long_text)
    report = build_problem_report("Test Game", "0.1.0", flagged)
    assert len(report["items"][0]["ren_py"]) <= 80
    assert report["items"][0]["ren_py"].endswith("…")


def test_summary_counts_match_items_and_total():
    flagged = FlaggedItems()
    flagged.add(text="a", reason="scene position has no VNDS equivalent", loc=LOC)
    flagged.add(text="b", reason="unsupported statement", loc=LOC)
    flagged.add(text="c", reason="unsupported statement", loc=LOC)
    report = build_problem_report("Test Game", "0.1.0", flagged)

    assert report["summary"]["total"] == 3
    assert report["summary"]["approximated"] == 1
    assert report["summary"]["blocking"] == 2
    assert report["summary"]["manual"] == 0
    assert report["summary"]["info"] == 0
    assert len(report["items"]) == report["summary"]["total"]


def test_fully_convertible_game_has_zero_total():
    report = build_problem_report("Test Game", "0.1.0", FlaggedItems())
    assert report["summary"]["total"] == 0
    assert not has_blocking(report)


def test_has_blocking_true_when_any_blocking_item_present():
    report = build_problem_report("Test Game", "0.1.0", _flagged_with("unsupported statement"))
    assert has_blocking(report)


def test_emit_problems_json_is_valid_sorted_json():
    report = build_problem_report("Test Game", "0.1.0", _flagged_with("unsupported statement"))
    text = emit_problems_json(report)
    parsed = json.loads(text)
    assert parsed == report
    # sort_keys=True -> "converter_version" before "game" before "generated" before "items" before "summary"
    assert text.index('"converter_version"') < text.index('"game"') < text.index('"generated"')


def test_format_report_table_contains_key_fields():
    report = build_problem_report("Test Game", "0.1.0", _flagged_with("unsupported statement", text="if x:"))
    table = format_report_table(report)
    assert "Test Game" in table
    assert "P0001" in table
    assert "BLOCKING" in table
    assert "game.rpy:42" in table


def test_translate_block_is_info_not_blocking():
    flagged = _flagged_with(
        "translate block is localization data, not game content",
        text="translate french strings:",
    )
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "info"


def test_bare_python_block_is_manual_not_blocking():
    flagged = _flagged_with(
        "python block has no VNDS equivalent (needs native reimplementation, if needed at all)",
        text="python:",
    )
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "manual"


def test_custom_audio_channel_is_info_not_blocking():
    flagged = _flagged_with(
        "custom audio channel not in the converter's known/verified set ('secondary'); behavior (loop=True, mixer=music) was inferred from the name",
        text="play secondary track.ogg",
    )
    report = build_problem_report("Test Game", "0.1.0", flagged)
    item = report["items"][0]
    assert item["severity"] == "info"
    assert item["category"] == "audio"
