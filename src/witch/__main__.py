"""Witch's command line: `python -m witch verify BUNDLE [--report DIR]`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .verify import verify


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="witch")
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("verify", help="check a .charm bundle and write its Problem Report")
    v.add_argument("bundle", type=Path)
    v.add_argument("--report", type=Path, help="directory for problems.json and problems.md")
    args = parser.parse_args(argv)

    report = verify(args.bundle.read_bytes(), args.bundle.name)
    if args.report:
        args.report.mkdir(parents=True, exist_ok=True)
        (args.report / "problems.json").write_text(report.to_json(), encoding="utf-8")
        (args.report / "problems.md").write_text(report.to_markdown(), encoding="utf-8")
    gating = [p for p in report.ordered() if p.gates]
    for p in gating[:20]:
        where = f"{p.file}:{p.line}" if p.file else "bundle"
        print(f"{p.severity}: {where}: {p.message}")
    if len(gating) > 20:
        print(f"... and {len(gating) - 20} more")
    print(f"{args.bundle.name}: {'FAILED' if report.failed else 'ok'} "
          f"({len(gating)} gating, {len(report.problems)} total)")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
