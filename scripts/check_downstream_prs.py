#!/usr/bin/env python3
"""Before merging (or deleting) a branch, ask which open PRs are based on it.

Why this exists
---------------
Merging an upstream branch of a stacked PR closes the downstream PRs (their base
disappears), and so does deleting the branch after a normal merge. It is silent:
the downstream PRs go from "open" to "closed" with no failure anywhere, and the
author finds out later. The lesson is in the corpus
(`lessons/contrib/a-stacked-pr-downstream-is-closed-when-the-upstream-branch-is-deleted.md`);
this script is the same rule as a check, because a doc note is skipped exactly
when the branch looks mergeable.

Usage:
    python3 scripts/check_downstream_prs.py <branch>
    python3 scripts/check_downstream_prs.py <branch> --repo owner/name

Exit codes:
    0  no open PR is based on <branch>
    1  at least one is — merge the stack bottom-up, or retarget them first
    2  could not check (gh missing, unauthenticated, or an unreadable response);
       do **not** read this as "none"
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys


def downstream_prs(branch: str, repo: str | None = None, gh: str = "gh") -> list[dict]:
    """Open PRs whose base is `branch`, as `[{"number", "title", "headRefName"}]`.

    Raises RuntimeError when the question cannot be answered — a failed `gh` is a
    "could not check", not an empty list (the whole point is that "none" must be
    an observation).
    """
    argv = [gh, "pr", "list", "--state", "open", "--base", branch,
            "--json", "number,title,headRefName"]
    if repo:
        argv += ["--repo", repo]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True)
    except OSError as exc:
        raise RuntimeError(f"could not run {gh!r}: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"{gh} pr list exited {proc.returncode}: {detail or 'no output'}")
    try:
        rows = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gh returned unreadable JSON: {exc}") from exc
    if not isinstance(rows, list):
        raise RuntimeError(f"gh returned {type(rows).__name__}, expected a list")
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("branch", help="the branch you are about to merge or delete")
    ap.add_argument("--repo", help="owner/name; default: the checkout's remote")
    ap.add_argument("--gh", default="gh", help="gh executable (default: gh)")
    args = ap.parse_args(argv)

    try:
        rows = downstream_prs(args.branch, repo=args.repo, gh=args.gh)
    except RuntimeError as exc:
        print(f"COULD NOT CHECK: {exc}", file=sys.stderr)
        print("Do not read this as 'no downstream PRs'.", file=sys.stderr)
        return 2

    if not rows:
        print(f"no open PR is based on {args.branch!r}")
        return 0

    print(f"{len(rows)} open PR(s) are based on {args.branch!r}:")
    for row in rows:
        print(f"  DOWNSTREAM #{row.get('number')} {row.get('headRefName', '?')} — {row.get('title', '')}")
    print("Merging or deleting that branch will close them. Merge the stack bottom-up, or retarget them.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
