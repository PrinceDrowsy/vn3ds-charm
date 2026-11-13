"""Indentation-aware line lexer for the Ren'Py subset parser.

Ren'Py source is block-structured like Python (indentation defines nesting),
but real .rpy files contain plenty of syntax outside our supported subset
(screens, ATL, python blocks). We only need reliable indentation + comment
stripping here; the parser decides what each line means.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RawLine:
    indent: int
    text: str  # stripped of comment and surrounding whitespace
    lineno: int


def _indent_of(line: str) -> int:
    expanded = line.expandtabs(4)
    return len(expanded) - len(expanded.lstrip(" "))


_OPEN_CHARS = "([{"
_CLOSE_CHARS = ")]}"
_TRIPLE_QUOTES = ('"""', "'''")


def _scan_continuation(text: str, in_triple: str | None) -> tuple[str, int, str | None]:
    """Scans one raw physical line, tracking paren/bracket/brace nesting
    depth and open triple-quoted-string state (both ignoring characters
    inside any quoted string, including one already open from a previous
    line via `in_triple`) -- the two things a genuine multi-line Python
    construct (an `image X = LayeredImage(...)` call spanning dozens of
    lines with nested `layers=(...)`/`attribute_sets=(...)`, or a
    `\"\"\"...\"\"\"` docstring) needs `tokenize_lines` to recognize as one
    logical statement rather than shredding into one bogus "unsupported
    statement" per physical line (confirmed against real content: this was
    ~900 of Mice Tea's ~1000 "unknown"-category blocking items). Returns
    (comment-stripped text, this line's own paren depth delta, the
    triple-quote state carried into the *next* line). A `#` is only ever
    treated as a real comment outside any string/triple-quote -- one
    appearing inside a multi-line docstring is literal text, not a
    comment, unlike the previous single-line-only `_strip_comment`."""
    out: list[str] = []
    depth = 0
    in_string: str | None = None
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_triple:
            if text[i : i + 3] == in_triple:
                out.append(in_triple)
                i += 3
                in_triple = None
                continue
            out.append(ch)
            i += 1
            continue
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == in_string:
                in_string = None
            i += 1
            continue
        if text[i : i + 3] in _TRIPLE_QUOTES:
            in_triple = text[i : i + 3]
            out.append(in_triple)
            i += 3
            continue
        if ch in ('"', "'"):
            in_string = ch
            out.append(ch)
            i += 1
            continue
        if ch == "#":
            break
        if ch in _OPEN_CHARS:
            depth += 1
        elif ch in _CLOSE_CHARS:
            depth -= 1
        out.append(ch)
        i += 1
    return "".join(out), depth, in_triple


def tokenize_lines(source: str) -> list[RawLine]:
    if source.startswith("﻿"):  # tolerate a leading UTF-8 BOM
        source = source[1:]
    raw_lines = source.splitlines()
    n = len(raw_lines)
    lines: list[RawLine] = []
    i = 0
    while i < n:
        text, depth, in_triple = _scan_continuation(raw_lines[i], None)
        if not text.strip() and in_triple is None and depth == 0:
            i += 1
            continue
        indent = _indent_of(raw_lines[i])
        lineno = i + 1
        combined = text.strip()
        j = i + 1
        while (depth > 0 or in_triple is not None) and j < n:
            piece, piece_depth, in_triple = _scan_continuation(raw_lines[j], in_triple)
            depth += piece_depth
            piece = piece.strip()
            if piece:
                combined = f"{combined} {piece}" if combined else piece
            j += 1
        if combined:
            lines.append(RawLine(indent=indent, text=combined, lineno=lineno))
        i = j
    return lines


class Cursor:
    """A single-pass, peekable cursor over a list of RawLine."""

    def __init__(self, lines: list[RawLine]):
        self._lines = lines
        self._pos = 0

    def peek(self) -> RawLine | None:
        return self._lines[self._pos] if self._pos < len(self._lines) else None

    def advance(self) -> RawLine:
        line = self._lines[self._pos]
        self._pos += 1
        return line

    def bookmark(self) -> int:
        """Returns an opaque position marker for `restore` — lets a
        speculative multi-line parse (e.g. a screen: block) back out
        cleanly and re-skip from scratch if it turns out to use something
        unsupported partway through, rather than leaving the cursor at an
        inconsistent mid-block position."""
        return self._pos

    def restore(self, bookmark: int) -> None:
        self._pos = bookmark
