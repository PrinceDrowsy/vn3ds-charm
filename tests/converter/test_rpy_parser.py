import pytest

from converter.parser import (
    Call,
    DayCard,
    FrameAsset,
    Hide,
    If,
    Jump,
    Label,
    Menu,
    Pause,
    Placeholder,
    Play,
    PortraitUpdate,
    Return,
    ResetAudio,
    Say,
    Scene,
    ScreenBox,
    ScreenButton,
    ScreenHotspot,
    ScreenIf,
    ScreenImagemap,
    ScreenText,
    Set,
    SetVolume,
    Show,
    SpriteLayerCategories,
    Stop,
    SubchapterCard,
    SubchapterHide,
    TheEndCard,
    Transition,
    Unsupported,
    While,
    Window,
    parse_rpy,
    scan_screen_resolution,
    scan_transform_declarations,
)


def test_label_jump_call_return():
    source = """
    label start:
        jump next

    label next:
        call helper
        return

    label helper:
        return
    """
    script, problems = parse_rpy(source)
    assert problems == []
    names = [label.name for label in script.labels]
    assert names == ["start", "next", "helper"]

    start_body = script.labels[0].body
    assert len(start_body) == 1
    assert isinstance(start_body[0], Jump)
    assert start_body[0].target == "next"

    next_body = script.labels[1].body
    assert isinstance(next_body[0], Call)
    assert next_body[0].target == "helper"
    assert isinstance(next_body[1], Return)


def test_flat_unindented_label_body():
    # real Ren'Py never requires a label's body to be indented (unlike
    # if/menu/while/python, its own lexer never calls expect_block for
    # `label`) -- confirmed real content: Gender Bender DNA Twister
    # Extreme writes 14 of its 18 story files with zero indentation
    # anywhere, every statement (including everything "under" a label) at
    # column 0.
    source = """label start:
jump next

label next:
call helper
return

label helper:
return
"""
    script, problems = parse_rpy(source)
    assert problems == []
    names = [label.name for label in script.labels]
    assert names == ["start", "next", "helper"]

    start_body = script.labels[0].body
    assert len(start_body) == 1
    assert isinstance(start_body[0], Jump)
    assert start_body[0].target == "next"

    next_body = script.labels[1].body
    assert len(next_body) == 2
    assert isinstance(next_body[0], Call)
    assert next_body[0].target == "helper"
    assert isinstance(next_body[1], Return)


def test_flat_unindented_label_with_no_statements_before_next_label():
    source = """label a:
label b:
jump a
"""
    script, problems = parse_rpy(source)
    assert problems == []
    assert script.labels[0].name == "a"
    assert script.labels[0].body == []
    assert script.labels[1].name == "b"
    assert len(script.labels[1].body) == 1
    assert isinstance(script.labels[1].body[0], Jump)


def test_flat_unindented_nested_label():
    # same bug pattern, reached via _parse_statement's own nested-label
    # handling (a label appearing inside another block's indented body)
    # rather than parse_rpy's top-level loop.
    source = """label outer:
    if True:
        label inner:
        jump elsewhere
    jump elsewhere
"""
    script, problems = parse_rpy(source)
    assert problems == []
    outer_body = script.labels[0].body
    if_node = outer_body[0]
    inner_label = if_node.branches[0].body[0]
    assert isinstance(inner_label, Label)
    assert inner_label.name == "inner"
    assert len(inner_label.body) == 1
    assert isinstance(inner_label.body[0], Jump)


def test_scene_show_hide_with_position_and_transition():
    source = """
    label start:
        scene bg cafe with dissolve
        show eileen happy at left with dissolve
        hide eileen with dissolve
    """
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body

    scene = body[0]
    assert isinstance(scene, Scene)
    assert scene.image == "bg cafe"
    assert scene.position is None
    assert scene.transition == "dissolve"

    show = body[1]
    assert isinstance(show, Show)
    assert show.image == "eileen happy"
    assert show.position == "left"
    assert show.transition == "dissolve"

    hide = body[2]
    assert isinstance(hide, Hide)
    assert hide.image == "eileen"
    assert hide.transition == "dissolve"


def test_show_atl_block_with_static_xalign_yalign():
    source = """
    label start:
        show jennifer a01 worried:
            xalign 0.0
        show coffeeshop bw:
            zoom 1.0 alpha 1.0 xalign .5 yalign .5
    """
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body

    show1 = body[0]
    assert isinstance(show1, Show)
    assert show1.xalign == 0.0
    assert show1.yalign is None
    assert show1.approximated_atl is False  # no timing/zoom/alpha in *this* line's static values

    show2 = body[1]
    assert show2.xalign == 0.5
    assert show2.yalign == 0.5
    # static zoom/alpha are now genuinely applied (sx/sy/alpha on the Show
    # node, actually rendered via the engine's per-sprite animation state)
    # rather than silently discarded, so this is no longer approximated.
    assert show2.approximated_atl is False
    assert show2.sx == 1.0
    assert show2.sy == 1.0
    assert show2.alpha == 1.0


def test_show_atl_block_with_timed_tween_approximates_to_final_state():
    source = """
    label start:
        show coffeeshop bw:
            zoom 1.0 alpha 1.0 xalign .5 yalign .5
            linear .7 alpha 0.0 zoom 2.0
    """
    script, problems = parse_rpy(source)
    assert problems == []
    show = script.labels[0].body[0]
    assert isinstance(show, Show)
    assert show.xalign == 0.5
    assert show.yalign == 0.5
    assert show.approximated_atl is True
    # a single step touching both alpha and zoom together doesn't match
    # either exact fade preset -- falls back to the general keyframe form.
    assert show.anim is not None
    assert show.anim.preset is None
    assert show.anim.keyframes is not None


def test_atl_fade_in_matches_enter_fade_preset_exactly():
    # VN3DS-spec.md §9.1's own called-out case: alpha 0 -> alpha 1, nothing
    # else -- an exact preset match, not flagged approximated.
    source = """
    label start:
        show eileen happy:
            alpha 0.0
            linear 0.3 alpha 1.0
    """
    script, problems = parse_rpy(source)
    assert problems == []
    show = script.labels[0].body[0]
    assert show.approximated_atl is False
    assert show.anim.preset == "enter_fade"
    assert show.anim.duration == 0.3
    assert show.anim.keyframes is None


def test_atl_fade_out_matches_exit_fade_preset_exactly():
    source = """
    label start:
        show eileen happy:
            linear 0.4 alpha 0.0
    """
    script, problems = parse_rpy(source)
    assert problems == []
    show = script.labels[0].body[0]
    assert show.approximated_atl is False
    assert show.anim.preset == "exit_fade"
    assert show.anim.duration == 0.4


def test_atl_multi_step_position_tween_falls_back_to_keyframes():
    source = """
    label start:
        show eileen happy:
            xalign 0.0 alpha 0.0
            linear 0.5 xalign 0.5 alpha 1.0
            linear 0.5 xalign 0.5 yalign 0.1
    """
    script, problems = parse_rpy(source)
    assert problems == []
    show = script.labels[0].body[0]
    assert show.approximated_atl is True
    anim = show.anim
    assert anim.preset is None
    assert anim.duration == 1.0
    assert len(anim.keyframes) == 3
    t0, props0 = anim.keyframes[0]
    assert t0 == 0.0
    assert props0 == {"x": 0.0, "alpha": 0.0}
    t1, props1 = anim.keyframes[1]
    assert t1 == 0.5
    assert props1 == {"x": 200.0, "alpha": 1.0}
    t2, props2 = anim.keyframes[2]
    assert t2 == 1.0
    # yalign is emitted as a raw 0.0-1.0 fraction, not pre-baked to a pixel
    # "y" -- see _atl_prop_to_engine's docstring: the sprite's actual
    # rendered height (needed to convert it correctly) isn't known until
    # the asset pipeline resolves the real image, long after this parses.
    assert props2 == {"x": 200.0, "yalign": 0.1}


def test_atl_block_touching_python_is_flagged_even_with_a_matched_shape():
    source = """
    label start:
        show eileen happy:
            alpha 0.0
            if True:
                pass
            linear 0.3 alpha 1.0
    """
    script, problems = parse_rpy(source)
    show = script.labels[0].body[0]
    assert show.approximated_atl is True
    assert show.anim.preset is None
    assert show.anim.keyframes is not None


def test_scene_atl_block_with_no_position_is_flagged():
    # `scene` (unlike `show`) has no animation path at all -- Scene.anim
    # doesn't exist, so a scene ATL block with nothing but a timed step and
    # no xalign/yalign is still entirely unconvertible.
    source = """
    label start:
        scene foo:
            linear 0.5 alpha 0.5
    """
    script, problems = parse_rpy(source)
    assert len(problems) == 1
    assert problems[0].reason == "ATL block has no recognizable static/final position (xalign/yalign)"


def test_show_atl_block_with_animation_but_no_position_is_not_flagged_unsupported():
    # regression: a show ATL block with a real animation and no explicit
    # position used to be rejected outright (Unsupported) purely because
    # it lacked xalign/yalign -- now that animation-only ATL is
    # convertible, it should parse into a real Show with an anim, not be
    # thrown away.
    source = """
    label start:
        show foo:
            linear 0.5 alpha 0.5
    """
    script, problems = parse_rpy(source)
    assert problems == []
    show = script.labels[0].body[0]
    assert isinstance(show, Show)
    assert show.xalign is None
    assert show.yalign is None
    assert show.approximated_atl is True
    assert show.anim is not None
    assert show.anim.keyframes is not None


def test_scan_transform_declarations_captures_body_lines():
    source = """
    transform bs_centerleft3:
        xcenter 0.55 yalign 1.0 ypos 1.3 zoom 1.1

    transform faceleft:
        xzoom -1.0
    """
    transforms = scan_transform_declarations(source)
    assert transforms["bs_centerleft3"] == ["xcenter 0.55 yalign 1.0 ypos 1.3 zoom 1.1"]
    assert transforms["faceleft"] == ["xzoom -1.0"]


def test_transform_declaration_is_not_flagged_as_unsupported():
    # Previously every `transform NAME:` fell through to the generic
    # "unsupported top-level statement" handling -- real content (Mice
    # Tea's transforms.rpy) has 348 of these in one file alone. The
    # declaration itself carries no problem; fidelity/approximation is
    # judged at each usage site instead.
    source = """
    transform bs_centerleft3:
        xcenter 0.55 yalign 1.0 ypos 1.3 zoom 1.1

    label start:
        return
    """
    script, problems = parse_rpy(source)
    assert problems == []
    assert script.labels[0].name == "start"


def test_show_block_with_bare_transform_name_lines_resolves_position_and_zoom():
    # Real Mice Tea usage (story/afd/afd_23.rpy): a `show X:` block whose
    # only content is one or more bare transform-name lines, composing a
    # position preset with a face-direction flip -- confirmed the dominant
    # real-world pattern (~1737 sites) for how this game positions sprites.
    source = """
    transform bs_centerleft3:
        xcenter 0.55 yalign 1.0 ypos 1.3 zoom 1.1

    transform faceleft:
        xzoom -1.0

    label start:
        show afd_l neutral faceleft:
            bs_centerleft3
            faceleft
    """
    transforms = scan_transform_declarations(source)
    script, problems = parse_rpy(source, transforms=transforms)
    assert problems == []
    show = script.labels[0].body[0]
    assert isinstance(show, Show)
    assert show.xalign == 0.55
    assert show.yalign == 1.3
    assert show.yanchor == 1.0
    assert show.sx == -1.0
    assert show.sy == 1.1
    assert show.approximated_atl is False


def test_at_clause_with_comma_separated_transform_names_resolves_both():
    # Real Mice Tea usage (story/day1.rpy): `at NAME1, NAME2` composing a
    # position preset with a face-direction flip via the `at` clause itself
    # rather than an indented block.
    source = """
    transform offscreenright_male:
        xcenter 1.2 yalign 1.0 ypos 1.25 zoom 1.0

    transform faceleft:
        xzoom -1.0

    label start:
        show gavin neutral faceleft at offscreenright_male, faceleft
    """
    transforms = scan_transform_declarations(source)
    script, problems = parse_rpy(source, transforms=transforms)
    assert problems == []
    show = script.labels[0].body[0]
    assert isinstance(show, Show)
    assert show.xalign == 1.2
    assert show.yalign == 1.25
    # faceleft's xzoom applies *after* offscreenright_male's own zoom (last
    # value wins, matching real ATL composition order) -- listing the face
    # flip last is exactly why real content orders it that way.
    assert show.sx == -1.0


def test_at_clause_names_combine_with_a_following_atl_block():
    # Real Mice Tea usage (story/day1.rpy:980): the `at` clause supplies a
    # base state, and the indented block's own lines override on top of it
    # -- Ren'Py's real "base state, then overrides" order.
    source = """
    transform faceleft:
        xzoom -1.0

    transform offscreenright_male:
        xcenter 1.2 yalign 1.0 ypos 1.25 zoom 1.0

    label start:
        show gavin neutral faceleft at faceleft, offscreenright_male:
            xcenter 1.4
    """
    transforms = scan_transform_declarations(source)
    script, problems = parse_rpy(source, transforms=transforms)
    assert problems == []
    show = script.labels[0].body[0]
    assert isinstance(show, Show)
    assert show.xalign == 1.4  # overridden by the block, not the at-clause's 1.2
    assert show.yalign == 1.25  # untouched by the block, still from the at-clause


def test_transform_composed_with_a_repeating_animated_transform_stays_approximated():
    # `fidget`-style transforms (timed steps + `repeat`) are out of scope
    # (the engine's animation system has no loop concept and these use
    # relative xoffset/yoffset, which isn't modeled at all) -- but a real
    # scene composing one of these with a real positional transform should
    # still resolve the static base position, only flagging the animated
    # part as approximated rather than losing the position too.
    source = """
    transform bs_center:
        xcenter 0.5 yalign 1.0 ypos 1.2 zoom 1.1

    transform fidget:
        ease .4 yoffset -1 xoffset 3
        ease .4 yoffset 1 xoffset 2
        repeat

    label start:
        show afd_l neutral:
            bs_center
            fidget
    """
    transforms = scan_transform_declarations(source)
    script, problems = parse_rpy(source, transforms=transforms)
    assert problems == []
    show = script.labels[0].body[0]
    assert isinstance(show, Show)
    assert show.xalign == 0.5
    assert show.yalign == 1.2
    assert show.approximated_atl is True


def test_yalign_then_ypos_override_keeps_distinct_yanchor():
    # Real Mice Tea transform shape (transforms.rpy): `yalign 1.0` sets both
    # the anchor and position fractions to 1.0 as a shorthand, but a
    # subsequent `ypos` override only moves the *position* -- the anchor
    # must stay at 1.0, not silently follow ypos to the same value.
    source = """
    label start:
        show afd_l neutral:
            yalign 1.0
            ypos 1.2
    """
    script, problems = parse_rpy(source)
    assert problems == []
    show = script.labels[0].body[0]
    assert show.yalign == 1.2
    assert show.yanchor == 1.0


def test_standalone_with_transition():
    source = """
    label start:
        scene bg cafe
        with fade
    """
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body
    assert isinstance(body[1], Transition)
    assert body[1].name == "fade"


def test_standalone_with_none_is_a_harmless_no_op_not_a_transition():
    # Ren'Py's own idiom for "explicitly no transition" (real content: 153
    # uses in Mice Tea alone) -- must not be treated as an unrecognized
    # transition *name* (which would downgrade to a real dissolve/fade now
    # that transitions actually do something on hardware).
    source = """
    label start:
        scene bg cafe
        with None
    """
    script, problems = parse_rpy(source)
    body = script.labels[0].body
    assert not any(isinstance(node, Transition) for node in body)
    assert len(problems) == 1
    assert "with None" in problems[0].reason


def test_inline_with_none_is_not_treated_as_a_transition():
    source = """
    label start:
        hide eileen with None
    """
    script, problems = parse_rpy(source)
    assert problems == []
    hide = script.labels[0].body[0]
    assert hide.transition is None


def test_play_stop_queue_and_pause():
    source = """
    label start:
        play music "illurock.opus"
        play sound "click.ogg"
        play voice "line1.ogg"
        queue music "next.ogg"
        stop music
        stop sound
        stop voice
        pause
        pause 1.5
    """
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body

    assert body[0] == Play(channel="music", file="illurock.opus", is_queue=False, loc=body[0].loc)
    assert body[1] == Play(channel="sound", file="click.ogg", is_queue=False, loc=body[1].loc)
    assert body[2] == Play(channel="voice", file="line1.ogg", is_queue=False, loc=body[2].loc)
    assert body[3] == Play(channel="music", file="next.ogg", is_queue=True, loc=body[3].loc)
    assert body[4] == Stop(channel="music", loc=body[4].loc)
    assert body[5] == Stop(channel="sound", loc=body[5].loc)
    assert body[6] == Stop(channel="voice", loc=body[6].loc)
    assert body[7] == Pause(seconds=None, loc=body[7].loc)
    assert body[8] == Pause(seconds=1.5, loc=body[8].loc)


def test_bare_voice_statement_is_a_play_not_dialogue():
    # regression: Ren'Py's common `voice "path.ogg"` form (no "play"/"queue"
    # prefix) used to fall through to the Say-line regex, which happily
    # matched it as character "voice" saying the literal file path as
    # dialogue -- confirmed on real hardware with Jisei, where every voiced
    # line showed its own audio file path as if a character named "voice"
    # said it, and no audio ever played.
    source = """
    label start:
        voice "audio/v/line1.ogg"
        c2 "How's it going?"
    """
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body
    assert body[0] == Play(channel="voice", file="audio/v/line1.ogg", is_queue=False, loc=body[0].loc)
    assert isinstance(body[1], Say)
    assert body[1].who == "c2"
    assert body[1].what == "How's it going?"


def test_play_resolves_a_bare_identifier_against_a_top_level_define():
    # real content (Mice Tea): `play sound sfx_paper` where
    # `sfx_paper` is `define`d elsewhere as a literal path -- not a
    # literal string at the play site itself.
    source = """
    define sfx_paper = "audio/sfx/magazine1.mp3"

    label start:
        play sound sfx_paper
    """
    script, problems = parse_rpy(source)
    assert problems == []
    show = script.labels[0].body[0]
    assert show == Play(channel="sound", file="audio/sfx/magazine1.mp3", is_queue=False, loc=show.loc)


def test_play_resolves_a_bare_identifier_via_prescanned_string_defines():
    # the dominant real-world shape: the alias is declared inside an
    # `init python:` block (Mice Tea's screens/music.rpy declares every
    # `sfx_X = "audio/..."` this way, not via `define`), and/or in a
    # different file than the one using it bare -- both handled by the
    # game-wide `scan_string_defines` prepass, threaded in here the same
    # way `parse_game` does across files.
    source = """
    label start:
        play sound sfx_paper
    """
    string_defines = {"sfx_paper": "audio/sfx/magazine1.mp3"}
    script, problems = parse_rpy(source, string_defines=string_defines)
    assert problems == []
    show = script.labels[0].body[0]
    assert show == Play(channel="sound", file="audio/sfx/magazine1.mp3", is_queue=False, loc=show.loc)


def test_play_bare_identifier_with_no_known_define_is_used_as_is():
    # an unresolvable bare name is used as-is (a visibly wrong path is a
    # more honest failure than silently dropping the cue).
    source = """
    label start:
        play sound sfx_unknown
    """
    script, problems = parse_rpy(source)
    assert problems == []
    show = script.labels[0].body[0]
    assert show.file == "sfx_unknown"


def test_play_bracket_list_resolves_to_random_choices_dropping_silence_entries():
    # real content (Mice Tea): `play sound [a, "<silence 0.5>", b]` --
    # Ren'Py's randomized-file-choice idiom. The silence pseudo-entry is
    # a timing gap, not a real file, and is dropped.
    source = """
    define sfx_camera_fast = "audio/sfx/camera_fast.ogg"

    label start:
        play sound [sfx_camera_fast, "<silence 0.5>", "audio/sfx/camera_slow.ogg"]
    """
    script, problems = parse_rpy(source)
    assert problems == []
    show = script.labels[0].body[0]
    assert isinstance(show, Play)
    assert show.choices == ["audio/sfx/camera_fast.ogg", "audio/sfx/camera_slow.ogg"]
    assert show.file == "audio/sfx/camera_fast.ogg"


def test_play_bracket_list_with_a_single_real_entry_is_a_plain_play():
    source = """
    label start:
        play sound ["<silence 1.0>", "audio/sfx/cat_bell.ogg"]
    """
    script, problems = parse_rpy(source)
    assert problems == []
    show = script.labels[0].body[0]
    assert show == Play(channel="sound", file="audio/sfx/cat_bell.ogg", is_queue=False, loc=show.loc)


def test_play_recognizes_audio_and_ambiance_channels():
    # "audio" (Ren'Py's built-in one-shot channel) and "ambiance" (a real
    # custom channel registered via renpy.music.register_channel) both
    # used to be entirely unrecognized -- the old regex only matched
    # music/sound/voice.
    source = """
    label start:
        play audio "audio/sfx/powerswitch_01.ogg"
        play ambiance amb_subway
        stop ambiance
    """
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body
    assert body[0] == Play(channel="audio", file="audio/sfx/powerswitch_01.ogg", is_queue=False, loc=body[0].loc)
    assert body[1] == Play(channel="ambiance", file="amb_subway", is_queue=False, loc=body[1].loc)
    assert body[2] == Stop(channel="ambiance", loc=body[2].loc)


def test_renpy_music_play_resolves_a_bare_identifier_and_channel_kwarg():
    # real content (Mice Tea): `$ renpy.music.play(music_from_within,
    # fadein=1.0, synchro_start=True, channel='music2')` -- a Python call
    # doing via `$` what the declarative `play` statement does. fadein/
    # synchro_start have no VNDS equivalent and are silently dropped, same
    # as the declarative `play ... fadein N` form already does.
    source = """
    define music_from_within = "audio/music/from_within.ogg"

    label start:
        $ renpy.music.play(music_from_within, fadein=1.0, synchro_start=True, channel='music2')
    """
    script, problems = parse_rpy(source)
    assert problems == []
    play = script.labels[0].body[0]
    assert play == Play(channel="music2", file="audio/music/from_within.ogg", is_queue=False, loc=play.loc)


def test_renpy_music_play_defaults_to_the_music_channel():
    source = """
    label start:
        $ renpy.music.play("audio/music/theme.ogg")
    """
    script, problems = parse_rpy(source)
    assert problems == []
    play = script.labels[0].body[0]
    assert play == Play(channel="music", file="audio/music/theme.ogg", is_queue=False, loc=play.loc)


def test_renpy_music_stop_resolves_channel_kwarg():
    source = """
    label start:
        $ renpy.music.stop(channel='music2', fadeout=1.0)
    """
    script, problems = parse_rpy(source)
    assert problems == []
    stop = script.labels[0].body[0]
    assert stop == Stop(channel="music2", loc=stop.loc)


def test_renpy_music_set_volume_becomes_a_real_setvolume_node():
    # a genuine engine feature (audio.moon fades the channel's volume),
    # not an approximation -- real content (Mice Tea's reset_audio/
    # crossfade logic) uses this heavily.
    source = """
    label start:
        $ renpy.music.set_volume(0.0, delay=3.0, channel='music2')
    """
    script, problems = parse_rpy(source)
    assert problems == []
    node = script.labels[0].body[0]
    assert isinstance(node, SetVolume)
    assert node.channel == "music2"
    assert node.level == 0.0
    assert node.delay == 3.0


def test_renpy_music_set_volume_defaults_channel_and_delay():
    source = """
    label start:
        $ renpy.music.set_volume(1.0)
    """
    script, problems = parse_rpy(source)
    assert problems == []
    node = script.labels[0].body[0]
    assert isinstance(node, SetVolume)
    assert node.channel == "music"
    assert node.level == 1.0
    assert node.delay == 0.0


def test_day_statement_parses_number_subtitle_and_mood():
    # real content (Mice Tea's statements.rpy): `day "N" "subtitle"
    # ["mood"]`, a custom Ren'Py statement registered via
    # renpy.statements.register.
    source = '''
    label start:
        day "32" "Routines" "sad"
    '''
    script, problems = parse_rpy(source)
    assert problems == []
    node = script.labels[0].body[0]
    assert isinstance(node, DayCard)
    assert node.day_number == "32"
    assert node.subtitle == "Routines"
    assert node.mood == "sad"


def test_day_statement_mood_defaults_to_default_when_omitted():
    source = '''
    label start:
        day "1" "A New Topic"
    '''
    script, problems = parse_rpy(source)
    assert problems == []
    node = script.labels[0].body[0]
    assert node.mood == "default"


def test_subchapter_statement_parses_the_message():
    source = '''
    label start:
        subchapter "{noalt}Routines{/noalt}"
    '''
    script, problems = parse_rpy(source)
    assert problems == []
    node = script.labels[0].body[0]
    assert isinstance(node, SubchapterCard)
    assert node.message == "{noalt}Routines{/noalt}"


def test_subchapter_hide_and_reset_audio_take_no_arguments():
    source = '''
    label start:
        subchapter_hide
        reset_audio
    '''
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body
    assert isinstance(body[0], SubchapterHide)
    assert isinstance(body[1], ResetAudio)


def test_the_end_statement_parses_the_title():
    source = '''
    label start:
        the_end "The Beginning of Something New"
    '''
    script, problems = parse_rpy(source)
    assert problems == []
    node = script.labels[0].body[0]
    assert isinstance(node, TheEndCard)
    assert node.title == "The Beginning of Something New"


def test_placeholder_statement_with_and_without_an_argument():
    source = '''
    label start:
        placeholder
        placeholder wip
    '''
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body
    assert isinstance(body[0], Placeholder)
    assert isinstance(body[1], Placeholder)


def test_renpy_pause_function_form_converts_like_bare_pause():
    source = """
    label start:
        $ renpy.pause(0.7)
        $ renpy.pause()
    """
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body
    assert body[0] == Pause(seconds=0.7, loc=body[0].loc)
    assert body[1] == Pause(seconds=None, loc=body[1].loc)


def test_renpy_block_rollback_is_a_flagged_noop():
    source = """
    label start:
        $ renpy.block_rollback()
    """
    script, problems = parse_rpy(source)
    assert len(problems) == 1
    assert problems[0].reason == "renpy.block_rollback() is a no-op (rollback isn't implemented yet)"


def test_bare_variable_reference_is_a_flagged_noop():
    source = """
    label start:
        $ kan_mouth
    """
    script, problems = parse_rpy(source)
    assert len(problems) == 1
    assert problems[0].reason == "bare variable reference has no effect, treated as a no-op"


def test_movie_cutscene_is_flagged_video():
    source = """
    label start:
        $ renpy.movie_cutscene("op.ogv")
    """
    script, problems = parse_rpy(source)
    assert len(problems) == 1
    assert problems[0].reason == "movie/video playback has no VNDS equivalent (needs native reimplementation)"


def test_custom_transition_definition_is_flagged_approximated():
    source = """
    define wipedown = CropMove(0.5, "wipedown")

    label start:
        "Hi."
    """
    script, problems = parse_rpy(source)
    assert script.top_level_sets == []
    assert len(problems) == 1
    assert problems[0].reason == "custom transition definition has no VNDS equivalent (any use already downgrades to a plain dissolve)"


def test_atl_negative_xalign_is_recognized():
    source = """
    label start:
        show jennifer a01 blunt02:
            xalign -0.05
    """
    script, problems = parse_rpy(source)
    assert problems == []
    show = script.labels[0].body[0]
    assert show.xalign == -0.05


def test_scan_screen_resolution_finds_direct_config_assignment():
    source = """
    init python:
        config.screen_width = 1024
        config.screen_height = 768
    """
    assert scan_screen_resolution(source) == (1024, 768)


def test_scan_screen_resolution_finds_gui_init_call():
    source = 'init python:\n    gui.init(1920, 1080)\n'
    assert scan_screen_resolution(source) == (1920, 1080)


def test_scan_screen_resolution_returns_none_when_undeclared():
    source = 'label start:\n    "Hi."\n'
    assert scan_screen_resolution(source) is None


def test_bare_int_ypos_rescales_using_the_games_own_declared_resolution():
    # real-hardware-relevant regression: Jisei declares 1024x768 and uses
    # bare-int (absolute-pixel) ypos/xpos throughout -- previously treated
    # as if it were already a 0.0-1.0 fraction of the *target* 400x240
    # space, computing wildly out-of-range values (651 * 240 = 156240).
    # Ren'Py's real rule: a bare int is an absolute pixel offset in the
    # game's own declared resolution; only a float is a fraction.
    source = """
    label start:
        show jennifer a01:
            xpos 680 ypos 651
    """
    script, problems = parse_rpy(source, screen_resolution=(1024, 768))
    assert problems == []
    show = script.labels[0].body[0]
    assert show.xalign == pytest.approx(680 / 1024)
    assert show.yalign == pytest.approx(651 / 768)


def test_float_xalign_yalign_unaffected_by_screen_resolution():
    # regression: a float literal is already a fraction (Ren'Py's real
    # rule) and must never be rescaled, regardless of the game's declared
    # resolution -- this is the dominant, most common real-content case
    # and must stay byte-identical to existing behavior.
    source = """
    label start:
        show jennifer a01:
            xalign 0.5 yalign 0.25
    """
    script, problems = parse_rpy(source, screen_resolution=(1024, 768))
    assert problems == []
    show = script.labels[0].body[0]
    assert show.xalign == 0.5
    assert show.yalign == 0.25


def test_bare_negative_int_ypos_rescales_correctly():
    source = """
    label start:
        show jennifer a01:
            ypos -40
    """
    script, problems = parse_rpy(source, screen_resolution=(1440, 900))
    assert problems == []
    show = script.labels[0].body[0]
    assert show.yalign == pytest.approx(-40 / 900)


def test_bare_int_atl_position_falls_back_to_800x600_when_resolution_undeclared():
    # no screen_resolution passed at all (matches every existing caller/
    # test that predates this feature) -- must not crash, and uses Ren'Py's
    # own historical pre-GUI-template engine default as the denominator.
    source = """
    label start:
        show jennifer a01:
            xpos 400
    """
    script, problems = parse_rpy(source)
    assert problems == []
    show = script.labels[0].body[0]
    assert show.xalign == pytest.approx(400 / 800)


def test_bare_int_position_in_a_timed_atl_animation_also_rescales():
    # the *animated* keyframe path (_parse_atl_animation) parses ATL
    # properties independently from the static path -- must get the same
    # int-vs-float treatment, not just the static one.
    source = """
    label start:
        show jennifer a01:
            xpos 0 ypos 0
            linear 0.5 xpos 512 ypos 384
    """
    script, problems = parse_rpy(source, screen_resolution=(1024, 768))
    assert problems == []
    show = script.labels[0].body[0]
    assert show.anim is not None
    assert show.anim.keyframes[0][1]["x"] == pytest.approx(0.0)
    assert show.anim.keyframes[1][1]["x"] == pytest.approx(round((512 / 1024) * 400, 2))


def test_persistent_assignment_resolves_to_a_flat_global_achievement_still_flagged():
    # persistent.X is now resolved into a real, readable global (VNDS has
    # no cross-save persistence, but a plain global is a faithful
    # within-playthrough equivalent -- see _render_expr's own docstring).
    # achievement.* has no equivalent at all and stays flagged.
    source = """
    label start:
        $ persistent.naoki = True
        $ achievement.grant("ACHIEVEMENT_X")
    """
    script, problems = parse_rpy(source)
    assert len(problems) == 1
    assert problems[0].reason == "persistent/achievement API has no VNDS equivalent (needs native reimplementation)"
    set_node = script.labels[0].body[0]
    assert isinstance(set_node, Set)
    assert set_node.var == "persistent_naoki"
    assert set_node.expr == "True"


def test_say_narrator_named_var_and_anonymous():
    source = """
    label start:
        "A narrator line."
        e "A line from a Character() variable."
        "Anonymous Name" "A line with a literal speaker name."
    """
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body

    narrator = body[0]
    assert isinstance(narrator, Say)
    assert narrator.who is None
    assert narrator.what == "A narrator line."

    named_var = body[1]
    assert isinstance(named_var, Say)
    assert named_var.who == "e"
    assert named_var.what == "A line from a Character() variable."

    anonymous = body[2]
    assert isinstance(anonymous, Say)
    assert anonymous.who == "Anonymous Name"
    assert anonymous.what == "A line with a literal speaker name."


def test_character_definition():
    source = '''
    define e = Character("Eileen", color="#c8ffc8")

    label start:
        e "Hello!"
    '''
    script, problems = parse_rpy(source)
    assert problems == []
    assert "e" in script.characters
    assert script.characters["e"].display_name == "Eileen"
    assert script.characters["e"].color == "#c8ffc8"


def test_character_definition_with_explicit_none_is_a_valid_narrator():
    # Character(None, ...) is a deliberate Ren'Py idiom for a styled but
    # nameless narrator (e.g. a color/ctc-only character) -- not a parse
    # failure, and must not show a literal "narrator" nameplate.
    source = '''
    define narrator = Character(None, color="#ffffff")

    label start:
        narrator "Some text."
    '''
    script, problems = parse_rpy(source)
    assert problems == []
    assert script.characters["narrator"].display_name is None
    assert script.characters["narrator"].color == "#ffffff"


def test_character_definition_with_translation_wrapper():
    source = '''
    define e = Character(_("Eileen"), color="#c8ffc8")
    '''
    script, problems = parse_rpy(source)
    assert problems == []
    assert script.characters["e"].display_name == "Eileen"


def test_dynamic_character_resolves_via_string_define():
    source = '''
    define chancename = "Girl"
    define c = DynamicCharacter("chancename", color="#fff")
    define bad = DynamicCharacter("unknownvar")
    '''
    script, problems = parse_rpy(source)
    assert script.characters["c"].display_name == "Girl"
    assert "bad" not in script.characters
    reasons = [p.reason for p in problems]
    assert "DynamicCharacter approximated with its current default display name" in reasons
    assert "DynamicCharacter's name variable could not be resolved to a literal string" in reasons


def test_parse_rpy_recovers_the_games_default_font_from_inside_an_init_python_block():
    # `style.default.font = "..."` (Jisei's real options.rpy) sits inside
    # `init -1 python hide:` -- arbitrary Python, otherwise entirely
    # unparsed -- so this is deliberately recovered by a standalone scan
    # over the raw source, independent of the statement-by-statement
    # parser/block structure, the same way _record_string_define already
    # opportunistically scans for `define name = "literal"`.
    source = '''
    init -1 python hide:

        config.screen_width = 1024
        config.screen_height = 768

        style.default.font = "gui/HanSrf.ttf"
        style.default.size = 25

    label start:
        return
    '''
    script, _problems = parse_rpy(source)
    assert script.default_font == "gui/HanSrf.ttf"


def test_parse_rpy_default_font_is_none_when_not_declared():
    script, _problems = parse_rpy('label start:\n    return\n')
    assert script.default_font is None


def test_parse_rpy_recovers_default_font_from_gui_default_font_define():
    # Mice Tea's gui.rpy (Ren'Py's standard GUI-customization template) has
    # no `style.default.font` line at all -- it declares the dialogue font
    # via the template's own `define gui.default_font = "..."` variable
    # instead. Same purpose, different name, so this must resolve too.
    source = '''
    define gui.default_font = "VarelaRound.ttf"
    define gui.name_font = "BerkshireSwash.ttf"

    label start:
        return
    '''
    script, _problems = parse_rpy(source)
    assert script.default_font == "VarelaRound.ttf"


def test_parse_rpy_recovers_default_text_cps_from_inside_an_init_python_block():
    # Jisei's real options.rpy: `config.default_text_cps = 35` -- a static,
    # game-wide typewriter speed (not `preferences.text_cps`, a
    # runtime-adjustable user setting some games instead default to 0/off
    # and let the player change via an options menu -- out of scope, see
    # ir.py's Script.default_text_cps docstring).
    source = '''
    init python:
        config.default_text_cps = 35

    label start:
        return
    '''
    script, _problems = parse_rpy(source)
    assert script.default_text_cps == 35.0


def test_parse_rpy_default_text_cps_is_none_when_not_declared():
    script, _problems = parse_rpy('label start:\n    return\n')
    assert script.default_text_cps is None


def test_parse_rpy_recovers_default_text_cps_from_the_shorter_config_text_cps_form():
    source = 'init python:\n    config.text_cps = 42\n'
    script, _problems = parse_rpy(source)
    assert script.default_text_cps == 42.0


def test_parse_rpy_recovers_textbox_image_modern_form():
    source = 'screen say(who, what):\n    window:\n        background Image("gui/textbox.png", xalign=0.5, yalign=1.0)\n'
    script, _problems = parse_rpy(source)
    assert script.textbox_image == "gui/textbox.png"


def test_parse_rpy_recovers_textbox_image_legacy_form():
    source = 'init python:\n    style.window.background = "gui/textbox.png"\n'
    script, _problems = parse_rpy(source)
    assert script.textbox_image == "gui/textbox.png"


def test_parse_rpy_textbox_image_is_none_when_not_declared():
    script, _problems = parse_rpy('label start:\n    return\n')
    assert script.textbox_image is None


def test_parse_rpy_recovers_namebox_frame_modern_form_with_real_tiling():
    source = '''
    init python:
        define gui.namebox_borders = Borders(5, 5, 5, 5)
        define gui.namebox_tile = True

    screen say(who, what):
        window:
            background Frame("gui/namebox/namebox.png", gui.namebox_borders, tile=gui.namebox_tile)
    '''
    script, _problems = parse_rpy(source)
    assert script.namebox == FrameAsset(image="gui/namebox/namebox.png", borders=(5, 5, 5, 5), tile=True)


def test_parse_rpy_recovers_namebox_frame_legacy_form():
    source = 'init python:\n    style.say_who_window.background = Frame("gui/namebox.png", 16, 16)\n'
    script, _problems = parse_rpy(source)
    assert script.namebox == FrameAsset(image="gui/namebox.png", borders=(16, 16, 16, 16), tile=False)


def test_parse_rpy_recovers_namebox_bare_image_legacy_form():
    # confirmed real content: Jisei's namebox has no Frame() wrapper at all
    # -- a plain image, borders all-zero (draw_frame's degenerate case).
    source = 'init python:\n    style.say_who_window.background = "gui/namebox.png"\n'
    script, _problems = parse_rpy(source)
    assert script.namebox == FrameAsset(image="gui/namebox.png", borders=(0, 0, 0, 0), tile=False)


def test_parse_rpy_namebox_is_none_when_not_declared():
    script, _problems = parse_rpy('label start:\n    return\n')
    assert script.namebox is None


def test_parse_rpy_recovers_choice_button_frames_modern_form_via_well_known_paths():
    # Ren'Py's modern gui.rpy template routes the actual choice-button
    # image path through its own internal gui.button_properties() helper
    # -- never mentioned literally in the game's own source -- so this is
    # detected via gui.choice_button_borders' presence and resolved to
    # Ren'Py's own fixed, non-game-specific filenames.
    source = '''
    init python:
        define gui.choice_button_borders = Borders(150, 22, 150, 8)
        define gui.choice_button_tile = False
    '''
    script, _problems = parse_rpy(source)
    assert script.choice_idle == FrameAsset(
        image="gui/button/choice_idle_background.png", borders=(150, 22, 150, 8), tile=False
    )
    assert script.choice_hover == FrameAsset(
        image="gui/button/choice_hover_background.png", borders=(150, 22, 150, 8), tile=False
    )


def test_parse_rpy_recovers_choice_button_frames_legacy_form():
    source = (
        'init python:\n'
        '    style.button.background = Frame("gui/minibar.png", 16, 16)\n'
        '    style.button.hover_background = Frame("gui/minibar_b.png", 16, 16)\n'
    )
    script, _problems = parse_rpy(source)
    assert script.choice_idle == FrameAsset(image="gui/minibar.png", borders=(16, 16, 16, 16), tile=False)
    assert script.choice_hover == FrameAsset(image="gui/minibar_b.png", borders=(16, 16, 16, 16), tile=False)


def test_parse_rpy_choice_button_frames_are_none_when_not_declared():
    script, _problems = parse_rpy('label start:\n    return\n')
    assert script.choice_idle is None
    assert script.choice_hover is None


def test_character_namebox_background_kwarg_is_captured():
    source = '''
    define margaret_think = Character("Margaret", namebox_background="gui/namebox/nameboxTHI.png")
    '''
    script, _problems = parse_rpy(source)
    assert script.characters["margaret_think"].namebox_background == "gui/namebox/nameboxTHI.png"


def test_character_without_namebox_background_kwarg_defaults_to_none():
    source = 'define e = Character("Eileen")\n'
    script, _problems = parse_rpy(source)
    assert script.characters["e"].namebox_background is None


def test_image_declaration_resolves_literal_path():
    source = '''
    image sakev = "gui/logo.jpg"
    image ctc = anim.Blink("gui/ctc.png", xalign=.93)

    label start:
        scene sakev
    '''
    script, problems = parse_rpy(source)
    assert script.images["sakev"] == "gui/logo.jpg"
    assert "ctc" not in script.images
    assert len(problems) == 1
    assert problems[0].reason == "image declaration is not a plain file path (dynamic displayable)"


def test_image_declaration_resolves_composite_layers():
    source = '''
    image chance a01 grin = im.Composite(None, (0,0), "char/chance/base01.png", (0,0), "char/chance/eyebrows01.png", (0,0), "char/chance/mouth10.png", (0,0), "char/chance/eyes08.png")
    image mikolaj a01 sarcastic = im.Composite(None,(0,0), "char/miko/base01.png",(0,0), "char/miko/eyebrows02.png")

    label start:
        show chance a01 grin
    '''
    script, problems = parse_rpy(source)
    assert script.composites["chance a01 grin"] == [
        "char/chance/base01.png",
        "char/chance/eyebrows01.png",
        "char/chance/mouth10.png",
        "char/chance/eyes08.png",
    ]
    assert script.composites["mikolaj a01 sarcastic"] == [
        "char/miko/base01.png",
        "char/miko/eyebrows02.png",
    ]
    assert "chance a01 grin" not in script.images
    assert problems == []


def test_image_declaration_does_not_resolve_composite_with_nonzero_offset():
    source = '''
    image portrait = im.Composite(None, (0,0), "base.png", (10,0), "hat.png")
    '''
    script, problems = parse_rpy(source)
    assert "portrait" not in script.composites
    assert "portrait" not in script.images
    assert len(problems) == 1
    assert problems[0].reason == "image declaration is not a plain file path (dynamic displayable)"


def test_menu_with_leading_prompt_statement():
    source = """
    label start:
        menu:
            "What's a visual novel?"
            "Say hi.":
                jump polite
            "Stay quiet.":
                jump shy

    label polite:
        return

    label shy:
        return
    """
    script, problems = parse_rpy(source)
    assert problems == []
    menu = script.labels[0].body[0]
    assert isinstance(menu, Menu)
    assert len(menu.prompt) == 1
    assert isinstance(menu.prompt[0], Say)
    assert menu.prompt[0].what == "What's a visual novel?"
    assert [c.text for c in menu.choices] == ["Say hi.", "Stay quiet."]


def test_menu_with_nested_choices():
    source = """
    label start:
        menu:
            "Say hi.":
                jump polite
            "Stay quiet.":
                jump shy

    label polite:
        return

    label shy:
        return
    """
    script, problems = parse_rpy(source)
    assert problems == []
    menu = script.labels[0].body[0]
    assert isinstance(menu, Menu)
    assert [c.text for c in menu.choices] == ["Say hi.", "Stay quiet."]
    assert isinstance(menu.choices[0].body[0], Jump)
    assert menu.choices[0].body[0].target == "polite"
    assert isinstance(menu.choices[1].body[0], Jump)
    assert menu.choices[1].body[0].target == "shy"


def test_legacy_ui_star_menu_pattern_converts_to_menu():
    # Ren'Py's legacy imperative ui.vbox/ui.textbutton/ui.close +
    # ui.interact() + if/elif-on-result idiom (predates menu:/screen:, but
    # some real games -- e.g. Jisei's investigation navigation -- build
    # their entire choice UI this way). Should convert cleanly, same
    # disposition as a real menu:.
    source = """
    label cafemenu0:
        $ ui.vbox(xalign=0.393, yalign=0.69)
        $ ui.textbutton("Talk", clicked=ui.returns(0), xminimum=220)
        $ ui.close()

        $ ui.vbox(xalign=0.67, yalign=0.69)
        $ ui.textbutton("Examine Room", clicked=ui.returns(1), xminimum=220)
        $ ui.close()

        $ result = ui.interact()
        if result == 0:
            jump cafetalkmenu0
        elif result==1:
            jump cafeexamine0
    """
    script, problems = parse_rpy(source)
    assert problems == []
    menu = script.labels[0].body[0]
    assert isinstance(menu, Menu)
    assert [c.text for c in menu.choices] == ["Talk", "Examine Room"]
    assert isinstance(menu.choices[0].body[0], Jump)
    assert menu.choices[0].body[0].target == "cafetalkmenu0"
    assert isinstance(menu.choices[1].body[0], Jump)
    assert menu.choices[1].body[0].target == "cafeexamine0"


def test_legacy_ui_star_menu_skips_disabled_button():
    source = """
    label m:
        $ ui.textbutton("Talk", clicked=None)
        $ ui.textbutton("Coffee Shop Girl", clicked=ui.returns(1))
        $ result = ui.interact()
        if result == 1:
            jump talk_girl
    """
    script, problems = parse_rpy(source)
    assert problems == []
    menu = script.labels[0].body[0]
    assert isinstance(menu, Menu)
    assert [c.text for c in menu.choices] == ["Coffee Shop Girl"]


def test_legacy_ui_star_menu_with_trailing_else_is_not_converted():
    # An else with no corresponding button can't be safely represented as
    # a menu choice -- leave the whole thing flagged rather than silently
    # dropping its body.
    source = """
    label m:
        $ ui.textbutton("A", clicked=ui.returns(0))
        $ result = ui.interact()
        if result == 0:
            jump a
        else:
            jump fallback
    """
    script, problems = parse_rpy(source)
    assert not isinstance(script.labels[0].body[0], Menu)
    assert len(problems) > 0


def test_default_and_define_literals_become_top_level_sets():
    source = '''
    default affection = 0
    define playouttakes = False
    define greeting = "Hello!"

    label start:
        "Hi."
    '''
    script, problems = parse_rpy(source)
    assert problems == []
    by_var = {s.var: s for s in script.top_level_sets}
    assert by_var["affection"].expr == "0"
    assert by_var["playouttakes"].expr == "False"
    assert by_var["greeting"].expr == '"Hello!"'


def test_default_persistent_attribute_resolves_to_a_flat_global():
    # real content (Mice Tea): `default persistent.skip_sex = "prompt"` --
    # previously never matched _DEFAULT_DEFINE_RE at all (no dot allowed
    # in the name), falling through to "unsupported top-level statement".
    source = '''
    default persistent.skip_sex = "prompt"
    default store.other_flag = True

    label start:
        "Hi."
    '''
    script, problems = parse_rpy(source)
    assert problems == []
    by_var = {s.var: s for s in script.top_level_sets}
    assert by_var["persistent_skip_sex"].expr == '"prompt"'
    assert by_var["store_other_flag"].expr == "True"


def test_default_with_a_non_persistent_dotted_name_is_flagged():
    source = '''
    default some_object.attr = 5

    label start:
        "Hi."
    '''
    script, problems = parse_rpy(source)
    assert script.top_level_sets == []
    assert len(problems) == 1
    assert problems[0].reason == "unsupported top-level statement"


def test_default_with_list_value_is_flagged_manual_not_generic():
    source = """
    default notes = ["a", "b"]

    label start:
        "Hi."
    """
    script, problems = parse_rpy(source)
    assert script.top_level_sets == []
    assert len(problems) == 1
    assert problems[0].reason == "list/dict-valued assignment has no VNDS equivalent (data for a feature needing native reimplementation)"


def test_default_and_define_literals_inside_a_label_body_convert_as_a_set():
    # regression: converting a second real game (Mice Tea) found this --
    # `default`/`define` of a literal declared *inside* a label's body
    # (route-tracking flags set partway through a scene are common real
    # content, e.g. `default afd24_route = "afd24_nonfurry"`) fell through
    # to a generic Unsupported, since only the top-level parse loop
    # recognized these prefixes -- the per-statement parser used for
    # label bodies didn't.
    source = '''
    label start:
        "Before."
        default afd24_route = "afd24_nonfurry"
        define chapter_count = 3
        "After."
    '''
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body
    assert isinstance(body[1], Set)
    assert body[1].var == "afd24_route"
    assert body[1].expr == '"afd24_nonfurry"'
    assert isinstance(body[2], Set)
    assert body[2].var == "chapter_count"
    assert body[2].expr == "3"


def test_default_with_list_value_inside_a_label_body_is_flagged_manual_not_generic():
    source = '''
    label start:
        default notes = ["a", "b"]
        "Hi."
    '''
    script, problems = parse_rpy(source)
    body = script.labels[0].body
    assert len(problems) == 1
    assert problems[0].reason == "list/dict-valued assignment has no VNDS equivalent (data for a feature needing native reimplementation)"
    assert isinstance(body[0], Unsupported)
    assert body[0].reason == problems[0].reason


def test_default_with_other_non_literal_value_is_flagged_generic():
    source = """
    default weird = some_func()

    label start:
        "Hi."
    """
    script, problems = parse_rpy(source)
    assert script.top_level_sets == []
    assert len(problems) == 1
    assert problems[0].reason == "unsupported top-level statement"


def test_dollar_statement_literal_assignment_and_accumulation():
    source = """
    label start:
        $ book = True
        $ affection = 0
        $ affection += 1
        $ affection -= 2
        $ affection = other_var
    """
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body
    assert body[0] == Set(var="book", expr="True", loc=body[0].loc)
    assert body[1] == Set(var="affection", expr="0", loc=body[1].loc)
    assert body[2] == Set(var="affection", expr="(affection + 1)", loc=body[2].loc)
    assert body[3] == Set(var="affection", expr="(affection - 2)", loc=body[3].loc)
    assert body[4] == Set(var="affection", expr="other_var", loc=body[4].loc)


def test_dollar_statement_now_supports_cross_variable_arithmetic():
    # Phase 2.4 added a real engine-side evaluator, so 2.1's original
    # self-reference-only restriction no longer applies to $ assignments.
    source = """
    label start:
        $ hp = shield + 5
        $ score = get_score()
    """
    script, problems = parse_rpy(source)
    body = script.labels[0].body
    assert body[0] == Set(var="hp", expr="(shield + 5)", loc=body[0].loc)
    assert len(problems) == 1
    assert problems[0].reason == "unsupported statement"
    assert "get_score" in problems[0].text


def test_if_elif_else_flattens_into_if_node():
    source = """
    label start:
        if affection >= 3:
            jump route_good
        elif affection >= 1:
            jump route_ok
        else:
            jump route_bad
    """
    script, problems = parse_rpy(source)
    assert problems == []
    node = script.labels[0].body[0]
    assert isinstance(node, If)
    assert len(node.branches) == 3
    assert node.branches[0].condition == "(affection >= 3)"
    assert node.branches[1].condition == "(affection >= 1)"
    assert node.branches[2].condition is None
    assert isinstance(node.branches[2].body[0], Jump)
    assert node.branches[2].body[0].target == "route_bad"


def test_if_supports_compound_and_or_conditions():
    # Phase 2.4/2.5: ifvar can evaluate compound conditions directly, so
    # and/or no longer need to be rejected as "too complex".
    source = """
    label start:
        if affection >= 3 and book:
            jump route_good
        elif affection >= 1 or seen_note:
            jump route_ok
    """
    script, problems = parse_rpy(source)
    assert problems == []
    node = script.labels[0].body[0]
    assert node.branches[0].condition == "((affection >= 3)) and (book)"
    assert node.branches[1].condition == "((affection >= 1)) or (seen_note)"


def test_if_with_bare_and_negated_truthy_conditions():
    source = """
    label start:
        if book:
            jump has_book
        elif not seen_note:
            jump show_note
    """
    script, problems = parse_rpy(source)
    assert problems == []
    node = script.labels[0].body[0]
    assert node.branches[0].condition == "book"
    assert node.branches[1].condition == "not seen_note"


def test_if_condition_resolves_persistent_attribute_access():
    # real content (Mice Tea): `if persistent.skip_sex == "prompt":` --
    # previously unconditionally unsupported (any attribute access at
    # all), now resolved to a flat global the same way a plain variable
    # would be.
    source = """
    label start:
        if persistent.skip_sex == "prompt":
            jump ask
        elif store.some_flag:
            jump other
    """
    script, problems = parse_rpy(source)
    assert problems == []
    node = script.labels[0].body[0]
    assert node.branches[0].condition == '(persistent_skip_sex == "prompt")'
    assert node.branches[1].condition == "store_some_flag"


def test_if_with_unsupported_condition_is_flagged_as_whole_construct():
    source = """
    label start:
        if some_condition.attr:
            jump somewhere
        else:
            jump elsewhere
    """
    script, problems = parse_rpy(source)
    assert len(problems) == 1
    assert problems[0].reason == "if/elif/else condition too complex for the current expression subset"
    assert isinstance(script.labels[0].body[0], Unsupported)


def test_while_loop_parses_condition_and_body():
    source = """
    label chat:
        $ inconvo = True
        while inconvo:
            menu:
                "Topic A":
                    $ inconvo = False
        "Done."
    """
    script, problems = parse_rpy(source)
    assert problems == []
    node = script.labels[0].body[1]
    assert isinstance(node, While)
    assert node.condition == "inconvo"
    assert isinstance(node.body[0], Menu)


def test_while_with_unsupported_condition_is_flagged():
    source = """
    label chat:
        while some_condition.attr:
            "unreachable"
    """
    script, problems = parse_rpy(source)
    assert len(problems) == 1
    assert problems[0].reason == "while condition too complex for the current expression subset"
    assert isinstance(script.labels[0].body[0], Unsupported)


def test_default_renpy_screens_are_flagged_distinctly_from_custom_ones():
    source = """
    screen say(who, what):
        text what

    screen main_menu():
        text "Main Menu"

    screen notes:
        text "Journal"

    label m:
        "done"
    """
    script, problems = parse_rpy(source)
    # "notes" is no longer flagged at all -- a plain `text "..."` custom
    # screen is now within the supported subset (pulled-forward Phase 5.1),
    # so it parses into a real ScreenDef instead of being rejected.
    # "main_menu" is deliberately no longer in the always-skipped set either
    # (real-hardware finding: games almost always customize it) -- a plain
    # `text "..."` body is within the supported subset, so it now converts
    # just like "notes" does. Only "say" (the dialogue box itself, which
    # the engine always renders natively) stays skipped.
    assert len(problems) == 1
    by_text = {p.text.split("(")[0].split(":")[0].strip(): p.reason for p in problems}
    assert by_text["screen say"] == "default Ren'Py screen already provided natively by the engine, no action needed"
    assert len(script.screens) == 2
    assert {s.name for s in script.screens} == {"main_menu", "notes"}


def test_window_show_and_hide():
    source = """
    label start:
        window show
        "Hi."
        window hide
    """
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body
    assert body[0] == Window(state="show", loc=body[0].loc)
    assert body[2] == Window(state="hide", loc=body[2].loc)


def test_window_auto_and_trailing_transition_token_are_recognized():
    # regression: converting a second real game (Mice Tea) found two
    # window forms the parser didn't recognize: "auto" (Ren'Py's third
    # window state, alongside show/hide) and a trailing transition token
    # (unrpyc's real decompiled rendering of "window hide" with an
    # explicit-but-empty transition argument, as "window hide None").
    # Both fell through to a generic Unsupported before this fix.
    source = """
    label start:
        window auto
        window hide None
    """
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body
    assert body[0] == Window(state="auto", loc=body[0].loc)
    assert body[1] == Window(state="hide", loc=body[1].loc)


def test_b_and_i_tags_translate_to_engine_escape_codes():
    source = r"""
    label start:
        "{b}Bold{/b} and {i}italic{/i}"
    """
    script, problems = parse_rpy(source)
    assert problems == []
    say = script.labels[0].body[0]
    assert isinstance(say, Say)
    assert say.what == "x1b[1mBoldx1b[22m and x1b[3mitalicx1b[23m"


def test_color_tag_translates_hex_to_the_extended_escape_code():
    source = r"""
    label start:
        "{color=#Ff0000}red{/color}"
    """
    script, problems = parse_rpy(source)
    assert problems == []
    say = script.labels[0].body[0]
    assert say.what == "x1b[#ff0000mredx1b[0m"


def test_wait_and_pause_tags_translate_to_a_pause_escape():
    source = r"""
    label start:
        "before{w}after{p=0.5}done"
    """
    script, problems = parse_rpy(source)
    assert problems == []
    say = script.labels[0].body[0]
    assert say.what == "beforex1b[P1.0mafterx1b[P0.5mdone"


def test_size_and_font_tags_strip_but_keep_content_and_now_flag():
    # previously silently passed through *unflagged* as literal, unrendered
    # braces -- worse than an ordinary unknown tag (which was at least
    # flagged) since there was no per-run font-size/font-file support to
    # act on it either way.
    source = r"""
    label start:
        "{size=30}big{/size} and {font=other.ttf}other{/font}"
    """
    script, problems = parse_rpy(source)
    say = script.labels[0].body[0]
    assert say.what == "big and other"
    assert len(problems) == 2
    assert all("no per-run font-size/font-file support" in p.reason for p in problems)


def test_alt_tag_strips_its_own_content_noalt_keeps_it():
    source = r"""
    label start:
        "Visible{alt} spoken only{/alt} and {noalt}still visible{/noalt}"
    """
    script, problems = parse_rpy(source)
    assert problems == []
    say = script.labels[0].body[0]
    assert say.what == "Visible and still visible"


def test_character_display_name_alt_text_does_not_leak_into_the_visible_name():
    # regression: a Character()'s display name was never translated at all
    # (raw {alt}/{i} markup, including {alt}'s *content*, passed straight
    # through) -- real content: `Character("{i}(Margaret){/i}{alt}
    # Thinking{/alt}", ...)` rendered as "(Margaret) Thinking" instead of
    # just "(Margaret)".
    source = r"""
    define margaret_think = Character("{i}(Margaret){/i}{alt} Thinking{/alt}", color="#c2989c")
    """
    script, problems = parse_rpy(source)
    assert problems == []
    char_def = script.characters["margaret_think"]
    assert char_def.display_name == "x1b[3m(Margaret)x1b[23m"


def test_unknown_text_tag_is_stripped_and_flagged():
    source = """
    label start:
        "Hello {shake}world{/shake}!"
    """
    script, problems = parse_rpy(source)
    assert len(problems) == 2  # {shake} and {/shake}
    assert all(p.reason.startswith("unknown text tag") for p in problems)
    say = script.labels[0].body[0]
    assert say.what == "Hello world!"


def test_unsupported_constructs_are_flagged_not_crashed():
    source = """
    label start:
        if some_condition.attr:
            "Branch text."
        $ some_var = some_func()
        screen custom_menu():
            text "Hi"
        "After the unsupported stuff, this still parses."
    """
    script, problems = parse_rpy(source)
    # three unsupported statements: if-block (attribute access unsupported),
    # $ statement (function call unsupported), screen-block
    assert len(problems) == 3
    assert all(isinstance(p, Unsupported) for p in problems)

    body = script.labels[0].body
    # unsupported nodes appear inline in body order too, so the emitter can
    # later place a "# FLAGGED" marker at the right point in script.vnds
    assert isinstance(body[0], Unsupported)
    assert isinstance(body[1], Unsupported)
    assert isinstance(body[2], Unsupported)
    last = body[3]
    assert isinstance(last, Say)
    assert last.what == "After the unsupported stuff, this still parses."


def test_source_locations_are_tracked():
    source = """
    label start:
        "line three"
    """
    script, _problems = parse_rpy(source, filename="test.rpy")
    say = script.labels[0].body[0]
    assert isinstance(say, Say)
    assert say.loc.file == "test.rpy"
    assert say.loc.line == 3


def test_screen_block_vbox_text_and_textbutton_actions():
    source = """
    screen main_menu2:
        vbox:
            text "Welcome"
            textbutton "Start" action Jump("start")
            textbutton "Quit" action Quit()
    """
    script, problems = parse_rpy(source)
    assert problems == []
    assert len(script.screens) == 1
    screen = script.screens[0]
    assert screen.name == "main_menu2"
    assert len(screen.root.children) == 1
    box = screen.root.children[0]
    assert isinstance(box, ScreenBox)
    assert isinstance(box.children[0], ScreenText)
    assert box.children[0].text == "Welcome"
    assert isinstance(box.children[1], ScreenButton)
    assert box.children[1].label == "Start"
    assert box.children[1].action == "jump start"
    assert box.children[2].action == "quit"


def test_screen_block_if_elif_else_and_more_actions():
    source = """
    screen stats:
        if affection > 5:
            text "High"
        elif affection > 0:
            text "Medium"
        else:
            text "Low"
        textbutton "Back" action Return()
        textbutton "Settings" action SetVariable("music_vol", 0.5)
        textbutton "Load" action ShowMenu("load_screen")
    """
    script, problems = parse_rpy(source)
    assert problems == []
    screen = script.screens[0]
    if_node = screen.root.children[0]
    assert isinstance(if_node, ScreenIf)
    assert len(if_node.branches) == 3
    assert if_node.branches[0].cond == "(affection > 5)"
    assert if_node.branches[1].cond == "(affection > 0)"
    assert if_node.branches[2].cond is None
    assert if_node.branches[0].children[0].text == "High"

    buttons = screen.root.children[1:]
    assert buttons[0].action == "hide_screen"
    assert buttons[1].action == 'setvar music_vol = 0.5'
    assert buttons[2].action == "show_screen load_screen"


def test_screen_block_with_for_loop_is_unsupported():
    # `for` loops need a list-typed VNDS variable to iterate, which
    # doesn't exist -- explicitly out of scope, reject the whole screen
    # rather than partially convert it.
    source = """
    screen save_slots:
        vbox:
            for i in range(10):
                text "Slot"
    """
    script, problems = parse_rpy(source)
    assert script.screens == []
    assert len(problems) == 1
    assert "outside the supported subset" in problems[0].reason


def test_screen_block_with_unrecognized_action_is_unsupported():
    source = """
    screen weird:
        textbutton "Go" action NullAction()
    """
    script, problems = parse_rpy(source)
    assert script.screens == []
    assert len(problems) == 1


def test_screen_block_partial_failure_does_not_desync_subsequent_parsing():
    # regression: a screen block that fails partway through (here, the
    # second button's unsupported action) must fully back out and re-skip
    # the whole block, not leave the cursor stuck mid-block -- otherwise
    # the label below would be misparsed as if it were screen content.
    source = """
    screen weird:
        textbutton "Ok" action Jump("start")
        textbutton "Bad" action NullAction()

    label start:
        "Reached the label cleanly."
    """
    script, problems = parse_rpy(source)
    assert script.screens == []
    assert len(problems) == 1
    assert len(script.labels) == 1
    assert script.labels[0].name == "start"
    say = script.labels[0].body[0]
    assert isinstance(say, Say)
    assert say.what == "Reached the label cleanly."


def test_imagemap_with_hotspots_covers_the_core_action_vocabulary():
    source = """
    screen main_menu():
        imagemap:
            ground "gui/mainmenu01_idle.jpg" idle "gui/mainmenu01_idle.jpg" hover "gui/mainmenu01_hover.jpg"
            hotspot (55, 390, 175, 31) action Start() alt "New Game"
            hotspot (167, 588, 143, 42) action Start("epilogue") alt "Epilogue"
            hotspot (66, 430, 169, 33) action ShowMenu("load") alt "Load Game"
            hotspot (277, 670, 143, 33) action Quit(confirm=False) alt "Quit Game"
            hotspot (10, 10, 5, 5) action NullAction()
    """
    # screen_resolution=(1000, 1000): a round denominator makes the
    # expected fractions easy to read/verify by hand (55/1000 = 0.055).
    script, problems = parse_rpy(source, screen_resolution=(1000, 1000))
    assert problems == []
    assert len(script.screens) == 1
    imagemap = script.screens[0].root.children[0]
    assert isinstance(imagemap, ScreenImagemap)
    assert imagemap.ground == "gui/mainmenu01_idle.jpg"
    assert imagemap.hotspots == [
        ScreenHotspot(x=0.055, y=0.39, w=0.175, h=0.031, action="hide_screen"),
        ScreenHotspot(x=0.167, y=0.588, w=0.143, h=0.042, action="jump epilogue"),
        ScreenHotspot(x=0.066, y=0.43, w=0.169, h=0.033, action="show_screen load"),
        ScreenHotspot(x=0.277, y=0.67, w=0.143, h=0.033, action="quit"),
        ScreenHotspot(x=0.01, y=0.01, w=0.005, h=0.005, action=None),
    ]


def test_imagemap_drops_only_the_one_hotspot_with_an_unsupported_action():
    # the key regression for imagemap's partial-failure design: unlike
    # every other custom-screen construct (where one bad line nulls the
    # whole screen), one hotspot using an action with no VNDS equivalent
    # (e.g. an arbitrary Python callback) is dropped and flagged on its
    # own -- every other hotspot, including the ones that matter most,
    # still converts and works.
    source = """
    screen main_menu():
        imagemap:
            ground "gui/mainmenu01_idle.jpg"
            hotspot (55, 390, 175, 31) action Start() alt "New Game"
            hotspot (300, 300, 10, 10) action Function(do_thing) alt "bonus"
            hotspot (277, 670, 143, 33) action Quit() alt "Quit Game"
    """
    script, problems = parse_rpy(source)
    assert len(problems) == 1
    assert problems[0].reason == "imagemap hotspot uses an unsupported action, this hotspot dropped"
    assert len(script.screens) == 1
    imagemap = script.screens[0].root.children[0]
    assert isinstance(imagemap, ScreenImagemap)
    assert [h.action for h in imagemap.hotspots] == ["hide_screen", "quit"]


def test_imagemap_with_unparseable_ground_bails_the_whole_screen():
    # unlike a bad hotspot action, a missing/unparseable `ground` line
    # means there's nothing to render at all -- matches the existing
    # whole-screen-bail precedent for genuinely unsupported structure.
    source = """
    screen main_menu():
        imagemap:
            hotspot (55, 390, 175, 31) action Start()
    """
    script, problems = parse_rpy(source)
    assert script.screens == []
    assert len(problems) == 1
    assert "outside the supported subset" in problems[0].reason


def test_imagemap_nested_in_if_else_matches_jiseis_real_main_menu_shape():
    # Jisei's real screen main_menu() is exactly this shape: two different
    # imagemaps (different background art) chosen by a persistent-data
    # condition -- confirmed via the 13-corpus survey. ScreenIf/
    # ScreenIfBranch already support arbitrary children, so this should
    # fall out for free once ScreenImagemap is a valid child type.
    source = """
    screen main_menu():
        if persistent.beatgame:
            imagemap:
                ground "gui/mainmenu02_idle.jpg"
                hotspot (55, 390, 175, 31) action Start() alt "New Game"
        else:
            imagemap:
                ground "gui/mainmenu01_idle.jpg"
                hotspot (55, 390, 175, 31) action Start() alt "New Game"
    """
    script, problems = parse_rpy(source)
    assert problems == []
    if_node = script.screens[0].root.children[0]
    assert isinstance(if_node, ScreenIf)
    assert len(if_node.branches) == 2
    beat_branch, default_branch = if_node.branches
    assert isinstance(beat_branch.children[0], ScreenImagemap)
    assert beat_branch.children[0].ground == "gui/mainmenu02_idle.jpg"
    assert isinstance(default_branch.children[0], ScreenImagemap)
    assert default_branch.children[0].ground == "gui/mainmenu01_idle.jpg"


def test_translate_strings_block_is_classified_as_localization_not_unsupported():
    # 13-corpus comparison finding: translate blocks (per-language
    # localization data) fell to the generic "unsupported top-level
    # statement" catch-all, dominating several real games' Problem
    # Reports (up to 99% of Slay the Princess's).
    source = '''
    translate french strings:
        old "Hello"
        new "Bonjour"

    label start:
        "Hi."
    '''
    script, problems = parse_rpy(source)
    assert len(problems) == 1
    assert problems[0].reason == "translate block is localization data, not game content"
    assert script.labels[0].name == "start"


def test_translate_label_block_nested_inside_a_label_body_is_classified():
    # translate LANG some_label: (a fully-translated copy of a label's
    # dialogue) can appear nested inside a label body too, not just at
    # top level.
    source = '''
    label start:
        "Before."
        translate french start:
            "Avant."
        "After."
    '''
    script, problems = parse_rpy(source)
    assert len(problems) == 1
    assert problems[0].reason == "translate block is localization data, not game content"
    body = script.labels[0].body
    assert [type(n).__name__ for n in body] == ["Say", "Unsupported", "Say"]
    assert body[2].what == "After."


def test_bare_python_block_inside_a_label_body_is_classified_manual():
    # 13-corpus comparison finding: a python: block mid-scene (as opposed
    # to top-level init python:) fell to the generic "unsupported
    # statement" catch-all instead of being classified like init python:.
    source = '''
    label start:
        "Before."
        python:
            inc_depressed()
            inc_cheerful()
        "After."
    '''
    script, problems = parse_rpy(source)
    assert len(problems) == 1
    assert problems[0].reason == "python block has no VNDS equivalent (needs native reimplementation, if needed at all)"
    body = script.labels[0].body
    assert [type(n).__name__ for n in body] == ["Say", "Unsupported", "Say"]
    assert body[2].what == "After."


def test_single_quoted_strings_parse_the_same_as_double_quoted():
    # 13-corpus comparison finding: DateWarp/Magical Diary/LongLiveTheQueen/
    # Our Life all use single-quoted string literals in real content (Ren'Py
    # treats '...' and "..." as fully interchangeable) -- the shared _QUOTED
    # regex only ever matched "..." before this fix, silently failing to
    # parse play/voice/say/menu-choice statements written with single quotes.
    source = """
    label start:
        voice 'audio/v/line1.ogg'
        play sound 'sounds/heart_thump.ogg'
        c2 'How\\'s it going?'
        "literal name" 'text with an escaped \\' inside'
        menu:
            'Go left':
                jump left
            'Go right':
                jump right
    """
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body
    assert body[0] == Play(channel="voice", file="audio/v/line1.ogg", is_queue=False, loc=body[0].loc)
    assert body[1] == Play(channel="sound", file="sounds/heart_thump.ogg", is_queue=False, loc=body[1].loc)
    assert body[2] == Say(who="c2", what="How's it going?", loc=body[2].loc)
    assert body[3] == Say(who="literal name", what="text with an escaped ' inside", loc=body[3].loc)
    menu = body[4]
    assert isinstance(menu, Menu)
    assert menu.choices[0].text == "Go left"
    assert menu.choices[1].text == "Go right"


def test_single_and_double_quotes_can_mix_within_one_statement():
    # e.g. a literal-name say line with one quote style for the name and
    # the other for the dialogue -- confirmed valid Ren'Py syntax.
    script, problems = parse_rpy('''label start:\n    "Anonymous" 'said this'\n''')
    assert problems == []
    assert script.labels[0].body[0] == Say(who="Anonymous", what="said this", loc=script.labels[0].body[0].loc)


def test_day_subchapter_the_end_cards_work_with_single_quotes():
    # DayCard/SubchapterCard/TheEndCard go through _DAY_RE/_SUBCHAPTER_RE/
    # _THE_END_RE, all _QUOTED-based -- a regression risk specific to this
    # fix since their capture groups now include the quote marks and must
    # be explicitly dequoted (previously bare, now via _dequote).
    source = """
    label start:
        day '1' 'A New Day'
        subchapter 'Chapter Two'
        the_end 'Fin'
    """
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body
    assert body[0] == DayCard(day_number="1", subtitle="A New Day", mood="default", loc=body[0].loc)
    assert body[1] == SubchapterCard(message="Chapter Two", loc=body[1].loc)
    assert body[2] == TheEndCard(title="Fin", loc=body[2].loc)


def test_say_with_one_attribute_synthesizes_an_implicit_show():
    # 13-corpus comparison finding: Ren'Py's combined show+say shorthand
    # (`ellen confused "No."` == `show ellen confused` + `ellen "No."` in
    # one line) wasn't recognized at all -- _SAY_RE only allowed a single
    # bare word before the quote, so any attribute token broke the match
    # entirely and the whole line fell to unsupported/unknown. Dominated
    # Magical Diary Wolf Hall's Problem Report (48%).
    source = '''
    label start:
        ellen confused "No."
    '''
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body
    assert body[0] == Show(image="ellen confused", position=None, loc=body[0].loc)
    assert body[1] == Say(who="ellen", what="No.", loc=body[1].loc)


def test_say_with_multiple_attributes_synthesizes_an_implicit_show():
    script, problems = parse_rpy('label start:\n    pg meansmile smug "Nothing that you will learn here."\n')
    assert problems == []
    body = script.labels[0].body
    assert body[0] == Show(image="pg meansmile smug", position=None, loc=body[0].loc)
    assert body[1] == Say(who="pg", what="Nothing that you will learn here.", loc=body[1].loc)


def test_say_with_no_attribute_still_parses_as_a_single_say_node():
    # Regression check: a plain `character "text"` (the overwhelmingly
    # common case) must not gain a spurious synthesized Show.
    script, problems = parse_rpy('label start:\n    ellen "No."\n')
    assert problems == []
    body = script.labels[0].body
    assert len(body) == 1
    assert body[0] == Say(who="ellen", what="No.", loc=body[0].loc)


def test_quoted_literal_display_name_with_a_space_is_not_treated_as_an_attribute():
    # Regression check: `_SAY_NAMED_RE`'s quoted-literal-name form (e.g.
    # `"Mysterious Stranger" "Hello."`) must never be split -- a space
    # inside a quoted display name is part of the name, not an attribute
    # separator (this form never goes through _SAY_RE at all).
    script, problems = parse_rpy('label start:\n    "Mysterious Stranger" "Hello."\n')
    assert problems == []
    body = script.labels[0].body
    assert len(body) == 1
    assert body[0] == Say(who="Mysterious Stranger", what="Hello.", loc=body[0].loc)


def test_dict_subscript_augmented_assignment_flattens_to_a_namespaced_variable():
    # 13-corpus comparison finding: ScarletHollow tracks relationships via
    # `$ stella_relationship["trust"] += 1` -- a dict-subscript augmented
    # assignment, unsupported since _render_expr had no ast.Subscript
    # branch at all (~7300 occurrences, its single biggest blocking cause).
    source = '''
    label start:
        $ stella_relationship["trust"] += 1
        $ stella_relationship["trust"] -= 2
    '''
    script, problems = parse_rpy(source)
    assert problems == []
    body = script.labels[0].body
    assert body[0] == Set(var="stella_relationship__trust", expr="(stella_relationship__trust + 1)", loc=body[0].loc)
    assert body[1] == Set(var="stella_relationship__trust", expr="(stella_relationship__trust - 2)", loc=body[1].loc)


def test_dict_subscript_plain_read_also_flattens():
    script, problems = parse_rpy('label start:\n    $ x = stella_relationship["trust"]\n')
    assert problems == []
    body = script.labels[0].body
    assert body[0] == Set(var="x", expr="stella_relationship__trust", loc=body[0].loc)


def test_dict_subscript_with_a_non_literal_key_stays_unsupported():
    # A dynamic/variable subscript key has no static VNDS equivalent --
    # must correctly fall through, not silently misconvert.
    script, problems = parse_rpy('label start:\n    $ x = stella_relationship[key_var]\n')
    assert len(problems) == 1
    assert problems[0].reason == "unsupported statement"
    assert script.labels[0].body[0] is problems[0]


def test_dict_subscript_with_a_non_identifier_safe_key_stays_unsupported():
    # A key containing a space/punctuation can't become a valid VNDS
    # variable name -- must correctly fall through rather than emit a
    # malformed identifier.
    script, problems = parse_rpy('label start:\n    $ x = stella_relationship["a b"]\n')
    assert len(problems) == 1
    assert problems[0].reason == "unsupported statement"
    assert script.labels[0].body[0] is problems[0]


def test_change_portrait_call_resolves_to_a_portrait_update_node():
    # Our Life: Beginnings & Always' bespoke multi-layer portrait system --
    # confirmed real content, 16000+ ChangePortrait calls in that one game.
    categories = SpriteLayerCategories(
        parts_order=("base", "brows", "mouth", "eyes"),
        expressions=frozenset({"eyes", "mouth", "brows"}),
    )
    source = '''
    label start:
        $ ChangePortrait(chara="Cove_8", base="default", eyes="closed", blink=True, transition=False)
        "Hello."
    '''
    script, problems = parse_rpy(source, sprite_categories=categories)
    assert problems == []
    body = script.labels[0].body
    update = body[0]
    assert isinstance(update, PortraitUpdate)
    assert update.name == "Cove_8"
    assert update.blink is True
    assert update.transition is False
    assert [u.slot for u in update.updates] == ["base", "eyes"]
    assert isinstance(body[1], Say)


def test_change_portrait_call_with_unresolvable_args_falls_through_to_unsupported():
    source = 'label start:\n    $ ChangePortrait(chara=some_var, base="default")\n'
    script, problems = parse_rpy(source, sprite_categories=SpriteLayerCategories())
    assert len(problems) == 1
    assert problems[0].reason == "unsupported statement"


def test_change_portrait_call_with_no_sprite_categories_provided_still_resolves():
    # sprite_categories defaults to an empty SpriteLayerCategories() for
    # callers that don't need portrait resolution at all (most games) --
    # must not crash, just categorize every slot as "plain".
    source = 'label start:\n    $ ChangePortrait(chara="Cove_8", base="default")\n'
    script, problems = parse_rpy(source)
    assert problems == []
    update = script.labels[0].body[0]
    assert update.updates[0].category == "plain"
