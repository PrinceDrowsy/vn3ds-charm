"""Problem Report v2 (REWORK-PLAN §13.2): problems ranked by what the player
would actually experience, and by whether play can reach them."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Literal

Severity = Literal["crash", "stuck", "missing", "mismatch", "cosmetic", "harmless"]
SEVERITIES: tuple[Severity, ...] = ("crash", "stuck", "missing", "mismatch", "cosmetic", "harmless")

# static: reachable from Ren'Py's entry labels by following the script.
# dynamic: reachable only from a label some `jump expression` or Python
#   `renpy.jump` could name; the static graph can't rule it out.
# none: no path leads there at all.
# The desktop runner (R3) turns these into measured reach counts.
Reach = Literal["static", "dynamic", "none"]
REACHES: tuple[Reach, ...] = ("static", "dynamic", "none")

GATING: frozenset[Severity] = frozenset({"crash", "stuck", "missing"})


@dataclass
class Problem:
    code: str
    severity: Severity
    reach: Reach
    message: str
    suggestion: str = ""
    file: str = ""
    line: int = 0
    node: str = ""  # Ren'Py's node name, when the problem belongs to a node

    @property
    def gates(self) -> bool:
        return self.severity in GATING and self.reach != "none"


@dataclass
class Report:
    bundle: str
    problems: list[Problem]

    @property
    def failed(self) -> bool:
        return any(p.gates for p in self.problems)

    def summary(self) -> dict[str, dict[str, int]]:
        counts = {s: {r: 0 for r in REACHES} for s in SEVERITIES}
        for p in self.problems:
            counts[p.severity][p.reach] += 1
        return counts

    def ordered(self) -> list[Problem]:
        return sorted(self.problems, key=lambda p: (SEVERITIES.index(p.severity), REACHES.index(p.reach),
                                                    p.file, p.line, p.code))

    def to_json(self) -> str:
        return json.dumps({
            "version": 2,
            "bundle": self.bundle,
            "failed": self.failed,
            "summary": self.summary(),
            "problems": [asdict(p) for p in self.ordered()],
        }, ensure_ascii=False, indent=1)

    def to_markdown(self) -> str:
        out = [f"# Problem Report: {self.bundle}", "",
               f"**{'FAILED' if self.failed else 'Passed'}**: "
               f"{sum(p.gates for p in self.problems)} reachable crash, stuck or missing-content problems.", "",
               "| Severity | " + " | ".join(REACHES) + " |", "|---|" + "---|" * len(REACHES)]
        for severity, row in self.summary().items():
            out.append(f"| {severity} | " + " | ".join(str(row[r]) for r in REACHES) + " |")
        current = None
        for p in self.ordered():
            if p.severity != current:
                current = p.severity
                out += ["", f"## {current}", ""]
            where = f"{p.file}:{p.line}" if p.file else "bundle"
            out.append(f"- `{p.code}` ({p.reach}) {where}: {p.message}" + (f" {p.suggestion}" if p.suggestion else ""))
        return "\n".join(out) + "\n"
