#!/usr/bin/env python3
"""Decide whether a lesson pull request may be squash-merged automatically (issue #1777).

Why the decision is a pure function in its own file
---------------------------------------------------
`.github/workflows/auto-merge-lessons.yml` holds a write token and performs an
irreversible action (a squash merge). Everything *mechanical* about that decision is kept
here, offline and side-effect free, so the whole rule set is unit-testable without a
network and without a repository to mutate: the workflow fetches the facts with `gh api`,
this module says merge / wait / refuse, and the workflow only acts on the verdict.

The trust boundary matters as much as the rules: the workflow runs *this file from the
default branch*, never the copy a pull request may carry, because a PR that could rewrite
its own gate could approve itself.

Verdicts
--------
``merge``   every mechanical condition holds — squash-merge it.
``wait``    nothing is wrong, something is simply not finished (a check is still running,
            a required check has not been reported at all, the opt-in label is absent).
            The workflow does **nothing** on ``wait``: no comment, no retry storm.
``refuse``  a condition is violated and only a human (or a new commit) can clear it. The
            workflow posts exactly one comment naming the blocker.

Refusals are ordered: the first blocker found is the one reported. Deny-list labels are
checked first, so an explicit "do not merge" is never silently outranked by anything else.
An absent opt-in label is a ``wait`` (the workflow is opt-in; a PR that never asked for
auto-merge must not be commented on or merged by it), but the deny-list is checked *before*
that, because a human explicitly saying "do not merge" always wins and must be visible.

CLI
---
    python3 scripts/lesson_pr_mergeable.py --json '<payload>'

prints ``<verdict>: <reason>`` and exits 0 for merge, 1 for refuse, 2 for wait. Exit 3
means the payload itself was unusable (bad JSON / not an object) and the caller must not
act on it — it is deliberately *not* 1, because 1 means "refuse", which posts a comment.

Payload shape (exactly what the workflow builds from the GitHub API)::

    {
      "files": ["lessons/contrib/foo.md"],          # changed paths
      "file_stats": {"lessons/contrib/foo.md": [42, 0]},  # path -> [additions, deletions]
      "checks": {"gate": "success", "provenance": "success",
                 "dco": "success", "audit-shape": "success",
                 "test (ubuntu-latest, 3.12)": "success"},  # name -> conclusion
      "labels": ["auto-merge-lesson"],
      "draft": false,
      "review_state": "APPROVED",                   # latest review state per author
      "body": "..."                                 # the PR body (reserved)
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Mapping, Sequence

# ── verdicts ─────────────────────────────────────────────────────────────────
MERGE = "merge"
WAIT = "wait"
REFUSE = "refuse"

EXIT_CODES = {MERGE: 0, REFUSE: 1, WAIT: 2}
# The payload was unusable; never 1, because 1 means "refuse" and posts a comment.
EXIT_BAD_PAYLOAD = 3

# ── the rules ────────────────────────────────────────────────────────────────
# The label a maintainer adds to opt a pull request into this channel.
OPT_IN_LABEL = "auto-merge-lesson"
# A human saying "not now" beats the opt-in label, whatever else is green.
DENY_LABELS = ("do-not-merge", "wip")

# Required checks by exact name...
REQUIRED_CHECKS = ("gate", "provenance", "dco", "audit-shape")
# ...plus every matrix leg of the cross-platform test job ("test (os, python)").
REQUIRED_CHECK_PREFIXES = ("test (",)

LESSONS_DIR = "lessons/"
# lessons/index.md is the corpus index: it may gain at most one line and must never lose
# one. Anything else (a bulk re-index) goes through a human, see
# docs/maintainer/auto-merge-lessons.md.
INDEX_PATH = "lessons/index.md"
INDEX_MAX_ADDITIONS = 1

# Conclusions that mean "not finished yet" — the workflow will see this PR again.
PENDING_CONCLUSIONS = frozenset(
    {"", "pending", "queued", "in_progress", "requested", "waiting", "expected"}
)
SUCCESS_CONCLUSION = "success"

CHANGES_REQUESTED = "changes_requested"


def _norm(value: Any) -> str:
    """Lower-cased, stripped text for a field that came out of JSON or the GitHub API."""
    return "" if value is None else str(value).strip().lower()


def _required_check_names(checks: Mapping[str, Any]) -> list[str]:
    """The names this PR is required to have green: the fixed four plus every `test (`."""
    fixed = list(REQUIRED_CHECKS)
    matrix = sorted(
        name
        for name in checks
        if isinstance(name, str)
        and name.startswith(REQUIRED_CHECK_PREFIXES)
        and name not in REQUIRED_CHECKS
    )
    return fixed + matrix


def _evaluate_checks(checks: Mapping[str, Any]) -> tuple[str, str]:
    """Every required check green? Returns (merge, "") when yes, else (verdict, reason).

    A conclusion that is not `success` refuses; a required check that is missing or still
    running only waits, because the workflow is re-triggered when it finishes.
    """
    not_successful: list[str] = []
    unfinished: list[str] = []
    for name in _required_check_names(checks):
        if name not in checks:
            unfinished.append(f"{name} (absent)")
            continue
        conclusion = _norm(checks[name])
        if conclusion in PENDING_CONCLUSIONS:
            unfinished.append(f"{name} ({conclusion or 'pending'})")
        elif conclusion != SUCCESS_CONCLUSION:
            not_successful.append(f"{name} ({conclusion})")

    if not_successful:
        return REFUSE, "required check(s) not successful: " + ", ".join(not_successful)
    if unfinished:
        return WAIT, "required check(s) not green yet: " + ", ".join(unfinished)
    return MERGE, ""


def _evaluate_files(
    files: Sequence[str], file_stats: Mapping[str, Any]
) -> tuple[str, str]:
    """Every changed path under lessons/, and lessons/index.md only gains one line."""
    if not files:
        # An empty file list cannot be told apart from a failed fetch, and "every path is
        # under lessons/" is vacuously true for it — never merge on that.
        return WAIT, "no changed files reported — scope could not be verified"

    outside = sorted(path for path in files if not path.startswith(LESSONS_DIR))
    if outside:
        shown = ", ".join(outside[:10])
        more = "" if len(outside) <= 10 else f" (+{len(outside) - 10} more)"
        return REFUSE, f"file(s) outside {LESSONS_DIR}: {shown}{more}"

    if INDEX_PATH in files:
        stats = file_stats.get(INDEX_PATH)
        if stats is None:
            return WAIT, f"{INDEX_PATH} is touched but its line stats are unknown"
        try:
            additions, deletions = int(stats[0]), int(stats[1])
        except (TypeError, ValueError, IndexError, KeyError):
            return WAIT, f"{INDEX_PATH} stats are unreadable: {stats!r}"
        if deletions > 0 or additions > INDEX_MAX_ADDITIONS:
            return (
                REFUSE,
                f"{INDEX_PATH} must be at most a one-line addition: "
                f"+{additions}/-{deletions} (allowed: +{INDEX_MAX_ADDITIONS}/-0)",
            )
    return MERGE, ""


def decide(
    files: list[str],
    checks: dict[str, str | None],
    labels: list[str],
    draft: bool,
    review_state: str,
    body: str = "",
    file_stats: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """Return ``(verdict, reason)`` for one pull request. Pure: no IO, no network.

    ``body`` is accepted so the payload shape is complete and stable; no rule reads it
    today (an opt-out marker in the body would be invisible to the label check the
    workflow also performs, so it would be a trap rather than a feature).
    """
    changed = [str(path) for path in (files or [])]
    check_map = dict(checks or {})
    label_set = {_norm(label) for label in (labels or [])}
    stats = dict(file_stats) if file_stats else {}

    denied = sorted(label for label in label_set if label in DENY_LABELS)
    if denied:
        return REFUSE, "deny-list label(s) present: " + ", ".join(denied)

    if OPT_IN_LABEL not in label_set:
        return (
            WAIT,
            f"label '{OPT_IN_LABEL}' is not present — this channel is opt-in only",
        )

    if draft:
        return REFUSE, "the pull request is still a draft"

    if _norm(review_state) == CHANGES_REQUESTED:
        return REFUSE, "a review requests changes (CHANGES_REQUESTED)"

    verdict, reason = _evaluate_files(changed, stats)
    if verdict != MERGE:
        return verdict, reason

    verdict, reason = _evaluate_checks(check_map)
    if verdict != MERGE:
        return verdict, reason

    return (
        MERGE,
        f"lessons-only diff ({len(changed)} file(s)), all required checks green, "
        f"label '{OPT_IN_LABEL}' present, not a draft, no changes requested",
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point: print ``<verdict>: <reason>`` and exit 0/1/2 (3 = bad payload)."""
    parser = argparse.ArgumentParser(
        prog="lesson_pr_mergeable.py",
        description=(
            "Decide whether a lesson pull request may be squash-merged automatically. "
            "Prints '<verdict>: <reason>'. Exits 0 for merge, 1 for refuse, 2 for wait, "
            "3 when the payload itself is unusable."
        ),
    )
    parser.add_argument(
        "--json",
        dest="payload",
        required=True,
        metavar="JSON",
        help="the decision payload as a JSON object, or '-' to read it from stdin",
    )
    args = parser.parse_args(argv)

    raw = sys.stdin.read() if args.payload == "-" else args.payload
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        print(f"error: --json is not valid JSON: {exc}", file=sys.stderr)
        return EXIT_BAD_PAYLOAD

    if not isinstance(payload, dict):
        print("error: --json must be a JSON object", file=sys.stderr)
        return EXIT_BAD_PAYLOAD

    verdict, reason = decide(
        files=payload.get("files") or [],
        checks=payload.get("checks") or {},
        labels=payload.get("labels") or [],
        draft=bool(payload.get("draft")),
        review_state=payload.get("review_state") or "",
        body=payload.get("body") or "",
        file_stats=payload.get("file_stats") or {},
    )
    print(f"{verdict}: {reason}")
    return EXIT_CODES[verdict]


if __name__ == "__main__":
    sys.exit(main())
