"""Witch's command line.

    python -m witch convert GAME_DIR --scratch DIR -o OUT.charm [--report DIR]
    python -m witch verify BUNDLE [--report DIR]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .renpy.graph import build
from .renpy.harvester import harvest
from .report import Report
from .verify import verify


def _finish(report: Report, name: str, report_dir: Path | None) -> int:
    if report_dir:
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "problems.json").write_text(report.to_json(), encoding="utf-8")
        (report_dir / "problems.md").write_text(report.to_markdown(), encoding="utf-8")
    gating = [p for p in report.ordered() if p.gates]
    for p in gating[:20]:
        where = f"{p.file}:{p.line}" if p.file else "bundle"
        print(f"{p.severity}: {where}: {p.message}")
    if len(gating) > 20:
        print(f"... and {len(gating) - 20} more")
    print(f"{name}: {'FAILED' if report.failed else 'ok'} ({len(gating)} gating, {len(report.problems)} total)")
    return 1 if report.failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="witch")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("convert", help="convert an installed Ren'Py game into a .charm bundle")
    c.add_argument("game", type=Path)
    c.add_argument("--scratch", type=Path, required=True, help="where the game is copied and run for harvesting")
    c.add_argument("-o", "--output", type=Path, required=True)
    c.add_argument("--report", type=Path, help="directory for problems.json and problems.md")
    v = sub.add_parser("verify", help="check a .charm bundle and write its Problem Report")
    v.add_argument("bundle", type=Path)
    v.add_argument("--report", type=Path, help="directory for problems.json and problems.md")
    args = parser.parse_args(argv)

    if args.command == "verify":
        return _finish(verify(args.bundle.read_bytes(), args.bundle.name), args.bundle.name, args.report)

    h = harvest(args.game, args.scratch)
    data = build(h).write()
    args.output.write_bytes(data)
    print(f"{h['renpy_version']}: {len(h['nodes'])} nodes harvested, Ren'Py names {h['named_nodes']}, "
          f"{h['named_outside_graph']} named outside the graph")
    return _finish(verify(data, args.output.name), args.output.name, args.report)


if __name__ == "__main__":
    sys.exit(main())
