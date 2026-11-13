"""Shared "flagged construct" record produced while emitting script.vnds.

Phase 1.3 (the full problems.json Problem Report, with severity/category/
message/suggestion) consumes this list; this module only owns the sequential
P#### id scheme so ids emitted as "# FLAGGED P0001" comments in script.vnds
are stable and match what 1.3 later reports.
"""
from __future__ import annotations

from dataclasses import dataclass

from converter.parser import SourceLocation


@dataclass
class FlaggedItem:
    id: str
    text: str
    reason: str
    loc: SourceLocation


class FlaggedItems:
    def __init__(self) -> None:
        self._items: list[FlaggedItem] = []

    def add(self, text: str, reason: str, loc: SourceLocation) -> str:
        item_id = f"P{len(self._items) + 1:04d}"
        self._items.append(FlaggedItem(id=item_id, text=text, reason=reason, loc=loc))
        return item_id

    @property
    def items(self) -> list[FlaggedItem]:
        return list(self._items)
