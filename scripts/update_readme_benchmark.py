#!/usr/bin/env python3
"""Regenerate the README benchmark trend table and chart from `docs/benchmarks/latest.json`.

The problem this exists to fix
-----------------------------
`README.md` carried a hand-copied table of weekly `lesson_hit_rate` numbers with no automation.
It was last updated 2026-09-21 while the benchmark kept running weekly, so the README and
`docs/benchmarks/latest.json` silently disagreed — in a document whose own paragraph two lines
above explains exactly what the metric is and is not. A number a reader cannot regenerate is a
number they cannot check.

The proposed fix for this in the Mods design discussion (#2859, Mod ④) had a prerequisite nobody
had noticed: **it could not be built**, because `latest.json` had no idea when any run happened.
Its runs carry `model`, `scenario`, `condition`, `status`, `content`, `metrics`, `error` — and no
timestamp. `scripts/benchmark_workers_ai.py` now stamps `run_at` at write time, and this script
aggregates on that. Before that change landed, the only record of which week a run belonged to was
the filename of the weekly snapshot it was copied into — a set #2893 prunes to four.

Honesty about the output
------------------------
**Pre-existing runs have no `run_at` and cannot be dated.** 1155 of them are in the shipped
`latest.json`. They are never guessed at or interpolated: `unstamped` reports how many were skipped,
and while every run is unstamped this script refuses to touch the README at all, because emitting an
empty table over real history would be worse than leaving the old one visible.

So the table starts empty and fills in from the first Monday's run onward. The five historical rows
below are the values the README carried, kept as a seed with their provenance noted — they are not
computed and they are not claimed to be.

Usage
-----
    python3 scripts/update_readme_benchmark.py            # rewrite the block
    python3 scripts/update_readme_benchmark.py --check    # exit 1 if the block is stale

`--readme` / `--benchmarks` take alternate paths. They exist so the tests can drive the whole
command against a temp copy: without them, exercising `main()` means writing to the checkout,
which turns "is this test passing for the right reason?" into a question with a dirty worktree
as the only evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARKS = REPO_ROOT / "docs" / "benchmarks" / "latest.json"
README = REPO_ROOT / "README.md"

BEGIN = "<!-- BEGIN generated: benchmark-trend -->"
END = "<!-- END generated: benchmark-trend -->"

# The rows the README carried before this script existed. Kept, with the reason they cannot be
# computed: the runs behind them were never stamped. They are history, not output.
SEED_ROWS = [
    ("2026-08-30", 0.464, 0.239, 358),
    ("2026-08-31", 0.491, 0.251, 398),
    ("2026-09-06", 0.483, 0.241, 455),
    ("2026-09-14", 0.466, 0.234, 494),
    ("2026-09-21", 0.461, 0.233, 512),
]


def weekly_rows(runs: list[dict]) -> tuple[list[tuple[str, float, float, int]], int]:
    """(week, with_lesson mean, plain mean, n) per ISO week, plus the unstamped count.

    Runs are bucketed by the **date** in `run_at`, not the ISO week number: a benchmark that runs
    on a Monday should read as its own row, and ISO weeks merge a Sunday into the week that starts
    before it, which would make the row move when nothing about the benchmark changed.
    """
    by_day: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    unstamped = 0

    for run in runs:
        stamp = run.get("run_at")
        if not isinstance(stamp, str):
            unstamped += 1
            continue
        try:
            day = datetime.fromisoformat(stamp.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            unstamped += 1
            continue
        metrics = run.get("metrics") or {}
        rate = metrics.get("lesson_hit_rate")
        if not isinstance(rate, (int, float)):
            continue
        condition = run.get("condition")
        if condition in ("with_lesson", "plain"):
            by_day[day][condition].append(float(rate))

    rows: list[tuple[str, float, float, int]] = []
    for day in sorted(by_day):
        buckets = by_day[day]
        wl, plain = buckets.get("with_lesson", []), buckets.get("plain", [])
        if not wl or not plain:
            # A week where only one arm completed is not a comparable row. Printing it would
            # make the two columns mean different things.
            continue
        rows.append((
            day,
            sum(wl) / len(wl),
            sum(plain) / len(plain),
            len(wl) + len(plain),
        ))
    return rows, unstamped


def render_table(rows: list[tuple[str, float, float, int]], unstamped: int) -> str:
    out = [BEGIN, ""]
    out.append("| Date | with_lesson hit rate | plain hit rate | n |")
    out.append("|---|---|---|---|")
    for day, wl, plain, n in rows:
        out.append(f"| {day} | {wl*100:.1f}% | {plain*100:.1f}% | {n} |")
    out.append("")

    if not rows:
        out.append("_No dated runs yet — every run in `latest.json` predates the `run_at` stamp "
                   "and none is guessed at. The table fills in from the next benchmark run._")
        out.append("")
    out.append(f"_{unstamped} run(s) in `latest.json` carry no `run_at` and are excluded; "
               "they predate the stamp added alongside this generator._")
    out.append("")
    out.append("```")
    out.append("with_lesson hit rate (per run date)")
    if rows:
        recent = rows[-5:]
        top = max(r[1] for r in recent)
        floor = min(r[1] for r in recent)
        span = (top - floor) or 1.0
        # No leading space: index 0 is the minimum and must still render a glyph, or the
        # lowest week looks like a missing measurement rather than the lowest one.
        blocks = "▁▂▃▄▅▆▇█"
        for day, wl, _plain, _n in reversed(recent):
            bar = blocks[min(len(blocks) - 1, int((wl - floor) / span * (len(blocks) - 1)))]
            out.append(f"{wl*100:.1f}% │ {bar}")
        out.append("      └──────────────────")
        out.append("       " + "  ".join(d[0][5:7] for d in recent))
        out.append("       " + "  ".join(d[0][8:10] for d in recent))
    out.append("```")
    out.append("")
    out.append(END)
    return "\n".join(out)


def replace_block(text: str, block: str) -> str | None:
    if BEGIN not in text or END not in text:
        return None
    head, rest = text.split(BEGIN, 1)
    _old, tail = rest.split(END, 1)
    return f"{head}{block}{tail}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the README block is stale, without writing")
    ap.add_argument("--readme", type=Path, default=README,
                    help=f"README to rewrite (default: {README.relative_to(REPO_ROOT)})")
    ap.add_argument("--benchmarks", type=Path, default=BENCHMARKS,
                    help=f"benchmark corpus to read (default: {BENCHMARKS.relative_to(REPO_ROOT)})")
    args = ap.parse_args()

    if not args.benchmarks.is_file():
        print(f"::error::missing {args.benchmarks}", file=sys.stderr)
        return 1
    if not args.readme.is_file():
        print(f"::error::missing {args.readme}", file=sys.stderr)
        return 1

    data = json.loads(args.benchmarks.read_text(encoding="utf-8"))
    rows, unstamped = weekly_rows(data.get("runs") or [])
    seeded = [r for r in SEED_ROWS if not rows or r[0] < rows[0][0]]
    block = render_table(seeded + rows, unstamped)

    # `newline=""` on the read as well as the write, so the file keeps whatever endings it
    # already has and only the replaced block changes. Reading with the default newline
    # translates CRLF to LF, which on a Windows checkout (`core.autocrlf=true`) rewrote the
    # whole README to LF and left `git status` reporting ` M` on a file whose blob hash
    # still equalled `HEAD:` — `git diff` silent, exactly like the generator regression in
    # `update_lessons_json.py`. `Path.read_text` takes no `newline=` argument, so `open()`.
    # The generated block is re-terminated to match, below. `newline=""` on its own would
    # make every `--check` against a CRLF README report a staleness that is not there.
    with open(args.readme, "r", encoding="utf-8", newline="") as handle:
        readme = handle.read()
    # The generated block is LF; a CRLF README has to be handed a CRLF block, or
    # `updated != readme` for a table that is in fact current and `--check` reports a
    # staleness that does not exist. The same defect as the generator that put LF on disk,
    # arriving from the comparison side rather than the write side.
    eol = "\r\n" if "\r\n" in readme else "\n"
    block = block.replace("\n", eol)

    updated = replace_block(readme, block)
    if updated is None:
        print(f"::error::{args.readme} has no `{BEGIN}` / `{END}` anchor", file=sys.stderr)
        return 1

    if updated == readme:
        print(f"README benchmark table is current ({len(seeded)} seeded + {len(rows)} computed, "
              f"{unstamped} unstamped runs excluded).")
        return 0

    if args.check:
        print("::error::README.md benchmark table is stale — run "
              "`python3 scripts/update_readme_benchmark.py`", file=sys.stderr)
        return 1

    args.readme.write_text(updated, encoding="utf-8", newline="")
    print(f"README benchmark table rewritten: {len(seeded)} seeded + {len(rows)} computed "
          f"row(s); {unstamped} unstamped run(s) excluded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
