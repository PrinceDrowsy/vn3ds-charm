import pytest

from converter.parser.character_image import (
    InterpreterBailout,
    expand_attrs,
    parse_character_image_declarations,
    resolve_layer_file,
    resolve_layers,
    resolve_layers_with_persistent,
    scan_character_image_constants,
)


def _def_source(selector_body: str, **overrides: str) -> str:
    """Builds a minimal one-character CharacterImage declaration + its
    layer_selector, in the same shape real content uses (an `init python:`
    block defining the selector, then the `image TAG = CharacterImage(...)`
    line) -- real declarations always keep both in the same file."""
    layers = overrides.get("layers", '"Base*", "eyes *", "mouth *"')
    attribute_sets = overrides.get(
        "attribute_sets", '{"eyes_happy", "eyes_neutral"}, {"mouth_smile", "mouth_neutral"}'
    )
    aliases = overrides.get("aliases", '{"happy": {"eyes_happy", "mouth_smile"}}')
    return f'''
init python:
    def afd_layer_selector(ci, attr):
{selector_body}

image afd_l = CharacterImage(
    character_name="afd",
    size=(750, 1300),
    layers=({layers},),
    attribute_sets=({attribute_sets},),
    aliases={aliases},
    layer_selector=afd_layer_selector,
)
'''


class TestInterpreterSubset:
    def test_plain_membership_yield(self):
        source = _def_source(
            '''        yield "Base"
        if "eyes_happy" in attr:
            yield "eyes happy"
        else:
            yield "eyes neutral"
'''
        )
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        layers, gated = resolve_layers(cd, frozenset({"eyes_happy"}))
        assert layers == ["Base", "eyes happy"]
        assert gated is None

    def test_elif_and_early_return(self):
        source = _def_source(
            '''        if "mouth_smile" in attr:
            yield "mouth smile"
            return
        elif "mouth_neutral" in attr:
            yield "mouth neutral"
        yield "Base"
'''
        )
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        layers, _ = resolve_layers(cd, frozenset({"mouth_smile"}))
        assert layers == ["mouth smile"]  # early return skips the trailing "Base" yield

    def test_and_or_not_boolean_ops(self):
        source = _def_source(
            '''        if "a" in attr and not "b" in attr:
            yield "only_a"
        if "a" in attr or "c" in attr:
            yield "a_or_c"
'''
        )
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        layers, _ = resolve_layers(cd, frozenset({"a"}))
        assert layers == ["only_a", "a_or_c"]
        layers, _ = resolve_layers(cd, frozenset({"a", "b"}))
        assert layers == ["a_or_c"]

    def test_string_concat_and_local_variable(self):
        source = _def_source(
            '''        base = "eyes "
        if "eyes_happy" in attr:
            base = base + "happy"
        else:
            base = base + "neutral"
        yield base
'''
        )
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        layers, _ = resolve_layers(cd, frozenset({"eyes_happy"}))
        assert layers == ["eyes happy"]

    def test_replace_and_split_and_len_and_indexing(self):
        source = _def_source(
            '''        name = "eyes_happy"
        parts = name.split("_")
        yield parts[0] + " " + parts[1]
        if len(attr) > 0:
            yield name.replace("_", " ")
'''
        )
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        layers, _ = resolve_layers(cd, frozenset({"eyes_happy"}))
        assert layers == ["eyes happy", "eyes happy"]

    def test_for_loop_over_attr(self):
        source = _def_source(
            '''        for a in attr:
            yield a
'''
        )
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        layers, _ = resolve_layers(cd, frozenset({"x"}))
        assert layers == ["x"]

    def test_set_intersection_and_union(self):
        source = _def_source(
            '''        special = {"tf1", "tf2"}
        if len(special & attr) > 0:
            yield "special"
        combined = special.union({"extra"})
        if "extra" in combined:
            yield "combined_ok"
'''
        )
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        layers, _ = resolve_layers(cd, frozenset({"tf1"}))
        assert layers == ["special", "combined_ok"]

    def test_module_level_constant_referenced_directly(self):
        source = f'''
init python:
    AFD_L_EYES = ["eyes_happy", "eyes_neutral"]

    def afd_layer_selector(ci, attr):
        for a in attr:
            if a in AFD_L_EYES:
                yield "eyes " + a.replace("eyes_", "")

image afd_l = CharacterImage(
    character_name="afd",
    size=(750, 1300),
    layers=("eyes *",),
    attribute_sets=(set(AFD_L_EYES),),
    aliases={{}},
    layer_selector=afd_layer_selector,
)
'''
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        layers, _ = resolve_layers(cd, frozenset({"eyes_happy"}))
        assert layers == ["eyes happy"]

    def test_bare_side_effect_call_is_a_no_op_not_a_bailout(self):
        source = _def_source(
            '''        persistent.cv_npcs.add("afd_l")
        check_npc_unlock_progress()
        yield "Base"
'''
        )
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        layers, _ = resolve_layers(cd, frozenset())
        assert layers == ["Base"]

    def test_renpy_loadable_call_uses_injected_checker(self, tmp_path):
        (tmp_path / "characters" / "afd").mkdir(parents=True)
        (tmp_path / "characters" / "afd" / "special.png").write_bytes(b"\x89PNG")
        source = _def_source(
            '''        if renpy.loadable("characters/afd/special.png"):
            yield "special"
        else:
            yield "fallback"
'''
        )
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        layers, _ = resolve_layers(cd, frozenset(), assets_dir=tmp_path)
        assert layers == ["special"]
        layers, _ = resolve_layers(cd, frozenset(), assets_dir=None)
        assert layers == ["fallback"]

    def test_local_helper_function_called_for_its_return_value(self):
        # confirmed real content: margaret_get_arms_file/julie_get_arms_file
        # -- characters commonly factor out "compute this variant's file
        # name" as its own plain value-returning helper, called from
        # within the main selector rather than inlined.
        source = '''
init python:
    def afd_get_file(prefix, a):
        return prefix + " " + a.replace("eyes_", "")

    def afd_layer_selector(ci, attr):
        for a in attr:
            yield afd_get_file("eyes", a)

image afd_l = CharacterImage(
    character_name="afd",
    size=(750, 1300),
    layers=("eyes *",),
    attribute_sets=({"eyes_happy"},),
    aliases={},
    layer_selector=afd_layer_selector,
)
'''
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        layers, _ = resolve_layers(cd, frozenset({"eyes_happy"}))
        assert layers == ["eyes happy"]

    def test_helper_function_touching_persistent_is_tracked_for_gating(self):
        source = '''
init python:
    def afd_get_variant():
        if persistent.nude_sprites:
            return "nude"
        return "normal"

    def afd_layer_selector(ci, attr):
        yield afd_get_variant()

image afd_l = CharacterImage(
    character_name="afd",
    size=(750, 1300),
    layers=("normal", "nude"),
    attribute_sets=({"x"},),
    aliases={},
    layer_selector=afd_layer_selector,
)
'''
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        layers, persistent_name = resolve_layers(cd, frozenset())
        assert persistent_name == "nude_sprites"
        assert layers == ["nude"]
        assert resolve_layers_with_persistent(cd, frozenset(), False) == ["normal"]

    def test_lower_and_upper_string_methods(self):
        source = _def_source(
            '''        yield "EYES".lower()
        yield "eyes".upper()
'''
        )
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        layers, _ = resolve_layers(cd, frozenset())
        assert layers == ["eyes", "EYES"]

    def test_continue_skips_rest_of_loop_body(self):
        source = _def_source(
            '''        for a in attr:
            if a == "skip_me":
                continue
            yield a
'''
        )
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        layers, _ = resolve_layers(cd, frozenset({"skip_me", "keep_me"}))
        assert layers == ["keep_me"]

    def test_unsupported_construct_bails_out(self):
        # dict comprehensions (or any construct outside the supported
        # subset) must raise InterpreterBailout, not silently misbehave or
        # crash with an unrelated Python exception.
        source = _def_source(
            '''        x = {a: a for a in attr}
        yield "Base"
'''
        )
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        with pytest.raises(InterpreterBailout):
            resolve_layers(cd, frozenset())


class TestPersistentGating:
    def test_single_persistent_flag_reports_gating_and_both_variants(self):
        source = _def_source(
            '''        yield "Base"
        if persistent.nude_sprites:
            yield "nude overlay"
'''
        )
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        layers, persistent_name = resolve_layers(cd, frozenset())
        assert persistent_name == "nude_sprites"
        assert layers == ["Base", "nude overlay"]  # resolve_layers' own "default" is the True variant
        assert resolve_layers_with_persistent(cd, frozenset(), True) == ["Base", "nude overlay"]
        assert resolve_layers_with_persistent(cd, frozenset(), False) == ["Base"]

    def test_no_persistent_read_reports_not_gated(self):
        source = _def_source('''        yield "Base"
''')
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        layers, persistent_name = resolve_layers(cd, frozenset())
        assert persistent_name is None
        assert layers == ["Base"]

    def test_two_distinct_persistent_flags_bails_out(self):
        source = _def_source(
            '''        if persistent.a:
            yield "a"
        if persistent.b:
            yield "b"
'''
        )
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        with pytest.raises(InterpreterBailout):
            resolve_layers(cd, frozenset())


class TestDeclarationParsing:
    def test_set_call_capitalized_is_recognized_as_a_set_constructor(self):
        # confirmed real content: felicia.rpy's
        # `FELICIA_BASES = Set(FELICIA_BASES_LIST)` -- a capitalized `Set(...)`
        # call (Ren'Py's own Set helper), not the lowercase builtin.
        source = f'''
init python:
    FELICIA_BASES_LIST = (
        "base_vest",
        "base_baggy",
    )
    FELICIA_BASES = Set(FELICIA_BASES_LIST)

    def felicia_layer_selector(ci, attr):
        yield "Base"

image felicia = CharacterImage(
    character_name="felicia",
    size=(510, 1234),
    layers=("Base*",),
    attribute_sets=(FELICIA_BASES,),
    aliases={{}},
    layer_selector=felicia_layer_selector,
)
'''
        defs = parse_character_image_declarations(source, "felicia.rpy")
        assert "felicia" in defs
        assert defs["felicia"].attribute_sets == (frozenset({"base_vest", "base_baggy"}),)

    def test_union_chain_across_bare_names_and_set_literals(self):
        source = f'''
init python:
    MARGARET_ARMS = ["arms_a", "arms_b"]
    SPECIAL_POSES = {{"pose_x"}}
    MARGARET_POSES = ["pose_y"]

    def margaret_layer_selector(ci, attr):
        yield "Base"

image margaret = CharacterImage(
    character_name="margaret",
    size=(750, 1300),
    layers=("Base*",),
    attribute_sets=(set(MARGARET_ARMS).union(SPECIAL_POSES).union(MARGARET_POSES),),
    aliases={{}},
    layer_selector=margaret_layer_selector,
)
'''
        defs = parse_character_image_declarations(source, "margaret.rpy")
        assert defs["margaret"].attribute_sets == (
            frozenset({"arms_a", "arms_b", "pose_x", "pose_y"}),
        )

    def test_cross_file_constant_resolved_via_global_lists(self):
        # confirmed real content: felicia.rpy's attribute_sets references
        # SPECIAL_POSES, which is actually declared in margaret.rpy --
        # Ren'Py's own namespace for these constants is flat across files.
        margaret_source = '''
init python:
    SPECIAL_POSES = {"pose_x", "pose_y"}
'''
        felicia_source = f'''
init python:
    def felicia_layer_selector(ci, attr):
        yield "Base"

image felicia = CharacterImage(
    character_name="felicia",
    size=(510, 1234),
    layers=("Base*",),
    attribute_sets=(SPECIAL_POSES.union({{"extra"}}),),
    aliases={{}},
    layer_selector=felicia_layer_selector,
)
'''
        global_lists = scan_character_image_constants(margaret_source)
        defs = parse_character_image_declarations(felicia_source, "felicia.rpy", global_lists=global_lists)
        assert defs["felicia"].attribute_sets == (frozenset({"pose_x", "pose_y", "extra"}),)

        # without the prepass, the same file fails to parse at all -- the
        # existing "couldn't parse this declaration" fallback (rpy_parser.py)
        # takes over, not a crash.
        assert parse_character_image_declarations(felicia_source, "felicia.rpy") == {}

    def test_selector_not_taking_two_args_is_rejected(self):
        source = '''
init python:
    def bad_selector(ci):
        yield "Base"

image afd_l = CharacterImage(
    character_name="afd",
    size=(750, 1300),
    layers=("Base*",),
    attribute_sets=({"x"},),
    aliases={},
    layer_selector=bad_selector,
)
'''
        assert parse_character_image_declarations(source, "afd.rpy") == {}

    def test_non_character_image_declarations_are_ignored(self):
        source = '''
image plain = "some/path.png"
'''
        assert parse_character_image_declarations(source, "x.rpy") == {}


class TestAliasExpansion:
    def test_alias_expands_to_its_attribute_set(self):
        source = _def_source(selector_body='''        yield "Base"
''')
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        expanded = expand_attrs(cd, frozenset({"happy"}))
        assert expanded == frozenset({"eyes_happy", "mouth_smile"})

    def test_unrecognized_attribute_passes_through_unchanged(self):
        source = _def_source(selector_body='''        yield "Base"
''')
        defs = parse_character_image_declarations(source, "afd.rpy")
        cd = defs["afd_l"]
        expanded = expand_attrs(cd, frozenset({"eyes_happy", "something_else"}))
        assert expanded == frozenset({"eyes_happy", "something_else"})


class TestWildcardLayerResolution:
    def test_wildcard_pattern_matches_real_file_case_insensitively(self, tmp_path):
        char_dir = tmp_path / "characters" / "afd"
        char_dir.mkdir(parents=True)
        (char_dir / "Eyes Happy.png").write_bytes(b"\x89PNG")
        layers = ("Base*", "eyes *")
        result = resolve_layer_file("eyes happy", "afd", layers, tmp_path)
        assert result is not None
        path, index = result
        assert path.endswith("Eyes Happy.png")
        assert index == 1  # "eyes *" is layers[1] -- draw order, not yield order

    def test_exact_entry_matches_a_real_file(self, tmp_path):
        char_dir = tmp_path / "characters" / "afd"
        char_dir.mkdir(parents=True)
        (char_dir / "arms jacket neutral.png").write_bytes(b"\x89PNG")
        layers = ("arms jacket neutral", "Base*")
        result = resolve_layer_file("arms jacket neutral", "afd", layers, tmp_path)
        assert result is not None
        _path, index = result
        assert index == 0

    def test_no_matching_entry_returns_none(self, tmp_path):
        char_dir = tmp_path / "characters" / "afd"
        char_dir.mkdir(parents=True)
        result = resolve_layer_file("lighting_night", "afd", ("Base*",), tmp_path)
        assert result is None

    def test_prefix_does_not_falsely_match_a_longer_similarly_named_file(self, tmp_path):
        # "Base*" must not match a file that merely starts with "Base" but
        # is a different, longer name the wildcard wasn't meant to cover
        # (mirrors the engine's own "afd_l" vs "afd_larger" slot-prefix fix).
        char_dir = tmp_path / "characters" / "afd"
        char_dir.mkdir(parents=True)
        (char_dir / "Basement.png").write_bytes(b"\x89PNG")
        result = resolve_layer_file("base_thing", "afd", ("base_*",), tmp_path)
        assert result is None
