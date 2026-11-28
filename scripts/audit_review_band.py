#!/usr/bin/env python3
"""The "review band" either runs to completion or says so — it does not stop in the middle.

`docs/maintainer/intake-triage.md` §2 defines the handling for the one structural class of intake
this repository can never convert: the September/October form had **no `## Root Cause` field**, so
those reports are complete as reports and impossible as lessons. The prescribed handling is a single
template comment carrying `<!-- needs-root-cause -->` plus three exits (supply a cause / answer
"unknown" / answer "close").

Why this script exists (2026-11-28)
-----------------------------------
That band had been executed **partially and silently**. Measured over the 90 open old-form intakes:

* 90 carried `needs-info` — the label half of the band had run, at some point;
* **12 of them had never received the comment** — the half that actually asks the reporter, i.e. the
  only half that can ever move the issue.

Nothing was broken. A label applied looks identical to a label applied along with a question, and a
job that stamps 60 of 90 items and exits 0 has the same colour as one that stamps 90. The only
difference is 12 issues that wait forever, and no surface where that number appears.

So the statistic is not "how many are labelled". It is **"how many are labelled without having been
asked"**, and this script's job is to be the thing that fails on a non-zero value.

Why the marker and not the label
--------------------------------
`<!-- needs-root-cause -->` is already in the published template and is already how the replay avoids
double-commenting (`emit_intake_receipt.py` reads it the same way). It is checked in the issue's
**comments**, because the question is "was this reporter asked", not "was this issue tagged".

Exit status
-----------
::

    status 0   every old-form intake has been asked
    status 1   at least one has not   -> the band stopped in the middle, finish it
    status 2   the queue could not be read (0 issues / gh failed) -> 0/0 is not a pass

`--report` (the default) prints the work list. `--json` emits it for a workflow step. Nothing here
writes to GitHub: the band is a human/agent action, and a script that commented on 90 anonymous
reporters by itself would be the wrong shape.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

from pathlib import Path as Path_  # `--summary` only; the queue itself is read through `gh`

REPO = "Ikalus1988/MisakaNet"

#: The form generations. The field that makes an intake structurally unconvertible appeared in
#: November; before that, `## Root Cause` was not a section the form emitted at all.
OLD_FORM_MONTHS = ("2026-09", "2026-10")

#: The marker the published template carries. It is in `docs/maintainer/intake-triage.md` §2 and in
#: every comment already sent, so it is the stable identifier — not the wording around it.
MARKER = "<!-- needs-root-cause -->"


def _gh(*args: str) -> str:
    """`gh`, with the encoding named.

    Same reason as `label_audit.load` (#5139/#5153): without `encoding=`, Windows decodes the output
    as GBK, the reader thread raises, and subprocess swallows it — leaving `stdout` empty, which then
    parses as "no issues" and reads as a clean run.
    """
    out = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        raise SystemExit(f"gh {' '.join(args)} failed: {(out.stderr or '')[:300]}")
    return out.stdout


def open_intakes() -> list[dict]:
    raw = _gh("issue", "list", "--repo", REPO, "--state", "open", "--label", "mcp-intake",
              "--limit", "1000", "--json", "number,title,createdAt")
    rows = json.loads(raw or "[]")
    return [r for r in rows if str(r.get("title", "")).startswith("[Intake]")]


def asked(number: int) -> bool:
    """Whether the template comment is already on this issue.

    **Paginated**, because the question is ``has this marker appeared at all``: comments come back
    oldest-first and one page is the *oldest* 100, so a single-page read would answer ``no`` for an
    issue whose reply is simply older than the last 100 comments — and ``no`` here means posting the
    template a second time (`tests/test_github_list_reads_paginate.py` owns this rule; measured
    2026-10-04: seven issues here carry >100 comments, one carries 249).
    """
    # One line on purpose: `test_github_list_reads_paginate`'s scanner looks at the line carrying
    # the `per_page=`, so `--paginate` must be on it. (The scanner also accepts `--paginate` as
    # pagination — teaching it that was part of this change.)
    raw = _gh("api", f"repos/{REPO}/issues/{number}/comments?per_page=100", "--paginate", "--jq", '[.[] | select(.body | contains("needs-root-cause"))] | length')  # noqa: E501
    # `--jq` runs **per page** under `--paginate`, so the counts print one per page and concatenate
    # ("100" + "0" = 1000). Summing the emitted lines is the correct read of the same document.
    try:
        return sum(int(line) for line in (raw or "").split() if line.strip()) > 0
    except ValueError:
        return False


def band(number: int, created_at: str) -> str:
    """Which band this intake belongs to, from the form generation alone."""
    return "old-form" if str(created_at)[:7] in OLD_FORM_MONTHS else "current-form"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="emit the work list as JSON")
    ap.add_argument("--summary", metavar="JSON",
                    help="read a `--json` payload from this path and print it as markdown")
    ap.add_argument("--limit", type=int, default=1000)
    args = ap.parse_args(argv)

    if args.summary:
        # A separate mode rather than an inline heredoc in the workflow: a `python3 - <<'PY'` block
        # inside a YAML `run:` folds the document's indentation into the heredoc, and the first
        # version of the workflow did not parse at all.
        payload = json.loads(Path_(args.summary).read_text(encoding="utf-8"))
        print(f"open intakes **{payload['open_intakes']}** · old form **{payload['old_form']}** · "
              f"never asked **{payload['old_form_unasked']}**")
        if payload["numbers"]:
            print("\n" + ", ".join(f"#{n}" for n in payload["numbers"]))
        return 0

    intakes = open_intakes()
    if not intakes:
        # 0/0 is not a pass (#3759): an empty read means the query is broken, not that the queue is
        # clean, and a green run from a broken query is the failure this whole file is about.
        print("read 0 open intakes — that is a broken query, not a clean queue", file=sys.stderr)
        return 2

    old = [i for i in intakes if band(i["number"], i["createdAt"]) == "old-form"]
    missing = sorted(i["number"] for i in old if not asked(i["number"]))

    report = {
        "open_intakes": len(intakes),
        "old_form": len(old),
        "old_form_unasked": len(missing),
        "numbers": missing,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(f"open intakes {len(intakes)} — old form {len(old)} — "
              f"old-form without the template reply {len(missing)}")
        for n in missing:
            print(f"  #{n}")

    if missing:
        print(
            "\nThe review band stopped in the middle: these issues carry `needs-info` but were never "
            "asked for a cause, so nothing can move them. The comment is the template in "
            "`docs/maintainer/intake-triage.md` §2; post it verbatim (it carries "
            f"`{MARKER}` so a re-run will not double-comment).",
            file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
