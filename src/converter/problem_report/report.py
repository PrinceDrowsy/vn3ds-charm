"""Builds and emits the Problem Report (problems.json + a human-readable table),
per VN3DS-spec.md §7.2-7.3.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone

from converter.emitters import FlaggedItem, FlaggedItems
from converter.parser import Unsupported

from .classify import classify
from .schema import SEVERITIES


def build_problem_report(
    game: str,
    converter_version: str,
    flagged: FlaggedItems,
    *,
    parser_problems: list[Unsupported] | None = None,
    generated: str | None = None,
) -> dict:
    # The parser and the emitter each discover their own flagged constructs
    # (parser: malformed defines, unrecognized menu syntax, etc; emitter:
    # things only visible once flattening into VNDS's flat label format).
    # Both must land in the same report, so parser problems get folded into
    # a single P#### id sequence continuing after the emitter's.
    items: list[FlaggedItem] = list(flagged.items)
    # Statement-level parser problems (reason "unsupported statement") are
    # embedded as Unsupported nodes in the IR, so the emitter's tree walk
    # already flags them too — only top-level/definition-level parser
    # problems (which never reach the emitter, since they're dropped before
    # anything is added to script.labels/characters) are genuinely new here.
    seen = {(item.reason, item.text, str(item.loc)) for item in items}
    next_id = len(items) + 1
    for problem in parser_problems or []:
        key = (problem.reason, problem.text, str(problem.loc))
        if key in seen:
            continue
        seen.add(key)
        items.append(FlaggedItem(id=f"P{next_id:04d}", text=problem.text, reason=problem.reason, loc=problem.loc))
        next_id += 1

    problems = [classify(item) for item in items]
    summary = {severity: 0 for severity in SEVERITIES}
    for problem in problems:
        summary[problem.severity] += 1
    summary["total"] = len(problems)

    return {
        "game": game,
        "converter_version": converter_version,
        "generated": generated or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": summary,
        "items": [asdict(problem) for problem in problems],
    }


def emit_problems_json(report: dict) -> str:
    return json.dumps(report, sort_keys=True, indent=2) + "\n"


def has_blocking(report: dict) -> bool:
    return report["summary"]["blocking"] > 0


def format_report_table(report: dict) -> str:
    """A human-readable rendering of the report, for problems.md / console
    output alongside the JSON (spec §7.3 acceptance criteria)."""
    summary = report["summary"]
    lines = [
        f"Problem Report - {report['game']} (converter {report['converter_version']})",
        f"Generated: {report['generated']}",
        "",
        f"Total: {summary['total']}  Blocking: {summary['blocking']}  "
        f"Manual: {summary['manual']}  Approximated: {summary['approximated']}  "
        f"Info: {summary['info']}",
        "",
    ]
    for item in report["items"]:
        lines.append(f"[{item['severity'].upper():12}] {item['id']} ({item['category']}) {item['source']}")
        lines.append(f"    {item['message']}")
        lines.append(f"    ren'py: {item['ren_py']}")
        if item["suggestion"]:
            lines.append(f"    -> {item['suggestion']}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"
