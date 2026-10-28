#!/usr/bin/env python3
"""Give `answered` to closed question issues whose thread already contains an answer.

Why this exists (2026-10-28)
----------------------------
Measured before running it: **79 closed `question` issues, 42 of them without the `answered` label**,
and `sync_answered_questions.py` skips anything unlabelled. So 42 questions had answers written in
their threads and were **permanently unsearchable** — not wrong, not stale, just never indexed,
with no mechanism that would ever notice.

Running it moved D1 `questions` from 36 answered to 73 (30% → 60% of the question corpus searchable),
and 38 of the 42 had an extractable answer. The other four genuinely had none.

The durable part is why it is a script and not a one-off: the label is the only entry point to the
sync, and nothing adds it on close. Run this on a schedule (it is wired into
`sync-question-answers.yml`) and the backlog cannot re-form.

The rule is the sync's own — `extract_answer` from `sync_answered_questions.py`, which requires an
`ANSWER_MARKERS` hit and no `AUTOMATED_MARKERS`. Re-implementing it here would let the two disagree
about what an answer is.

Usage
-----
    python3 scripts/backfill_answered_labels.py             # report only
    python3 scripts/backfill_answered_labels.py --apply     # label them
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

from sync_answered_questions import extract_answer

LABEL = "answered"


def gh_json(args: list[str]) -> list:
    out = subprocess.run(["gh", *args], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"error: gh {' '.join(args)} failed: {out.stderr[:300]}")
    return json.loads(out.stdout or "[]")


def candidates() -> list[dict]:
    """Closed question issues with no `answered` label that DO have an answer in-thread."""
    issues = gh_json(["issue", "list", "--state", "closed", "--label", "question", "--limit", "500",
                      "--json", "number,title,labels,comments,closedAt"])
    found = []
    for issue in issues:
        labels = {l["name"] for l in issue["labels"]}
        if LABEL in labels:
            continue
        comments = [{"body": c["body"], "createdAt": c["createdAt"], "id": c["id"]}
                    for c in issue.get("comments") or []]
        answer, created_at, comment_id = extract_answer(comments)
        if not answer:
            continue
        found.append({"number": issue["number"], "title": issue["title"],
                      "closed_at": issue.get("closedAt"), "answer_id": comment_id,
                      "answer_chars": len(answer)})
    return sorted(found, key=lambda i: i["number"])


def label(issue_number: int) -> bool:
    out = subprocess.run(["gh", "issue", "edit", str(issue_number), "--add-label", LABEL],
                         capture_output=True, text=True)
    return out.returncode == 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="add the label (default: report only)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows = candidates()
    if args.json:
        print(json.dumps({"candidates": rows, "count": len(rows)}, ensure_ascii=False, indent=1))
    else:
        print(f"{len(rows)} closed question issue(s) carry an answer but no `{LABEL}` label")
        for row in rows:
            print(f"  #{row['number']:5d} {row['answer_chars']:5d} chars  {row['title'][:70]}")

    if not args.apply or not rows:
        return 0

    failed = [row["number"] for row in rows if not label(row["number"])]
    print(f"labelled {len(rows) - len(failed)}/{len(rows)}"
          + (f"; failed: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
