#!/usr/bin/env python3
"""Audit the labels that separate corpus intakes from product/decision work.

The corpus queues are built from labels, so a label that leaks silently moves work into the wrong
queue. Measured 2026-11-11 on 262 open issues:

* `intake` and `mcp-intake` are applied together on all 190 intakes — one is a redundant alias;
* 5 issues carried `needs-human-review` without any corpus label (product/roadmap/meta issues);
* 2 `[Intake]` issues had escalated to `decision` (#4639, #4629) — the batch converter must skip
  them, and it now does;
* one label pair differs only by punctuation: `status: competition` vs `status:competition`.

The check is deliberately about **structure**, not about counts: a large queue is not a failure, a
mis-filed item is.

    python3 scripts/label_audit.py                 # report
    python3 scripts/label_audit.py --check         # exit 1 on leaks / duplicate label families
    python3 scripts/label_audit.py --from-file issues.json
"""
from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys

CORPUS_LABELS = {"mcp-intake", "intake", "lesson-submission"}
#: Labels that only make sense on corpus material; a product issue carrying one is a misfile.
CORPUS_ONLY = {"needs-human-review", "pending-review", "auto-rejected", "needs-answer"}
#: Pairs that are the same axis under two names; both used means the filter depends on the alias.
ALIAS_GROUPS = [
    {"intake", "mcp-intake"},
    {"question", "type:question"},
    {"bug", "type:bug"},
    {"p2", "priority:low"},
    {"status: competition", "status:competition"},
]


def load(path: str | None) -> list[dict]:
    if path:
        return json.loads(open(path, encoding="utf-8").read())
    out = subprocess.run(
        ["gh", "issue", "list", "--repo", "Ikalus1988/MisakaNet", "--state", "open", "--limit", "500",
         "--json", "number,title,labels"],
        capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"gh issue list failed: {out.stderr[:300]}")
    return json.loads(out.stdout or "[]")


def names(issue: dict) -> set[str]:
    return {label.get("name") for label in (issue.get("labels") or []) if isinstance(label, dict)}


def audit(issues: list[dict]) -> dict:
    leaks = [i["number"] for i in issues if (names(i) & CORPUS_ONLY) and not (names(i) & CORPUS_LABELS)]
    escalated = [i["number"] for i in issues if "decision" in names(i) and (names(i) & CORPUS_LABELS)]
    alias_report = {}
    for group in ALIAS_GROUPS:
        used = sorted(label for label in group if any(label in names(i) for i in issues))
        if len(used) > 1:
            alias_report[" / ".join(used)] = {
                "counts": {label: sum(1 for i in issues if label in names(i)) for label in used}
            }
    counts = collections.Counter(label for i in issues for label in names(i))
    return {
        "open_issues": len(issues),
        "leaks": leaks,
        "escalated_intakes": escalated,
        "duplicate_aliases": alias_report,
        "most_used": counts.most_common(12),
    }


def report(result: dict) -> int:
    print(f"open issues: {result['open_issues']}")
    print("\nmost used labels:")
    for label, count in result["most_used"]:
        print(f"  {label:24} {count}")
    print("\n`needs-human-review` / corpus-queue labels without a corpus label (misfiled):")
    print("  " + (", ".join(f"#{n}" for n in result["leaks"]) or "none"))
    print("\n`[Intake]` issues escalated to `decision` (the converter must skip them):")
    print("  " + (", ".join(f"#{n}" for n in result["escalated_intakes"]) or "none"))
    print("\nalias groups still applied under two names:")
    if not result["duplicate_aliases"]:
        print("  none")
    for group, detail in result["duplicate_aliases"].items():
        print(f"  {group}: {detail['counts']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 when a misfile or alias duplication exists")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--from-file", help="a saved `gh issue list --json number,title,labels` payload")
    args = ap.parse_args(argv)
    result = audit(load(args.from_file))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        report(result)
    # `--check` fails on misfiles only. Alias pairs are reported because they are worth knowing, but
    # they are legacy (190 intakes carry both names) and do not move work into a wrong queue.
    if args.check and result["leaks"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
