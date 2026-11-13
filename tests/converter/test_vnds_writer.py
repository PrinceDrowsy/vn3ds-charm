from converter.parser import (
    AnimSpec,
    CharacterDef,
    DayCard,
    Hide,
    If,
    IfBranch,
    Jump,
    Label,
    Menu,
    MenuChoice,
    Pause,
    Placeholder,
    Play,
    PortraitDef,
    Return,
    ResetAudio,
    Say,
    Scene,
    ScreenBox,
    ScreenButton,
    ScreenDef,
    ScreenHotspot,
    ScreenIf,
    ScreenIfBranch,
    ScreenImagemap,
    ScreenText,
    Set,
    SetVolume,
    Show,
    SourceLocation,
    SpriteLayerCategories,
    Stop,
    SubchapterCard,
    SubchapterHide,
    TheEndCard,
    Transition,
    While,
    Window,
    parse_character_image_declarations,
    parse_rpy,
)
from converter.emitters import emit_script_vnds

LOC = SourceLocation("test.rpy", 1)


def _say(who, what):
    return Say(who=who, what=what, loc=LOC)


def test_basic_flow_emits_labels_and_commands():
    labels = [
        ("start", [_say(None, "Hello."), Jump(target="next", loc=LOC)]),
        ("next", [Return(loc=LOC)]),
    ]
    text, flagged = emit_script_vnds(labels, characters={})
    assert flagged.items == []
    assert text == (
        "@start\n"
        "nameplate ~\n"
        "text Hello.\n"
        "jump next\n"
        "\n"
        "@next\n"
        "return\n"
    )


def test_say_resolves_character_display_name_as_nameplate():
    # Character(color=...) (VN3DS-spec.md §6) rides as a "#hexcolor" token
    # right before the name -- previously parsed and stored, never emitted,
    # so every nameplate rendered in the engine's own default color
    # regardless of the character's real per-character tint.
    characters = {"e": CharacterDef(varname="e", display_name="Eileen", color="#c8ffc8", loc=LOC)}
    labels = [("start", [_say("e", "Hi there.")])]
    text, _flagged = emit_script_vnds(labels, characters)
    assert "nameplate #c8ffc8 Eileen\n" in text
    assert "text Hi there.\n" in text


def test_say_with_no_character_color_omits_the_color_token():
    characters = {"e": CharacterDef(varname="e", display_name="Eileen", color=None, loc=LOC)}
    labels = [("start", [_say("e", "Hi there.")])]
    text, _flagged = emit_script_vnds(labels, characters)
    assert "nameplate Eileen\n" in text


def test_say_with_none_display_name_clears_nameplate():
    # Character(None, ...) is a valid nameless-narrator idiom -- must not
    # fall back to showing the literal variable name as a nameplate, but
    # (like any other narrator line) still needs to clear whatever
    # nameplate a preceding character line left showing.
    characters = {"narrator": CharacterDef(varname="narrator", display_name=None, color="#ffffff", loc=LOC)}
    labels = [("start", [_say("narrator", "Some text.")])]
    text, _flagged = emit_script_vnds(labels, characters)
    assert "nameplate ~\n" in text
    assert "nameplate narrator" not in text
    assert "text Some text.\n" in text


def test_say_with_literal_anonymous_name_used_directly():
    labels = [("start", [_say("Random Person", "Hi.")])]
    text, _flagged = emit_script_vnds(labels, characters={})
    assert "nameplate Random Person\n" in text


def test_menu_flattens_with_fallthrough_continuation():
    # A choice with no explicit jump must implicitly jump to whatever
    # followed the menu in the source (Ren'Py "falls through" semantics).
    menu = Menu(
        choices=[
            MenuChoice(text="Say hi.", body=[_say(None, "Hi!")], loc=LOC),
            MenuChoice(text="Stay quiet.", body=[Jump(target="elsewhere", loc=LOC)], loc=LOC),
        ],
        loc=LOC,
    )
    labels = [("start", [menu, _say(None, "After the menu.")])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert flagged.items == []

    assert "@start\nchoice Say hi.|Stay quiet.\njump __start_choice_2|__start_choice_3\n" in text
    # first choice falls through -> implicit jump to the continuation label
    assert "@__start_choice_2\nnameplate ~\ntext Hi!\njump __start_cont_1\n" in text
    # second choice already ends in a jump -> no implicit jump appended
    assert "@__start_choice_3\njump elsewhere\n" in text
    # the continuation label carries whatever followed the menu
    assert "@__start_cont_1\nnameplate ~\ntext After the menu.\n" in text


def test_menu_with_no_continuation_needs_no_implicit_jump():
    menu = Menu(
        choices=[MenuChoice(text="Only option.", body=[Return(loc=LOC)], loc=LOC)],
        loc=LOC,
    )
    labels = [("start", [menu])]
    text, _flagged = emit_script_vnds(labels, characters={})
    assert "@__start_choice_1\nreturn\n" in text
    assert "jump __start_cont" not in text


def test_nested_label_mid_body_emits_inline_and_keeps_falling_through():
    # regression: converting a second real game (Mice Tea) crashed
    # immediately with "unhandled node type: Label" -- Ren'Py allows (and
    # real content uses) a `label name:` declared *inside* another label's
    # body: a named point mid-scene, jumped back to directly to
    # re-present a choice after a failed/retry path, not a genuinely
    # nested scope. VNDS's label system is exactly as flat as Ren'Py's --
    # every "@name" is a global jump target, and falling through one
    # during linear execution is a no-op -- so this needs no synthetic
    # jump, just the marker emitted inline, with everything that followed
    # it in the source still executing right after.
    nested = Label(
        name="choice_point",
        body=[_say(None, "Reached the choice point.")],
        loc=LOC,
    )
    labels = [("start", [_say(None, "Before."), nested, _say(None, "After.")])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert flagged.items == []
    parsed = _labels_from_vnds(text)

    assert parsed["start"] == ["nameplate ~", "text Before."]
    assert parsed["choice_point"] == [
        "nameplate ~",
        "text Reached the choice point.",
        "nameplate ~",
        "text After.",
    ]


def test_image_tag_resolves_through_declared_path_basename():
    # `image sakev = "gui/logo.jpg"` — the tag doesn't match the file's
    # basename, so a naive slugify of the tag would emit the wrong token.
    images = {"sakev": "gui/logo.jpg"}
    labels = [("start", [Scene(image="sakev", position=None, loc=LOC), Show(image="sakev", position=None, loc=LOC), Hide(image="sakev", loc=LOC)])]
    text, _flagged = emit_script_vnds(labels, characters={}, images=images)
    assert "bgload logo.t3x\n" in text
    assert "setimg logo.t3x 200 40 sakev\n" in text
    assert "clearslot sakev\n" in text


def test_undeclared_image_tag_falls_back_to_slugified_tag():
    labels = [("start", [Scene(image="eileen happy", position=None, loc=LOC)])]
    text, _flagged = emit_script_vnds(labels, characters={}, images={})
    assert "bgload eileen_happy.t3x\n" in text


def test_set_emits_gsetvar():
    labels = [("start", [Set(var="affection", expr="(affection + 1)", loc=LOC)])]
    text, _flagged = emit_script_vnds(labels, characters={})
    assert "gsetvar affection = (affection + 1)\n" in text


def test_top_level_sets_emit_before_first_label():
    labels = [("start", [_say(None, "Hi.")])]
    top_level_sets = [Set(var="affection", expr="0", loc=LOC)]
    text, _flagged = emit_script_vnds(labels, characters={}, top_level_sets=top_level_sets)
    assert text.startswith("gsetvar affection = 0\n@start\n")


def test_if_elif_else_flattens_with_fallthrough_continuation():
    node = If(
        branches=[
            IfBranch(condition="(affection >= 3)", body=[_say(None, "Route good.")]),
            IfBranch(condition="(affection >= 1)", body=[Jump(target="route_ok", loc=LOC)]),
            IfBranch(condition=None, body=[_say(None, "Route bad.")]),
        ],
        loc=LOC,
    )
    labels = [("start", [node, _say(None, "After the if.")])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert flagged.items == []

    assert (
        "@start\n"
        "ifvar (affection >= 3) jump __start_if_2\n"
        "ifvar (affection >= 1) jump __start_if_3\n"
        "jump __start_else_4\n"
    ) in text
    # first branch falls through -> implicit jump to the continuation label
    assert "@__start_if_2\nnameplate ~\ntext Route good.\njump __start_cont_1\n" in text
    # second branch already ends in a jump -> no implicit jump appended
    assert "@__start_if_3\njump route_ok\n" in text
    # else branch also needs the implicit jump since it's its own label too
    assert "@__start_else_4\nnameplate ~\ntext Route bad.\njump __start_cont_1\n" in text
    assert "@__start_cont_1\nnameplate ~\ntext After the if.\n" in text


def test_if_without_else_or_remainder_ends_cleanly():
    node = If(
        branches=[IfBranch(condition="book", body=[Return(loc=LOC)])],
        loc=LOC,
    )
    labels = [("start", [node])]
    text, _flagged = emit_script_vnds(labels, characters={})
    assert "@start\nifvar book jump __start_if_1\n" in text
    assert "jump __start_cont" not in text
    assert "@__start_if_1\nreturn\n" in text


def _labels_from_vnds(text):
    """Parses emitted script.vnds text into {label: [lines...]} for
    tracing flattened control flow in tests, without depending on exact
    synthetic label names (which are an implementation detail)."""
    labels = {}
    current = None
    for line in text.splitlines():
        if line.startswith("@"):
            current = line[1:]
            labels[current] = []
        elif line.strip() and current is not None:
            labels[current].append(line.strip())
    return labels


def _find_label(parsed, predicate):
    return next(name for name, block in parsed.items() if predicate(block))


def _follow_jump(parsed, label):
    """Follows a chain of labels whose *entire* content is a single
    unconditional jump (synthetic hops the emitter's worklist mechanism
    introduces), returning the first label with real content."""
    seen = set()
    while parsed[label] == [f"jump {parsed[label][0].split(' ', 1)[1]}"] and label not in seen:
        seen.add(label)
        label = parsed[label][0].split(" ", 1)[1]
    return label


def test_while_loop_wires_entry_check_body_and_exit():
    node = While(condition="inconvo", body=[_say(None, "in the loop")], loc=LOC)
    labels = [("chat", [Set(var="inconvo", expr="True", loc=LOC), node, _say(None, "after the loop")])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert flagged.items == []
    parsed = _labels_from_vnds(text)

    # entry point jumps straight to a check label
    chat_block = parsed["chat"]
    assert chat_block[-1].startswith("jump ")
    check_label = chat_block[-1].split(" ", 1)[1]

    # the check tests the condition and (possibly via synthetic hop labels)
    # jumps into the real body if true
    check_block = parsed[check_label]
    assert check_block[0].startswith("ifvar inconvo jump ")
    body_label = _follow_jump(parsed, check_block[0].split(" jump ")[1])
    assert parsed[body_label][0] == "nameplate ~"
    assert parsed[body_label][1] == "text in the loop"
    # the body loops back to the same check after finishing
    assert parsed[body_label][-1] == f"jump {check_label}"

    # if the condition is false, the check falls through to the post-loop code
    assert check_block[-1].startswith("jump ")
    exit_label = _follow_jump(parsed, check_block[-1].split(" ", 1)[1])
    assert parsed[exit_label] == ["nameplate ~", "text after the loop"]


def test_while_with_early_exit_body_does_not_append_loop_back():
    # a body that already ends in its own control transfer (e.g. a menu
    # choice jumping elsewhere entirely) must not get an extra loop-back
    # jump appended after it
    node = While(condition="flag", body=[Jump(target="elsewhere", loc=LOC)], loc=LOC)
    labels = [("start", [node])]
    text, _flagged = emit_script_vnds(labels, characters={})
    parsed = _labels_from_vnds(text)
    body_label = _find_label(parsed, lambda block: block == ["jump elsewhere"])
    assert body_label is not None


def test_while_with_no_remainder_ends_cleanly_when_false():
    node = While(condition="flag", body=[Return(loc=LOC)], loc=LOC)
    labels = [("start", [node])]
    text, _flagged = emit_script_vnds(labels, characters={})
    parsed = _labels_from_vnds(text)
    check_label = _find_label(parsed, lambda block: block and block[0].startswith("ifvar flag jump "))
    # no remainder after the while -> no trailing unconditional jump needed
    assert len(parsed[check_label]) == 1


def test_show_atl_xalign_yalign_used_precisely_no_flag():
    labels = [("start", [Show(image="bg", position=None, xalign=0.25, yalign=0.5, loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    # yalign/yanchor are threaded through as trailing setimg tokens (in
    # addition to the positional, sprite-height-unaware `y` fallback) so
    # the engine can resolve the real pixel position against the sprite's
    # actual loaded height at setimg time -- see _static_prop_tokens.
    assert "setimg bg.t3x 100 120 bg yalign=0.5 yanchor=0.5\n" in text
    assert flagged.items == []


def test_show_atl_xalign_only_keeps_default_y():
    labels = [("start", [Show(image="bg", position=None, xalign=0.0, loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "setimg bg.t3x 0 40 bg\n" in text
    assert flagged.items == []


def test_show_approximated_atl_flags_but_still_positions():
    labels = [("start", [Show(image="bg", position=None, xalign=0.5, yalign=0.5, approximated_atl=True, loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "setimg bg.t3x 200 120 bg yalign=0.5 yanchor=0.5\n" in text
    assert len(flagged.items) == 1
    assert flagged.items[0].reason.startswith("ATL animation/zoom/alpha approximated")


def test_scene_atl_position_is_ignored_and_flagged():
    labels = [("start", [Scene(image="bg", position=None, xalign=0.5, yalign=0.5, loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "bgload bg.t3x\n" in text
    assert len(flagged.items) == 1
    assert flagged.items[0].reason == "scene ATL position has no VNDS equivalent (bgload is full-screen); position ignored"


def test_show_with_preset_anim_emits_anim_command_no_flag():
    anim = AnimSpec(duration=0.3, preset="enter_fade")
    labels = [("start", [Show(image="eileen happy", position=None, loc=LOC, anim=anim)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "setimg eileen_happy.t3x 200 40 eileen\n" in text
    assert "anim eileen_happy enter_fade 0.3\n" in text
    assert flagged.items == []


def test_show_with_keyframe_anim_emits_anim_begin_keyframe_anim_end():
    anim = AnimSpec(
        duration=1.0,
        keyframes=[(0.0, {"x": 80.0, "alpha": 0.0}), (0.5, {"x": 160.0, "alpha": 1.0}), (1.0, {"x": 160.0})],
    )
    labels = [("start", [Show(image="char_hero", position=None, loc=LOC, anim=anim, approximated_atl=True)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "anim_begin char_hero 1\n" in text
    assert "keyframe 0 x=80 alpha=0\n" in text
    assert "keyframe 0.5 x=160 alpha=1\n" in text
    assert "keyframe 1 x=160\n" in text
    assert "anim_end\n" in text
    assert len(flagged.items) == 1
    assert "generic keyframe sequence" in flagged.items[0].reason


def test_show_with_keyframe_anim_and_ease_includes_ease_in_anim_begin():
    anim = AnimSpec(duration=0.6, ease="ease_out", keyframes=[(0.0, {"alpha": 0.0}), (1.0, {"alpha": 1.0})])
    labels = [("start", [Show(image="char_hero", position=None, loc=LOC, anim=anim)])]
    text, _flagged = emit_script_vnds(labels, characters={})
    assert "anim_begin char_hero 0.6 ease_out\n" in text


def test_scene_with_known_transition_emits_a_real_bgload_fade_no_flag():
    # dissolve/fade wire into bgload's existing (previously-unpopulated)
    # frames token -- a real alpha fade-in (images.moon's Timer.tween), not
    # the old inert "transition dissolve 0.5" line ("transition" was never
    # a recognized engine instruction at all).
    labels = [("start", [Scene(image="bg", position=None, transition="dissolve", loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "bgload bg.t3x 30\n" in text
    assert "transition" not in text
    assert flagged.items == []


def test_scene_with_unknown_transition_downgrades_to_a_real_dissolve_and_flags():
    labels = [("start", [Scene(image="bg", position=None, transition="wipeleft", loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "bgload bg.t3x 30\n" in text
    assert len(flagged.items) == 1
    assert "wipeleft" in flagged.items[0].reason


def test_show_with_known_transition_fires_a_real_enter_fade_no_flag():
    labels = [("start", [Show(image="eileen happy", position="center", transition="dissolve", loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "anim eileen_happy enter_fade 0.5\n" in text
    assert flagged.items == []


def test_show_with_vpunch_fires_the_real_shake_preset_no_flag():
    labels = [("start", [Show(image="eileen happy", position="center", transition="vpunch", loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "anim eileen_happy shake 0.5\n" in text
    assert flagged.items == []


def test_hide_clears_by_slot_not_by_the_hide_statements_own_bare_path():
    # real-hardware regression: a bare `hide chance` (no attributes) used to
    # resolve to some default/base image path and emit a path-matched
    # `clearimg` -- but the character was actually shown as "chance happy"
    # (a *different* composited file), so the path never matched what was
    # really on screen and the old sprite stayed stuck ("stacking"). Fixed
    # by clearing by slot (the tag, "chance") instead, matching however the
    # character actually got shown.
    labels = [
        (
            "start",
            [
                Show(image="chance happy", position="center", loc=LOC),
                Hide(image="chance", loc=LOC),
            ],
        )
    ]
    text, _flagged = emit_script_vnds(labels, characters={})
    lines = text.strip().splitlines()
    assert "clearslot chance" in lines
    assert not any(line.startswith("clearimg") for line in lines)


def test_hide_with_transition_fades_out_and_waits_before_removal():
    labels = [("start", [Hide(image="eileen happy", transition="dissolve", loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    lines = text.strip().splitlines()
    # the fade + wait must come *before* clearslot, or images.moon drops the
    # sprite before the fade is ever visible.
    assert (
        lines.index("anim eileen_happy exit_fade 0.5")
        < lines.index("anim_wait eileen_happy")
        < lines.index("clearslot eileen")
    )
    assert flagged.items == []


def test_standalone_transition_applies_to_the_preceding_scene():
    labels = [("start", [Scene(image="bg", position=None, loc=LOC), Transition(name="fade", loc=LOC)])]
    text, _flagged = emit_script_vnds(labels, characters={})
    assert "bgload bg.t3x 30\n" in text
    assert "transition" not in text


def test_standalone_transition_applies_to_the_preceding_show():
    labels = [
        ("start", [Show(image="eileen happy", position="center", loc=LOC), Transition(name="dissolve", loc=LOC)])
    ]
    text, _flagged = emit_script_vnds(labels, characters={})
    assert "anim eileen_happy enter_fade 0.5\n" in text


def test_standalone_transition_before_hide_fades_out_then_removes():
    # Ren'Py's common two-line idiom: a bare `hide` immediately followed by
    # a standalone `with` -- must be intercepted before the sprite is
    # removed, same as an inline `hide x with dissolve`.
    labels = [("start", [Hide(image="eileen happy", loc=LOC), Transition(name="dissolve", loc=LOC)])]
    text, _flagged = emit_script_vnds(labels, characters={})
    lines = text.strip().splitlines()
    assert (
        lines.index("anim eileen_happy exit_fade 0.5")
        < lines.index("anim_wait eileen_happy")
        < lines.index("clearslot eileen")
    )


def test_standalone_transition_with_no_preceding_visual_is_a_harmless_flag_only():
    labels = [("start", [Transition(name="wipeleft", loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert text.strip().splitlines() == ["@start"]
    assert len(flagged.items) == 1
    assert "wipeleft" in flagged.items[0].reason


def test_play_music_sound_voice_map_to_existing_channel_commands():
    labels = [
        (
            "start",
            [
                Play(channel="music", file="bgm/theme.opus", is_queue=False, loc=LOC),
                Play(channel="sound", file="click.wav", is_queue=False, loc=LOC),
                Play(channel="voice", file="line1.ogg", is_queue=False, loc=LOC),
            ],
        )
    ]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "music theme.ogg\n" in text
    assert "sound click.ogg 1\n" in text
    assert "voiceover line1.ogg\n" in text
    assert flagged.items == []


def test_queue_is_approximated_as_immediate_play():
    labels = [("start", [Play(channel="music", file="next.ogg", is_queue=True, loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "music next.ogg\n" in text
    assert len(flagged.items) == 1
    assert flagged.items[0].reason.startswith("queue approximated")


def test_stop_maps_to_existing_stop_commands():
    labels = [("start", [Stop(channel="music", loc=LOC), Stop(channel="sound", loc=LOC), Stop(channel="voice", loc=LOC)])]
    text, _flagged = emit_script_vnds(labels, characters={})
    assert "stopmusic\n" in text
    assert "stopsound\n" in text
    assert "stopvoice\n" in text


def test_play_audio_channel_aliases_to_sound_commands():
    # Ren'Py's own built-in one-shot "audio" channel -- functionally the
    # same as "sound".
    labels = [("start", [Play(channel="audio", file="click.wav", is_queue=False, loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "sound click.ogg 1\n" in text
    assert flagged.items == []


def test_play_and_stop_ambiance_map_to_the_new_ambiance_channel():
    # a real, independent 4th channel -- not an approximation -- since it
    # legitimately plays simultaneously with music in real content.
    labels = [
        ("start", [Play(channel="ambiance", file="amb_city.ogg", is_queue=False, loc=LOC), Stop(channel="ambiance", loc=LOC)])
    ]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "ambiance amb_city.ogg\n" in text
    assert "stopambiance\n" in text
    assert flagged.items == []


def test_play_with_an_unrecognized_but_safe_channel_still_plays_generically():
    # 13-corpus comparison finding: a custom audio channel (ScarletHollow's
    # secondary/tertiary/music4-6, Our Life's voice2) used to be dropped
    # entirely -- the engine now has a generic play/stop path (audio.moon's
    # `channels` table) for any \\w+-safe channel name, so this now plays
    # for real instead of silently vanishing; still flagged, but info-level
    # (behavior inferred from the name, not a real gap).
    labels = [("start", [Play(channel="bogus", file="x.ogg", is_queue=False, loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "play bogus x.ogg 1 sound\n" in text  # no "voice"/"music"/"ambien" substring -> defaults loop=True, mixer=sound
    assert len(flagged.items) == 1
    assert "not in the converter's known/verified set" in flagged.items[0].reason


def test_play_with_a_curated_custom_channel_uses_its_known_shape():
    # secondary/tertiary/music4-6 (ScarletHollow) and voice2 (Our Life) are
    # seeded into _CUSTOM_CHANNEL_SHAPE from real content, not the generic
    # name-substring fallback.
    labels = [("start", [Play(channel="voice2", file="line.ogg", is_queue=False, loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "play voice2 line.ogg 0 sound\n" in text  # voice2 -> loop=False, mixer=sound
    assert len(flagged.items) == 1
    assert "not in the converter's known/verified set" in flagged.items[0].reason


def test_play_with_a_channel_name_unsafe_for_the_vnds_format_still_hard_drops():
    # Only reachable via the Python-API channel= kwarg form (the
    # declarative play/stop syntax is already \\w+-restricted at parse
    # time) -- a name with a space/punctuation can't become a VNDS
    # instruction token, so this is the one case that still correctly
    # drops rather than emitting a malformed line.
    labels = [("start", [Play(channel="my channel", file="x.ogg", is_queue=False, loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "my channel" not in text.split("\n")[-2]
    assert len(flagged.items) == 1
    assert "incompatible with the VNDS instruction format" in flagged.items[0].reason


def test_stop_with_an_unrecognized_but_safe_channel_still_stops_generically():
    labels = [("start", [Stop(channel="bogus", loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "stop bogus\n" in text
    assert len(flagged.items) == 1
    assert "not in the converter's known/verified set" in flagged.items[0].reason


def test_play_and_stop_music2_map_to_the_new_music2_channel():
    # a real, independent 5th channel -- Mice Tea uses it heavily for a
    # genuine layered-music crossfade, not just cleanup.
    labels = [
        ("start", [Play(channel="music2", file="b.ogg", is_queue=False, loc=LOC), Stop(channel="music2", loc=LOC)])
    ]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "music2 b.ogg\n" in text
    assert "stopmusic2\n" in text
    assert flagged.items == []


def test_set_volume_emits_a_real_setvolume_command():
    labels = [("start", [SetVolume(channel="music2", level=0.0, delay=3.0, loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "setvolume music2 0 3\n" in text
    assert flagged.items == []


def test_set_volume_voice_channel_uses_the_channel_identity_not_the_play_command_name():
    # "voice"'s *play* command is "voiceover", but its channel *identity*
    # (audio.moon's channel_table) is still "voice" -- setvolume must use
    # the identity, not the command name.
    labels = [("start", [SetVolume(channel="voice", level=0.5, delay=0.0, loc=LOC)])]
    text, _flagged = emit_script_vnds(labels, characters={})
    assert "setvolume voice 0.5 0\n" in text


def test_set_volume_with_an_unrecognized_but_safe_channel_still_sets_generically():
    # setvolume is already fully generic at the VNDS-instruction-format
    # level (audio.moon's channel_table resolves any name via its
    # `channels` fallback) -- no loop/mixer needed here, unlike play/stop.
    labels = [("start", [SetVolume(channel="bogus", level=1.0, delay=0.0, loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "setvolume bogus 1 0\n" in text
    assert len(flagged.items) == 1
    assert "not in the converter's known/verified set" in flagged.items[0].reason


def test_play_with_choices_emits_a_random_ifvar_jump_chain():
    # Ren'Py's randomized-file-choice idiom, as a genuine runtime random
    # pick composed from existing VNDS primitives -- not approximated to
    # a fixed entry.
    play = Play(
        channel="sound",
        file="a.ogg",
        is_queue=False,
        loc=LOC,
        choices=["a.ogg", "b.ogg", "c.ogg"],
    )
    labels = [("start", [play])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert flagged.items == []
    assert "random __start_rand_1 1 3\n" in text
    assert "ifvar (__start_rand_1 == 1) jump __start_rand_choice_3\n" in text
    assert "ifvar (__start_rand_1 == 2) jump __start_rand_choice_4\n" in text
    assert "ifvar (__start_rand_1 == 3) jump __start_rand_choice_5\n" in text
    assert "@__start_rand_choice_3\n" in text
    assert "sound a.ogg 1\n" in text
    assert "sound b.ogg 1\n" in text
    assert "sound c.ogg 1\n" in text
    assert "@__start_rand_cont_2\n" in text
    # each choice jumps to the shared continuation label
    assert text.count("jump __start_rand_cont_2") == 3


def test_play_with_choices_and_a_custom_channel_does_not_crash():
    # regression: _emit_random_play used to do a direct _PLAY_COMMAND[...]
    # subscript (no .get()) on the assumption "the caller already confirmed
    # the channel resolves" -- untrue for a custom channel outside the 5
    # curated ones, which would raise a real KeyError instead of falling
    # back to the generic play form like the ordinary (non-random) Play
    # path already does.
    play = Play(channel="bogus", file="a.ogg", is_queue=False, loc=LOC, choices=["a.ogg", "b.ogg"])
    labels = [("start", [play])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert len(flagged.items) == 1
    assert "not in the converter's known/verified set" in flagged.items[0].reason
    assert "play bogus a.ogg 1 sound\n" in text
    assert "play bogus b.ogg 1 sound\n" in text


def test_play_with_choices_does_not_consume_the_rest_of_the_body():
    play = Play(channel="sound", file="a.ogg", is_queue=False, loc=LOC, choices=["a.ogg", "b.ogg"])
    labels = [("start", [play, Say(who=None, what="after the random cue", loc=LOC)])]
    text, _flagged = emit_script_vnds(labels, characters={})
    assert "after the random cue" in text


def test_pause_with_duration_converts_seconds_to_frames():
    labels = [("start", [Pause(seconds=1.5, loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "delay 90\n" in text
    assert flagged.items == []


def test_bare_pause_is_flagged_info_and_emits_nothing():
    labels = [("start", [Pause(seconds=None, loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "delay" not in text
    assert len(flagged.items) == 1
    assert flagged.items[0].reason.startswith("bare pause")


def test_window_show_and_hide_emit_existing_engine_command():
    labels = [("start", [Window(state="show", loc=LOC), Window(state="hide", loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "window show\n" in text
    assert "window hide\n" in text
    assert flagged.items == []


def test_unsupported_node_emits_flagged_marker_and_is_recorded():
    from converter.parser import Unsupported

    labels = [("start", [Unsupported(text="if x:", reason="unsupported statement", loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={})
    assert "# FLAGGED P0001\n" in text
    assert len(flagged.items) == 1
    assert flagged.items[0].id == "P0001"
    assert flagged.items[0].text == "if x:"


def test_screen_def_emits_before_the_first_label():
    screen = ScreenDef(
        name="main_menu2",
        root=ScreenBox(children=[
            ScreenBox(children=[
                ScreenText(text="Welcome"),
                ScreenButton(label="Start", action="jump start"),
            ]),
        ]),
        loc=LOC,
    )
    labels = [("start", [Say(who=None, what="Hi.", loc=LOC)])]
    text, flagged = emit_script_vnds(labels, characters={}, screens=[screen])
    assert flagged.items == []

    lines = text.splitlines()
    assert lines.index("screen_begin main_menu2") < lines.index("@start")
    assert "vbox_begin" in lines
    assert "screen_text Welcome" in lines
    assert "screen_button Start | jump start" in lines
    assert "vbox_end" in lines
    assert "screen_end" in lines


def test_screen_def_with_if_elif_else_emits_screen_if_chain():
    screen = ScreenDef(
        name="stats",
        root=ScreenBox(children=[
            ScreenIf(branches=[
                ScreenIfBranch(cond="(affection > 5)", children=[ScreenText(text="High")]),
                ScreenIfBranch(cond="(affection > 0)", children=[ScreenText(text="Medium")]),
                ScreenIfBranch(cond=None, children=[ScreenText(text="Low")]),
            ]),
        ]),
        loc=LOC,
    )
    text, _flagged = emit_script_vnds([("start", [])], characters={}, screens=[screen])
    lines = text.splitlines()
    assert "screen_if (affection > 5)" in lines
    assert "screen_elif (affection > 0)" in lines
    assert "screen_else" in lines
    assert "screen_endif" in lines
    # order: if-branch content comes before elif, which comes before else
    assert lines.index("screen_if (affection > 5)") < lines.index("screen_elif (affection > 0)") < lines.index("screen_else") < lines.index("screen_endif")


def test_screen_imagemap_emits_ground_and_hotspots():
    # x/y/w/h are fractions (0.0-1.0) of the game's own declared
    # resolution, not absolute pixels (see ScreenHotspot's own docstring
    # for the real-hardware regression this fixes -- the engine
    # multiplies by whatever the actually-loaded ground image's real
    # dimensions turn out to be).
    screen = ScreenDef(
        name="main_menu",
        root=ScreenBox(children=[
            ScreenImagemap(
                ground="gui/mainmenu01_idle.jpg",
                hotspots=[
                    ScreenHotspot(x=0.055, y=0.39, w=0.175, h=0.031, action="hide_screen"),
                    ScreenHotspot(x=0.277, y=0.67, w=0.143, h=0.033, action="quit"),
                ],
            ),
        ]),
        loc=LOC,
    )
    text, flagged = emit_script_vnds([("start", [])], characters={}, screens=[screen])
    assert flagged.items == []
    lines = text.splitlines()
    assert "imagemap_begin mainmenu01_idle.t3x" in lines
    assert "hotspot 0.055 0.39 0.175 0.031 | hide_screen" in lines
    assert "hotspot 0.277 0.67 0.143 0.033 | quit" in lines
    assert "imagemap_end" in lines
    begin_idx = lines.index("imagemap_begin mainmenu01_idle.t3x")
    end_idx = lines.index("imagemap_end")
    assert begin_idx < lines.index("hotspot 0.055 0.39 0.175 0.031 | hide_screen") < end_idx


def test_screen_imagemap_null_action_hotspot_emits_empty_action():
    screen = ScreenDef(
        name="main_menu",
        root=ScreenBox(children=[
            ScreenImagemap(
                ground="gui/mainmenu01_idle.jpg",
                hotspots=[ScreenHotspot(x=0.01, y=0.01, w=0.005, h=0.005, action=None)],
            ),
        ]),
        loc=LOC,
    )
    text, _flagged = emit_script_vnds([("start", [])], characters={}, screens=[screen])
    assert "hotspot 0.01 0.01 0.005 0.005 | " in text.splitlines()


def test_screen_imagemap_nested_in_if_else():
    screen = ScreenDef(
        name="main_menu",
        root=ScreenBox(children=[
            ScreenIf(branches=[
                ScreenIfBranch(
                    cond="persistent_beatgame",
                    children=[ScreenImagemap(ground="gui/mainmenu02_idle.jpg", hotspots=[])],
                ),
                ScreenIfBranch(
                    cond=None,
                    children=[ScreenImagemap(ground="gui/mainmenu01_idle.jpg", hotspots=[])],
                ),
            ]),
        ]),
        loc=LOC,
    )
    text, _flagged = emit_script_vnds([("start", [])], characters={}, screens=[screen])
    lines = text.splitlines()
    assert (
        lines.index("screen_if persistent_beatgame")
        < lines.index("imagemap_begin mainmenu02_idle.t3x")
        < lines.index("screen_else")
        < lines.index("imagemap_begin mainmenu01_idle.t3x")
        < lines.index("screen_endif")
    )


def test_day_card_emits_title_background_overlay_text_and_mood_jingle():
    node = DayCard(day_number="32", subtitle="Routines", mood="sad", loc=LOC)
    text, flagged = emit_script_vnds([("start", [node])], characters={})
    assert "window hide\n" in text
    assert "bgload chapter_titlecard.t3x\n" in text
    assert "overlay_text day_title 200 66 80 fff Day\n" in text
    assert "overlay_text day_number 200 96 240 fff 32\n" in text
    assert "overlay_text day_subtitle 200 210 48 fff Routines\n" in text
    assert "music hot_cocoa_short.ogg\n" in text
    assert "bgload black.t3x\n" in text
    assert text.count("overlay_clear") == 2
    assert len(flagged.items) == 1
    assert "title-card visual style approximated" in flagged.items[0].reason


def test_day_card_sparkles_mood_uses_gyaru_titlecard_and_own_jingle():
    node = DayCard(day_number="7", subtitle="A Twist", mood="sparkles", loc=LOC)
    text, _flagged = emit_script_vnds([("start", [node])], characters={})
    assert "bgload chapter_titlecard_gyaru.t3x\n" in text
    assert "music sparkles.ogg\n" in text


def test_day_card_default_mood_uses_the_default_jingle():
    node = DayCard(day_number="1", subtitle="A New Topic", mood="default", loc=LOC)
    text, _flagged = emit_script_vnds([("start", [node])], characters={})
    assert "music a_new_topic.ogg\n" in text


def test_subchapter_card_position_depends_on_message_length():
    short = SubchapterCard(message="Short", loc=LOC)
    text, flagged = emit_script_vnds([("start", [short])], characters={})
    assert "overlay_text subchapter_text 68 12 40 514944 Short\n" in text
    assert len(flagged.items) == 1
    assert "backing image not reproduced" in flagged.items[0].reason

    long_msg = SubchapterCard(message="This is a much longer subchapter heading", loc=LOC)
    text, _flagged = emit_script_vnds([("start", [long_msg])], characters={})
    assert "overlay_text subchapter_text 112 12 40 514944" in text


def test_subchapter_card_strips_noalt_tags_for_length_but_keeps_them_in_text():
    node = SubchapterCard(message="{noalt}Routines{/noalt}", loc=LOC)
    text, _flagged = emit_script_vnds([("start", [node])], characters={})
    # "Routines" (8 chars, without the tags) is "small" -> x=68
    assert "overlay_text subchapter_text 68 12 40 514944" in text


def test_subchapter_hide_clears_the_overlay_with_no_flag():
    text, flagged = emit_script_vnds([("start", [SubchapterHide(loc=LOC)])], characters={})
    assert text.strip().endswith("overlay_clear")
    assert flagged.items == []


def test_reset_audio_emits_exact_setvolume_and_stop_commands_no_flag():
    text, flagged = emit_script_vnds([("start", [ResetAudio(loc=LOC)])], characters={})
    assert "setvolume music 1 0\n" in text
    assert "setvolume music2 1 0\n" in text
    assert "stopmusic2\n" in text
    assert "stopambiance\n" in text
    assert flagged.items == []


def test_the_end_card_emits_background_and_positioned_title():
    node = TheEndCard(title="The Beginning of Something New", loc=LOC)
    text, flagged = emit_script_vnds([("start", [node])], characters={})
    assert "window hide\n" in text
    assert "bgload the_end.t3x\n" in text
    assert "overlay_text the_end_title 11 11 40 fff The Beginning of Something New\n" in text
    assert len(flagged.items) == 1
    assert "end-card visual style approximated" in flagged.items[0].reason


def test_placeholder_shows_message_and_flags_the_missing_rollback():
    text, flagged = emit_script_vnds([("start", [Placeholder(loc=LOC)])], characters={})
    assert "overlay_text placeholder_msg 200 120 32 fff Path currently under construction.\n" in text
    assert len(flagged.items) == 1
    assert "rollback" in flagged.items[0].reason


def _afd_character_image(selector_body: str, attribute_sets: str = '{"eyes_happy", "eyes_neutral"}'):
    source = f'''
init python:
    def afd_layer_selector(ci, attr):
{selector_body}

image afd_l = CharacterImage(
    character_name="afd",
    size=(750, 1300),
    layers=("Base*", "eyes *"),
    attribute_sets=({attribute_sets},),
    aliases={{}},
    layer_selector=afd_layer_selector,
)
'''
    return parse_character_image_declarations(source, "afd_l.rpy")


def _make_afd_assets(tmp_path):
    char_dir = tmp_path / "characters" / "afd"
    char_dir.mkdir(parents=True)
    (char_dir / "Base.png").write_bytes(b"\x89PNG")
    (char_dir / "eyes happy.png").write_bytes(b"\x89PNG")
    (char_dir / "eyes neutral.png").write_bytes(b"\x89PNG")
    return tmp_path


class TestCharacterImageShowEmission:
    def test_emits_clearslot_and_one_setimg_per_layer_in_declared_order(self, tmp_path):
        assets_dir = _make_afd_assets(tmp_path)
        defs = _afd_character_image(
            '''        yield "Base"
        if "eyes_happy" in attr:
            yield "eyes happy"
        else:
            yield "eyes neutral"
'''
        )
        layer_files = {}
        labels = [("start", [Show(image="afd_l eyes_happy", position=None, loc=LOC)])]
        text, flagged = emit_script_vnds(
            labels, characters={}, character_images=defs, assets_dir=assets_dir,
            character_image_layer_files=layer_files,
        )
        lines = [l for l in text.splitlines() if l.startswith(("clearslot", "setimg"))]
        assert lines == [
            "clearslot afd_l",
            "setimg Base.t3x 200 40 afd_l:0",
            "setimg eyes_happy.t3x 200 40 afd_l:1",
        ]
        assert flagged.items == []
        assert set(layer_files.keys()) == {"Base", "eyes_happy"}

    def test_persistent_gated_selector_emits_ifvar_branch_with_two_layer_sets(self, tmp_path):
        assets_dir = _make_afd_assets(tmp_path)
        defs = _afd_character_image(
            '''        yield "Base"
        if persistent.nude_sprites:
            yield "eyes happy"
'''
        )
        labels = [("start", [Show(image="afd_l", position=None, loc=LOC)])]
        text, flagged = emit_script_vnds(
            labels, characters={}, character_images=defs, assets_dir=assets_dir,
        )
        assert "ifvar (persistent_nude_sprites == 1) jump" in text
        # false branch (no eyes layer) and true branch (with eyes layer)
        # each get their own clearslot -- two full groups, not one shared.
        assert text.count("clearslot afd_l") == 2
        assert text.count("setimg Base.t3x") == 2
        assert text.count("setimg eyes_happy.t3x") == 1
        assert flagged.items == []

    def test_unsupported_selector_construct_falls_back_to_default_pose_and_flags(self, tmp_path):
        assets_dir = _make_afd_assets(tmp_path)
        # the dict comprehension only runs for a non-empty attr set, so the
        # fallback re-resolution with an *empty* attr set (this feature's
        # "default pose" fallback) still succeeds -- demonstrating a
        # partial recovery, not a total loss, for this one bad usage.
        defs = _afd_character_image(
            '''        yield "Base"
        if attr:
            x = {a: a for a in attr}
'''
        )
        labels = [("start", [Show(image="afd_l eyes_happy", position=None, loc=LOC)])]
        text, flagged = emit_script_vnds(
            labels, characters={}, character_images=defs, assets_dir=assets_dir,
        )
        assert "clearslot afd_l" in text
        assert "setimg Base.t3x 200 40 afd_l:0" in text
        assert len(flagged.items) == 1
        assert "unsupported construct" in flagged.items[0].reason or "couldn't be resolved" in flagged.items[0].reason

    def test_layer_with_no_resolvable_file_is_flagged_but_others_still_render(self, tmp_path):
        # "some_overlay" here is a stand-in for any yielded name with no
        # matching per-character file or declared image -- not
        # "lighting_night" specifically, which is now its own special case
        # (see test_lighting_night_attribute_tints_every_layer_instead_of_
        # being_treated_as_a_layer below): a real selector never yields it
        # as a genuine layer name at all once requested.
        assets_dir = _make_afd_assets(tmp_path)
        defs = _afd_character_image(
            '''        yield "Base"
        yield "some_overlay"
'''
        )
        labels = [("start", [Show(image="afd_l", position=None, loc=LOC)])]
        text, flagged = emit_script_vnds(
            labels, characters={}, character_images=defs, assets_dir=assets_dir,
        )
        setimg_lines = [l for l in text.splitlines() if l.startswith("setimg")]
        assert setimg_lines == ["setimg Base.t3x 200 40 afd_l:0"]  # no line emitted for the unresolved layer
        assert any("some_overlay" in item.reason for item in flagged.items)

    def test_layer_matching_a_declared_image_falls_back_to_it_instead_of_dropping(self, tmp_path):
        # the original CharacterImage falls back to `ImageReference(layer)`
        # (an ordinary declared-image lookup) whenever a yielded layer name
        # isn't a per-character asset, rather than dropping the layer.
        assets_dir = _make_afd_assets(tmp_path)
        defs = _afd_character_image(
            '''        yield "Base"
        yield "some_overlay"
'''
        )
        labels = [("start", [Show(image="afd_l", position=None, loc=LOC)])]
        text, flagged = emit_script_vnds(
            labels, characters={}, character_images=defs, assets_dir=assets_dir,
            images={"some_overlay": "images/fx/some_overlay.png"},
        )
        setimg_lines = [l for l in text.splitlines() if l.startswith("setimg")]
        assert setimg_lines == [
            "setimg Base.t3x 200 40 afd_l:0",
            "setimg some_overlay.t3x 200 40 afd_l:1",
        ]
        assert flagged.items == []

    def test_lighting_night_attribute_tints_every_layer_instead_of_being_treated_as_a_layer(self, tmp_path):
        # real content: ~15 character selectors check `if "lighting_night"
        # in attr: yield "lighting_night"` -- but the original engine's own
        # _duplicate excludes "lighting_night" from `attr` entirely before
        # the selector ever runs (so that branch is dead code there) and
        # instead applies a fixed blue-ish tint to every resolved layer
        # when the *raw* show request includes it. expand_attrs now
        # reproduces the same exclusion, so a real-shaped selector never
        # yields it as a layer at all; the emitter applies the tint tokens
        # directly from the raw request.
        assets_dir = _make_afd_assets(tmp_path)
        defs = _afd_character_image(
            '''        yield "Base"
        if "lighting_night" in attr:
            yield "lighting_night"
'''
        )
        labels = [("start", [Show(image="afd_l lighting_night", position=None, loc=LOC)])]
        text, flagged = emit_script_vnds(
            labels, characters={}, character_images=defs, assets_dir=assets_dir,
        )
        setimg_lines = [l for l in text.splitlines() if l.startswith("setimg")]
        assert setimg_lines == ["setimg Base.t3x 200 40 afd_l:0 tint_r=0.75 tint_g=0.85 tint_b=1"]
        assert flagged.items == []

    def test_no_lighting_night_attribute_means_no_tint_tokens(self, tmp_path):
        assets_dir = _make_afd_assets(tmp_path)
        defs = _afd_character_image('''        yield "Base"
''')
        labels = [("start", [Show(image="afd_l", position=None, loc=LOC)])]
        text, _flagged = emit_script_vnds(
            labels, characters={}, character_images=defs, assets_dir=assets_dir,
        )
        setimg_lines = [l for l in text.splitlines() if l.startswith("setimg")]
        assert setimg_lines == ["setimg Base.t3x 200 40 afd_l:0"]

    def test_ordinary_show_unaffected_when_tag_not_a_character_image(self, tmp_path):
        assets_dir = _make_afd_assets(tmp_path)
        defs = _afd_character_image('''        yield "Base"
''')
        labels = [("start", [Show(image="bg", position=None, loc=LOC)])]
        text, flagged = emit_script_vnds(
            labels, characters={}, character_images=defs, assets_dir=assets_dir,
        )
        assert "setimg bg.t3x 200 40 bg\n" in text
        assert "clearslot" not in text


def _make_portrait_assets(tmp_path, folder="Cove_8"):
    char_dir = tmp_path / "images" / "characters" / folder
    expr_dir = char_dir / "Expressions"
    expr_dir.mkdir(parents=True)
    (char_dir / "default.png").write_bytes(b"\x89PNG")
    for i in range(3):
        (expr_dir / f"closed_eyes{i}.png").write_bytes(b"\x89PNG")
    (expr_dir / "n_brows.png").write_bytes(b"\x89PNG")
    return tmp_path


class TestPortraitUpdateEmission:
    def _categories(self):
        return SpriteLayerCategories(
            parts_order=("base", "brows", "mouth", "eyes"),
            expressions=frozenset({"eyes", "mouth", "brows"}),
        )

    def _portrait_defs(self):
        return {
            "Cove_8": PortraitDef(
                tag="cove_8", name="Cove_8", speaker="COVE",
                animate_eyes=True, animate_mouth=False, width=615, height=1439, loc=LOC,
            )
        }

    def _parse_and_emit(self, source, tmp_path, characters=None):
        script, problems = parse_rpy(source, sprite_categories=self._categories())
        assert problems == []
        layer_files = {}
        text, flagged = emit_script_vnds(
            [("start", script.labels[0].body)],
            characters=characters or {},
            assets_dir=_make_portrait_assets(tmp_path),
            portrait_defs=self._portrait_defs(),
            portrait_layer_files=layer_files,
        )
        return text, flagged, layer_files

    def test_plain_layer_emits_a_static_portrait_instruction(self, tmp_path):
        source = 'label start:\n    $ ChangePortrait(chara="Cove_8", base="default")\n'
        text, flagged, layer_files = self._parse_and_emit(source, tmp_path)
        assert flagged.items == []
        assert "portrait Cove_8 base default.t3x plain 1 0 1 1 1\n" in text
        assert "default" in layer_files

    def test_eyes_layer_emits_a_three_frame_portrait_anim_instruction(self, tmp_path):
        source = 'label start:\n    $ ChangePortrait(chara="Cove_8", eyes="closed")\n'
        text, flagged, layer_files = self._parse_and_emit(source, tmp_path)
        assert flagged.items == []
        assert (
            "portrait_anim Cove_8 eyes closed_eyes0.t3x closed_eyes1.t3x closed_eyes2.t3x "
            "eyes 1 1 3 1 1 1 cove\n" in text
        )
        assert {"closed_eyes0", "closed_eyes1", "closed_eyes2"} <= layer_files.keys()

    def test_blink_false_disables_the_eyes_animate_flag(self, tmp_path):
        source = 'label start:\n    $ ChangePortrait(chara="Cove_8", blink=False, eyes="closed")\n'
        text, _flagged, _layer_files = self._parse_and_emit(source, tmp_path)
        assert " eyes 0 1 3 1 1 1 cove\n" in text

    def test_transition_false_disables_the_dissolve_flag(self, tmp_path):
        source = 'label start:\n    $ ChangePortrait(chara="Cove_8", transition=False, base="default")\n'
        text, _flagged, _layer_files = self._parse_and_emit(source, tmp_path)
        assert "portrait Cove_8 base default.t3x plain 0 0 1 1 1\n" in text

    def test_matrix_tint_is_threaded_onto_the_instruction(self, tmp_path):
        source = (
            'label start:\n    $ ChangePortrait(chara="Cove_8", base="default", '
            "matrix=im.matrix.tint(0.75,0.85,1.0))\n"
        )
        text, _flagged, _layer_files = self._parse_and_emit(source, tmp_path)
        assert "portrait Cove_8 base default.t3x plain 1 0 0.75 0.85 1\n" in text

    def test_missing_asset_file_is_flagged_not_crashed(self, tmp_path):
        source = 'label start:\n    $ ChangePortrait(chara="Cove_8", base="does_not_exist")\n'
        text, flagged, _layer_files = self._parse_and_emit(source, tmp_path)
        assert len(flagged.items) == 1
        assert "no resolvable per-character asset file" in flagged.items[0].reason
        assert "portrait Cove_8" not in text

    def test_mouth_layer_falls_back_to_frame0_when_not_animated_and_frames_1_2_are_missing(self, tmp_path):
        # 13-corpus comparison finding, confirmed against real Our Life
        # content: every real Portrait declares animateMouth=False, and
        # frame1/2 files for "mouth" don't exist anywhere in the game's
        # real asset tree at all (the lip-flap code path is real but
        # genuinely never exercised) -- must not require files that were
        # never shipped just because the wire format has 3 frame slots.
        assets_dir = _make_portrait_assets(tmp_path)
        (assets_dir / "images" / "characters" / "Cove_8" / "Expressions" / "n_mouth0.png").write_bytes(b"\x89PNG")
        source = 'label start:\n    $ ChangePortrait(chara="Cove_8", mouth="n")\n'
        script, problems = parse_rpy(source, sprite_categories=self._categories())
        assert problems == []
        text, flagged = emit_script_vnds(
            [("start", script.labels[0].body)], characters={}, assets_dir=assets_dir,
            portrait_defs=self._portrait_defs(), portrait_layer_files={},
        )
        assert flagged.items == []
        assert "portrait_anim Cove_8 mouth n_mouth0.t3x n_mouth0.t3x n_mouth0.t3x mouth 0 1 2 1 1 1 cove\n" in text

    def test_eyes_layer_falls_back_to_static_when_declared_animated_but_frames_1_2_are_missing_for_this_mood(self, tmp_path):
        # A character declared animateEyes=True but this *specific* mood
        # only shipped a frame0 file -- must degrade to a static portrait
        # for this mood rather than dropping the layer entirely.
        assets_dir = _make_portrait_assets(tmp_path)
        (assets_dir / "images" / "characters" / "Cove_8" / "Expressions" / "surprised_eyes0.png").write_bytes(b"\x89PNG")
        source = 'label start:\n    $ ChangePortrait(chara="Cove_8", eyes="surprised")\n'
        script, problems = parse_rpy(source, sprite_categories=self._categories())
        assert problems == []
        text, flagged = emit_script_vnds(
            [("start", script.labels[0].body)], characters={}, assets_dir=assets_dir,
            portrait_defs=self._portrait_defs(), portrait_layer_files={},
        )
        assert flagged.items == []
        # blink stays "1" (this character IS declared animateEyes=True --
        # only the *frames* fall back, since this specific mood shipped no
        # frame1/2) -- 3 identical frames just means the engine's blink
        # cycle never visually changes anything for this mood, harmless.
        assert (
            "portrait_anim Cove_8 eyes surprised_eyes0.t3x surprised_eyes0.t3x surprised_eyes0.t3x "
            "eyes 1 1 3 1 1 1 cove\n" in text
        )

    def test_say_emits_a_speaking_line_only_when_a_game_uses_portraits(self, tmp_path):
        from converter.parser import CharacterDef

        characters = {"cove": CharacterDef(varname="cove", display_name="Cove", color=None, loc=LOC)}
        source = 'label start:\n    $ ChangePortrait(chara="Cove_8", base="default")\n    cove "Hi."\n'
        text, _flagged, _layer_files = self._parse_and_emit(source, tmp_path, characters=characters)
        assert "speaking cove\n" in text

    def test_say_emits_no_speaking_line_for_a_game_without_portraits(self):
        # regression: emitting `speaking` unconditionally would change
        # every other game's output -- must stay byte-identical for games
        # with no ChangePortrait usage at all (portrait_defs empty/None).
        labels = [("start", [_say("e", "Hi there.")])]
        text, _flagged = emit_script_vnds(labels, characters={"e": CharacterDef(varname="e", display_name="Eileen", color=None, loc=LOC)})
        assert "speaking" not in text
