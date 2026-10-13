#!/usr/bin/env python3
"""Re-score the intakes an *older* scorer rejected, because a scorer fix is forward-only.

`intake-auto-review.yml` runs on `issues: [opened, reopened]`. Nothing re-scores an issue
that already carries `auto-rejected`, so every time the scorer itself is fixed, the items the
fix was diagnosed from keep the stale verdict — and the pile only grows. The fix changes what
happens to the *next* report, never to the report that proved the bug.

Measured 2026-10-13 over the 25 open `auto-rejected` intakes:

    #3080  review  44.5      #3101  review  44.0      #3192  review  45.8
    22 others still reject — the label is correct for those

Two of those three are the issues the scorer defects were **diagnosed from**: #3080 is the
Chinese-report language bias (§86.4) and #3192 is the `1.` list-item false negative
(§87.3, fixed by #3220). The fix shipped; the two items it came from were never re-scored.

Dry-run by default, because relabelling moves work into the human queue. `--apply` mirrors
the workflow's own mapping and also drops `needs-salvage`: the workflow leaves it, but it is
a reject-side label, and the point is to clear a stale verdict rather than move it sideways.

Usage:
    python3 scripts/rescore_rejected_intakes.py             # report only
    python3 scripts/rescore_rejected_intakes.py --apply     # relabel what changed
    python3 scripts/rescore_rejected_intakes.py --json      # machine-readable
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

DEFAULT_LABEL = "auto-rejected"
# The four the workflow clears before applying its verdict, plus `needs-salvage` (this script's
# deliberate addition — see the module docstring).
CLEARED_LABELS = ("auto-approved", "auto-rejected", "needs-human-review", "pending-review")
SALVAGE_LABEL = "needs-salvage"


def _run_gh(args: list[str]) -> str:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def open_rejected(label: str = DEFAULT_LABEL, limit: int = 100) -> list[dict]:
    """Every open issue carrying the reject label, with the body the scorer needs."""
    out = _run_gh(["issue", "list", "--state", "open", "--label", label, "--limit", str(limit),
                   "--json", "number,title,body"])
    return json.loads(out or "[]")


def label_changes(decision: str) -> tuple[list[str], list[str]]:
    """`(remove, add)` for a verdict — the same mapping `intake-auto-review.yml` applies.

    Keeping this in one place is the point: if the workflow's mapping changes, the re-score
    must change with it, and a test pins the shape rather than the prose.
    """
    if decision == "approve":
        return list(CLEARED_LABELS), ["auto-approved", "needs-human-review"]
    if decision == "reject":
        return list(CLEARED_LABELS), ["auto-rejected", SALVAGE_LABEL]
    return list(CLEARED_LABELS), ["needs-human-review"]


def plan(issues: list[dict], score) -> list[dict]:
    """Diff each issue's *current* verdict against the current scorer. Pure; no network.

    `score(issue_number, title, body) -> (decision, weighted_score)` is injected so the
    decision logic can be tested without touching GitHub or the real scorer.
    """
    changes: list[dict] = []
    for issue in issues:
        number = issue["number"]
        decision, weighted = score(number, issue.get("title", ""), issue.get("body") or "")
        if decision == "reject":
            continue                      # the label is right; nothing to do
        remove, add = label_changes(decision)
        changes.append({
            "number": number,
            "decision": decision,
            "weighted_score": weighted,
            "remove": remove + [SALVAGE_LABEL],
            "add": add,
        })
    return changes


def apply_changes(changes: list[dict]) -> None:
    for change in changes:
        args = ["issue", "edit", str(change["number"])]
        for label in change["remove"]:
            args += ["--remove-label", label]
        for label in change["add"]:
            args += ["--add-label", label]
        _run_gh(args)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", default=DEFAULT_LABEL, help=f"label to re-check (default: {DEFAULT_LABEL})")
    parser.add_argument("--limit", type=int, default=100, help="how many open issues to read")
    parser.add_argument("--apply", action="store_true",
                        help="actually relabel; without it this is a report")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    try:
        issues = open_rejected(args.label, args.limit)
    except RuntimeError as exc:
        print(f"cannot run: {exc}", file=sys.stderr)
        return 2
    if not issues:
        print(f"# no open issue carries `{args.label}` — nothing to re-score")
        return 0

    from intake_auto_review import auto_review_issue        # noqa: E402  (path set above)

    def score(number: int, title: str, body: str) -> tuple[str, float]:
        result = auto_review_issue(number, title, body)
        return result.decision, round(float(result.weighted_score), 1)

    changes = plan(issues, score)

    if args.json:
        print(json.dumps({"checked": len(issues), "changed": changes}, ensure_ascii=False, indent=2))
    else:
        print(f"# re-scored {len(issues)} open `{args.label}` issue(s) against the current scorer")
        if not changes:
            print(f"# every verdict still holds — the label is correct on all {len(issues)}")
        else:
            print(f"# {len(changes)} no longer reject under current rules "
                  f"(the label is stale, not the report):")
            for change in sorted(changes, key=lambda c: -c["weighted_score"]):
                print(f"    #{change['number']:<6} {change['decision']:<8} weighted="
                      f"{change['weighted_score']:<6} → remove {','.join(change['remove'])} "
                      f"/ add {','.join(change['add'])}")
            if not args.apply:
                print("\n# dry run — nothing was changed. Re-run with --apply to relabel.")

    if args.apply and changes:
        apply_changes(changes)
        print(f"# applied {len(changes)} relabel(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
