"""Converts every Ren'Py game under a library folder and tabulates the result:
the R1 corpus metric (REWORK-PLAN §15, D20).

    python tools/witch/corpus.py LIBRARY_DIR --scratch DIR [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from witch.bundle.reader import Bundle  # noqa: E402
from witch.renpy.graph import build  # noqa: E402
from witch.renpy.harvester import HarvestError, harvest  # noqa: E402
from witch.verify import verify  # noqa: E402


def renpy_games(library: Path) -> list[Path]:
    return sorted(d for d in library.iterdir()
                  if d.is_dir() and (d / "renpy").is_dir() and any(d.glob("*.py")))


def run(game: Path, scratch: Path) -> dict:
    t0 = time.monotonic()
    try:
        h = harvest(game, scratch)
    except HarvestError as e:
        return {"game": game.name, "error": str(e).splitlines()[0]}
    # A game Witch can't convert yet is a result for this table, not a reason
    # to lose the rest of the corpus; the traceback goes to stderr.
    try:
        data = build(h).write()
    except Exception as e:
        traceback.print_exc()
        return {"game": game.name, "error": f"build: {type(e).__name__}: {e}"}
    (scratch / f"{game.name}.charm").write_bytes(data)
    report = verify(data, game.name)
    bundle = Bundle(data)
    unknown = Counter(n.fields["classname"] for n in map(bundle.node, range(bundle.count("NODE")))
                      if n.kind.name == "unknown")
    return {
        "game": game.name,
        "renpy": h["renpy_version"].replace("Ren'Py ", ""),
        "nodes": len(h["nodes"]),
        "named": h["named_nodes"],
        "outside": h["named_outside_graph"],
        "unknown_classes": dict(unknown),
        "summary": report.summary(),
        "codes": dict(Counter(p.code for p in report.problems if p.gates)),
        "seconds": round(time.monotonic() - t0, 1),
    }


def table(rows: list[dict]) -> str:
    out = ["| Game | Ren'Py | Nodes | Named | Outside | Unmapped classes | Crash | Stuck | Missing | Mismatch | s |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            out.append(f"| {r['game']} | harvest failed: {r['error']} |" + " |" * 9)
            continue
        reach = lambda sev: sum(n for k, n in r["summary"][sev].items() if k != "none")  # noqa: E731
        unmapped = ", ".join(f"{k} {v}" for k, v in sorted(r["unknown_classes"].items())) or "-"
        out.append(f"| {r['game']} | {r['renpy']} | {r['nodes']} | {r['named']} | {r['outside']} | {unmapped} | "
                   f"{reach('crash')} | {reach('stuck')} | {reach('missing')} | {reach('mismatch')} | {r['seconds']} |")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("library", type=Path)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    rows = []
    for game in renpy_games(args.library):
        print(f"{game.name}...", file=sys.stderr, flush=True)
        rows.append(run(game, args.scratch))
    if args.json:
        args.json.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(table(rows))


if __name__ == "__main__":
    main()
