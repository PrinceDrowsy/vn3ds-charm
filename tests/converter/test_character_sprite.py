from converter.parser.character_sprite import (
    PortraitLayerUpdate,
    SpriteLayerCategories,
    merge_sprite_layer_categories,
    parse_change_portrait_call,
    parse_portrait_declarations,
    scan_sprite_layer_categories,
)
from converter.parser.ir import SourceLocation

LOC = SourceLocation("game.rpy", 1)


def test_scan_sprite_layer_categories_resolves_the_const_indirection():
    # Real content: characterSpritePartsOrder is itself just
    # `= characterSpritePartsOrder_const` (a bare name reference to the
    # real literal list), not the literal list directly.
    source = '''
define characterSpritePartsOrder_const = ["base", "eyes", "mouth", "magic_effect"]
define characterSpritePartsOrder = characterSpritePartsOrder_const
default characterSpriteExpressions = ["eyes", "mouth", "brows"]
default characterSpriteGlowing = ["eye_glow"]
default characterSpriteMagic = ["magic_effect"]
'''
    categories = scan_sprite_layer_categories(source)
    assert categories.parts_order == ("base", "eyes", "mouth", "magic_effect")
    assert categories.expressions == frozenset({"eyes", "mouth", "brows"})
    assert categories.glowing == frozenset({"eye_glow"})
    assert categories.magic == frozenset({"magic_effect"})


def test_merge_sprite_layer_categories_unions_sets_and_prefers_first_parts_order():
    a = SpriteLayerCategories(parts_order=("base", "eyes"), expressions=frozenset({"eyes"}))
    b = SpriteLayerCategories(parts_order=("should", "not", "win"), glowing=frozenset({"eye_glow"}))
    merged = merge_sprite_layer_categories(a, b)
    assert merged.parts_order == ("base", "eyes")
    assert merged.expressions == frozenset({"eyes"})
    assert merged.glowing == frozenset({"eye_glow"})


def test_parse_portrait_declarations_keyed_by_name_not_tag():
    source = (
        'image cove_8 = Portrait(name="Cove_8", speaker="COVE", portraitName="cove_8", '
        "animateEyes=True, animateMouth=False, width=615, height=1439)\n"
    )
    defs = parse_portrait_declarations(source, "portrait.rpy")
    assert "Cove_8" in defs
    d = defs["Cove_8"]
    assert d.tag == "cove_8"
    assert d.speaker == "COVE"
    assert d.animate_eyes is True
    assert d.animate_mouth is False
    assert d.width == 615
    assert d.height == 1439


def test_parse_portrait_declarations_defaults_unspecified_fields():
    source = 'image bg_char = Portrait(name="Bg_Char", portraitName="bg_char")\n'
    defs = parse_portrait_declarations(source)
    d = defs["Bg_Char"]
    assert d.speaker is None
    assert d.animate_eyes is False
    assert d.animate_mouth is False
    assert d.width == 300
    assert d.height == 600


def _categories() -> SpriteLayerCategories:
    return SpriteLayerCategories(
        parts_order=("base", "brows", "blush", "mouth", "eyes", "eye_glow", "magic_effect"),
        expressions=frozenset({"eyes", "mouth", "brows"}),
        glowing=frozenset({"eye_glow"}),
        magic=frozenset({"magic_effect"}),
    )


def test_change_portrait_call_resolves_layer_updates_sorted_by_draw_order():
    text = '$ ChangePortrait(chara="Cove_8", eyes="n", base="default", brows="n_brows")'
    call = parse_change_portrait_call(text, _categories(), LOC)
    assert call is not None
    assert call.name == "Cove_8"
    assert call.blink is True
    assert call.transition is True
    assert call.tint is None
    assert [u.slot for u in call.updates] == ["base", "brows", "eyes"]  # draw order, not kwarg order


def test_change_portrait_call_only_touches_slots_actually_passed():
    # SetSpritePart's real incremental semantics -- an untouched slot must
    # not appear in the resolved update list at all.
    text = '$ ChangePortrait(chara="Cove_8", eyes="n")'
    call = parse_change_portrait_call(text, _categories(), LOC)
    assert [u.slot for u in call.updates] == ["eyes"]


def test_change_portrait_call_categorizes_eyes_and_mouth_specially():
    text = '$ ChangePortrait(chara="Cove_8", eyes="n", mouth="smile")'
    call = parse_change_portrait_call(text, _categories(), LOC)
    by_slot = {u.slot: u for u in call.updates}
    assert by_slot["eyes"].category == "eyes"
    assert by_slot["eyes"].is_expression_folder is True
    assert by_slot["mouth"].category == "mouth"


def test_change_portrait_call_categorizes_glow_and_magic_layers():
    text = '$ ChangePortrait(chara="Cove_8", eye_glow="on", magic_effect="shimmer")'
    call = parse_change_portrait_call(text, _categories(), LOC)
    by_slot = {u.slot: u for u in call.updates}
    assert by_slot["eye_glow"].category == "glow"
    assert by_slot["eye_glow"].is_expression_folder is False  # not in this test's expressions set
    assert by_slot["magic_effect"].category == "magic"


def test_change_portrait_call_categorizes_plain_layers():
    text = '$ ChangePortrait(chara="Cove_8", base="default")'
    call = parse_change_portrait_call(text, _categories(), LOC)
    assert call.updates[0].category == "plain"
    assert call.updates[0].is_expression_folder is False


def test_change_portrait_call_resolves_blink_and_transition_flags():
    text = '$ ChangePortrait(chara="Cove_8", blink=False, transition=False, base="default")'
    call = parse_change_portrait_call(text, _categories(), LOC)
    assert call.blink is False
    assert call.transition is False


def test_change_portrait_call_resolves_tint_from_a_matrix_chain():
    # Real content: matrix=im.matrix.saturation(1.0)*im.matrix.tint(1.0,1.0,1.0)*im.matrix.brightness(-0.0)
    # -- saturation/brightness have no engine equivalent and are ignored;
    # only the tint(...) factor is pulled out.
    text = (
        '$ ChangePortrait(chara="Cove_8", base="default", '
        "matrix=im.matrix.saturation(1.0)*im.matrix.tint(0.75,0.85,1.0)*im.matrix.brightness(-0.0))"
    )
    call = parse_change_portrait_call(text, _categories(), LOC)
    assert call.tint == (0.75, 0.85, 1.0)


def test_change_portrait_call_with_a_matrix_chain_containing_no_tint_is_none():
    text = '$ ChangePortrait(chara="Cove_8", base="default", matrix=im.matrix.saturation(0.5))'
    call = parse_change_portrait_call(text, _categories(), LOC)
    assert call.tint is None


def test_change_portrait_call_with_a_non_literal_chara_is_unresolvable():
    text = '$ ChangePortrait(chara=some_var, base="default")'
    assert parse_change_portrait_call(text, _categories(), LOC) is None


def test_change_portrait_call_with_a_non_literal_slot_value_is_unresolvable():
    text = '$ ChangePortrait(chara="Cove_8", base=some_expr())'
    assert parse_change_portrait_call(text, _categories(), LOC) is None


def test_change_portrait_call_with_positional_chara_argument():
    text = '$ ChangePortrait("Cove_8", base="default")'
    call = parse_change_portrait_call(text, _categories(), LOC)
    assert call is not None
    assert call.name == "Cove_8"


def test_non_change_portrait_statement_returns_none():
    assert parse_change_portrait_call('$ SomeOtherCall(x="y")', _categories(), LOC) is None
