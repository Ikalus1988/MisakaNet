#!/usr/bin/env python3
"""Compare two self-healing benchmark result documents.

The report distinguishes changed outcomes from performance regressions so a
run can be reviewed without manually diffing large JSON files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _tasks(document):
    rows = document.get("tasks", document.get("results", []))
    return {row.get("task_id", row.get("task")): row for row in rows}


def compare_documents(baseline, candidate):
    """Return outcome, speed, and cost changes between two runs."""
    before = _tasks(baseline)
    after = _tasks(candidate)
    changed = []
    regressions = []
    for task_id in sorted(set(before) | set(after)):
        old = before.get(task_id)
        new = after.get(task_id)
        if old is None or new is None:
            changed.append({"task_id": task_id, "change": "added" if old is None else "removed"})
            continue
        old_outcome = old.get("outcome", "success" if old.get("success") else "failure")
        new_outcome = new.get("outcome", "success" if new.get("success") else "failure")
        old_ms = float(old.get("duration_ms", old.get("time_seconds", 0) * 1000))
        new_ms = float(new.get("duration_ms", new.get("time_seconds", 0) * 1000))
        old_cost = float(old.get("cost_usd", 0))
        new_cost = float(new.get("cost_usd", 0))
        if old_outcome != new_outcome:
            changed.append({
                "task_id": task_id,
                "before": old_outcome,
                "after": new_outcome,
            })
        if old_outcome == "success" and new_outcome != "success":
            regressions.append({"task_id": task_id, "kind": "outcome", "before": old_outcome, "after": new_outcome})
        if new_ms > old_ms * 1.2 and new_ms - old_ms >= 1:
            regressions.append({"task_id": task_id, "kind": "slower", "before_ms": old_ms, "after_ms": new_ms})
        if new_cost > old_cost and new_cost > 0:
            regressions.append({"task_id": task_id, "kind": "more_expensive", "before_usd": old_cost, "after_usd": new_cost})

    old_rate = baseline.get("summary", {}).get("success_rate")
    new_rate = candidate.get("summary", {}).get("success_rate")
    return {
        "baseline_run_id": baseline.get("run_id", "unknown"),
        "candidate_run_id": candidate.get("run_id", "unknown"),
        "changed_outcomes": changed,
        "regressions": regressions,
        "summary": (
            f"{len(changed)} outcome changes; {len(regressions)} regressions; "
            f"success rate {old_rate!s} -> {new_rate!s}"
        ),
    }


def compare_files(baseline_path, candidate_path):
    """Load two result JSON files and compare them."""
    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    candidate = json.loads(Path(candidate_path).read_text(encoding="utf-8"))
    return compare_documents(baseline, candidate)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()
    report = compare_files(args.baseline, args.candidate)
    print(json.dumps(report, indent=2) if args.json else report["summary"])
    return 1 if report["regressions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
