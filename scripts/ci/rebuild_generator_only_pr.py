#!/usr/bin/env python3
"""Decide whether a contributor's conflicting pull request can be rebuilt instead of bounced.

WHY THIS EXISTS (2026-11-23)
----------------------------
Measured over the last 1200 pull requests: **107 external, 24 merged (22%), 80 closed (75%)**. Two of
the three external PRs open at the time of writing were stuck on conflicts that were **entirely in
generator-owned files** — `data/lessons.json`, `docs/data/*`, `docs/.generated-pages.json`,
`docs/_redirects`, `docs/sitemap.xml` — which is the one repair this repository tells maintainers not
to do by hand ("hand-resolving two branches' outputs and then regenerating is how you get a diff that
is neither side's answer").

A contributor cannot fix that themselves: it needs a rebase, seven generators in a fixed order, and a
self-check in a clean clone. `auto-sync-prs.yml` already tries to sync such branches and already fails
on exactly these paths.

So the question this module answers, as a pure function, is narrow:

    are **all** the conflicts in files no human wrote, and is there at least one hand-written file to
    carry over?

If yes, the rebuild is mechanical: take `main`, replay the contributor's hand-written files, run the
generators, push. If a single conflict is in a hand-written path, the answer is "leave it" — a human
wrote that line and a bot must not choose between two versions of it.

The decision is the part that failed repeatedly in the automation (a rule that closed ten strangers on
2026-11-22 came from deciding on the wrong attribute), so it lives here, offline and testable, and the
CLI defaults to a dry run.

Usage::

    python3 scripts/ci/rebuild_generator_only_pr.py --pr 5341            # say what would happen
    python3 scripts/ci/rebuild_generator_only_pr.py --pr 5341 --conflicts -  # plan from stdin

Exit codes: 0 = a rebuild is possible (plan printed), 1 = leave it to a human (reason printed),
2 = could not determine (network/git failure) — which is not the same answer as "safe to rebuild".
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.ci.check_dist_diff import is_published  # noqa: E402  — the one authority on "generator owns this"

def is_hand_written(path: str) -> bool:
    """Whether a human is expected to have typed this line.

    One authority, by negation: a path is hand-written **unless** `check_dist_diff` says a generator
    owns it. Deliberately conservative — an unknown path therefore blocks a rebuild instead of being
    silently discarded by one, and a second list of "generated paths" cannot drift from the first.
    """
    return not is_published(str(path))


def plan(conflicted: list[str], changed: list[str]) -> dict:
    """`{"action": "rebuild" | "leave", "reason": ..., "keep": [...]}` for one pull request.

    `conflicted` is the set of paths git reports as conflicting with the base; `changed` is every
    path the pull request touches. Both are repo-relative POSIX paths.
    """
    conflicted = [str(p) for p in (conflicted or [])]
    changed = [str(p) for p in (changed or [])]

    if not conflicted:
        return {"action": "leave", "reason": "no conflict with the base — nothing to rebuild",
                "keep": []}

    hand = sorted(p for p in conflicted if is_hand_written(p))
    if hand:
        return {
            "action": "leave",
            "reason": ("a human wrote the conflicting line(s): "
                       + ", ".join(hand[:3]) + (f" (+{len(hand) - 3})" if len(hand) > 3 else "")),
            "keep": [],
        }

    keep = sorted(p for p in changed if is_hand_written(p))
    if not keep:
        return {"action": "leave",
                "reason": "the pull request changes nothing hand-written — there is nothing to carry",
                "keep": []}

    regenerated = sorted({p for p in changed if not is_hand_written(p)})
    return {
        "action": "rebuild",
        "reason": (f"every conflict is in a generator-owned file ({len(conflicted)}), and "
                   f"{len(keep)} hand-written path(s) can be replayed onto main"),
        "keep": keep,
        "regenerate": regenerated,
    }


def conflicts_from_merge_tree(base: str, head: str) -> tuple[list[str], str]:
    """Paths git reports as conflicting between `base` and `head`, or a reason it could not tell."""
    result = subprocess.run(
        ["git", "merge-tree", "--write-tree", "--name-only", "--no-messages", base, head],
        cwd=REPO, capture_output=True, text=True, check=False)
    if result.returncode not in (0, 1):
        return [], (result.stderr or "git merge-tree failed").strip().splitlines()[0][:200]
    # With --write-tree, output line 1 is the tree id (or a conflict marker), then the conflicted names.
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    paths = [line.strip() for line in lines[1:] if not line.startswith(("*", "+", "-"))]
    return (paths, "") if result.returncode == 1 else ([], "")


#: Hosts that inject an environment `GITHUB_TOKEN` which is *not* the credential the keyring has.
#: Measured 2026-11-23: every `gh` call from a subprocess here returned HTTP 401 until the variable was
#: dropped, while the same command in the shell worked — the shell is not the only place it is set.
_ENV = {key: value for key, value in os.environ.items() if key != "GITHUB_TOKEN"}


def _fetch_pull_request_ref(number: int) -> str:
    """Make `origin/pr-<n>` exist, so a fork PR's head can be compared with the base."""
    ref = f"refs/remotes/origin/pr-{number}"
    subprocess.run(["git", "fetch", "--quiet", "origin", f"pull/{number}/head:{ref}"],
                   cwd=REPO, capture_output=True, text=True, check=False, env=_ENV)
    return f"origin/pr-{number}"


def pr_facts(number: int) -> tuple[dict | None, str]:
    """`{files, headRefName, baseRefName, maintainerCanModify}` for one pull request, or a reason."""
    result = subprocess.run(
        ["gh", "pr", "view", str(number), "--json",
         "files,headRefName,baseRefName,maintainerCanModify,mergeable"],
        cwd=REPO, capture_output=True, text=True, check=False, env=_ENV)
    if result.returncode != 0:
        return None, (result.stderr or "gh pr view failed").strip().splitlines()[0][:200]
    try:
        return json.loads(result.stdout or "{}"), ""
    except ValueError as error:
        return None, f"unreadable gh output: {error}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pr", type=int, help="pull request number to inspect")
    parser.add_argument("--conflicts", help="'-' to read the conflicted paths from stdin, one per line")
    parser.add_argument("--changed-file", type=Path,
                        help="a file listing every path the pull request touches; defaults to the "
                             "conflicted set (which is all a caller usually needs)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    changed: list[str] = []
    conflicted: list[str] = []
    if args.conflicts == "-":
        conflicted = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
        changed = conflicted
        if args.changed_file:
            changed = [line.strip() for line in
                       args.changed_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    elif args.pr:
        facts, error = pr_facts(args.pr)
        if facts is None:
            print(f"::error::{error}", file=sys.stderr)
            return 2
        changed = [str(entry.get("path", "")) for entry in facts.get("files") or []]
        mergeable = str(facts.get("mergeable") or "").upper()
        if mergeable == "MERGEABLE":
            result = {"action": "leave", "reason": "GitHub does not report a conflict",
                      "keep": [], "changed": len(changed)}
            print(json.dumps(result, ensure_ascii=False, indent=1) if args.json
                  else f"leave: {result['reason']}")
            return 1
        if mergeable != "CONFLICTING":
            # `UNKNOWN` is GitHub saying "not computed yet", which is not "no conflict". Measured
            # 2026-11-23 on #5341/#5345: the first `gh pr view` after a push answers UNKNOWN, so
            # treating anything-but-CONFLICTING as "fine" reads a conflict as a clean merge.
            print(f"::error::GitHub has not computed mergeability yet ({mergeable or 'empty'}) — "
                  f"re-run in a minute; this is not the same answer as \"no conflict\"",
                  file=sys.stderr)
            return 2
        head_ref = _fetch_pull_request_ref(args.pr)
        conflicted, error = conflicts_from_merge_tree(f"origin/{facts.get('baseRefName', 'main')}",
                                                      head_ref)
        if error:
            print(f"::error::{error}", file=sys.stderr)
            return 2
    else:
        parser.error("either --pr or --conflicts - is required")

    result = plan(conflicted, changed)
    result["conflicted"] = len(conflicted)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print(f"{result['action']}: {result['reason']}")
        for path in result.get("keep") or []:
            print(f"  keep  {path}")
    return 0 if result["action"] == "rebuild" else 1


if __name__ == "__main__":
    raise SystemExit(main())
