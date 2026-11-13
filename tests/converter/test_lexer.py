from converter.parser.lexer import tokenize_lines


def test_single_line_statements_are_unaffected():
    source = """
    label start:
        "Hi."
        return
    """
    lines = tokenize_lines(source)
    texts = [line.text for line in lines]
    assert texts == ["label start:", '"Hi."', "return"]


def test_multi_line_call_with_nested_parens_and_brackets_merges_into_one_line():
    # real-world shape: `image X = LayeredImage(size=(750, 1300),
    # layers=("Base*", "eyes *"), attribute_sets=(set(A), {"faceleft"}))`
    # spread across many physical lines -- previously each continuation
    # line became its own bogus "unsupported statement" (confirmed against
    # real content: ~900 of Mice Tea's ~1000 "unknown"-category blocking
    # items were exactly this).
    source = '''
    image afd_l = CharacterImage(
        character_name="afd",
        size=(750, 1300),
        layers=(
            "Base*",
            "eyes *", "Eyes *"
        ),
        attribute_sets=(
            set(AFD_L_EYES),
            {"faceleft", "faceright"}
        ),
    )

    label start:
        return
    '''
    lines = tokenize_lines(source)
    texts = [line.text for line in lines]
    assert len(texts) == 3
    assert texts[0].startswith('image afd_l = CharacterImage( character_name="afd",')
    assert texts[0].endswith(")")
    assert texts[1] == "label start:"
    assert texts[2] == "return"


def test_blank_lines_inside_a_continuation_are_ignored_not_terminating():
    source = '''
    image x = Foo(

        a=1,

        b=2,
    )
    '''
    lines = tokenize_lines(source)
    assert len(lines) == 1
    assert lines[0].text == "image x = Foo( a=1, b=2, )"


def test_triple_quoted_string_spanning_lines_is_merged_as_literal_text():
    source = '''
    init python:
        x = """
        line one # not a real comment, inside the triple-quote
        line two
        """
    '''
    lines = tokenize_lines(source)
    texts = [line.text for line in lines]
    assert len(texts) == 2
    assert texts[0] == "init python:"
    assert '# not a real comment' in texts[1]
    assert texts[1].startswith('x = """')
    assert texts[1].endswith('"""')


def test_comment_after_a_real_statement_is_still_stripped():
    source = """
    label start:  # entry point
        return
    """
    lines = tokenize_lines(source)
    assert lines[0].text == "label start:"


def test_hash_inside_a_single_line_string_is_not_a_comment():
    source = '''
    label start:
        "This has a # inside it"
        return
    '''
    lines = tokenize_lines(source)
    assert lines[1].text == '"This has a # inside it"'


def test_indent_of_merged_line_comes_from_its_first_physical_line():
    source = '''
    label start:
        image x = Foo(
            a=1,
        )
    '''
    lines = tokenize_lines(source)
    merged = lines[1]
    assert merged.indent == lines[0].indent + 4
