"""Problem Report schema (VN3DS-spec.md §7.2).

Severity levels (exact spec wording):
- blocking: the game cannot reach a correct state without human work. Must
  be zero before a game counts as "ported."
- manual: converted to a placeholder/stub; needs a human to reimplement
  natively (custom screen, ATL animation, achievements).
- approximated: converted, but behavior simplified. Playable as-is; review
  for fidelity.
- info: noted, no action needed (e.g. a downscaled background).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["blocking", "manual", "approximated", "info"]
Category = Literal[
    "python", "screen", "atl", "displayable", "video", "text-tag", "audio", "asset", "flow", "unknown"
]

SEVERITIES: tuple[Severity, ...] = ("blocking", "manual", "approximated", "info")


@dataclass
class Problem:
    id: str
    severity: Severity
    category: Category
    source: str  # "file:line"
    ren_py: str  # truncated source snippet
    message: str
    suggestion: str
