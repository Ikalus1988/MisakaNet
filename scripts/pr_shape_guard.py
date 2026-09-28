#!/usr/bin/env python3
"""Mechanical shape predicates for pull requests (issue #2066, evidence from 2026-09-26/27).

Why a separate, pure module. The 2026-09-22 session in #2066 spent eight hand-written reviews on one
automation account's output, three of them for PRs that were *the same template with a different issue
title inlined*. On 2026-09-26/27 four more arrived (one root-level `ai_solution.py` holding prose, one
`solutions/issue_2283_solution.ts` holding a Markdown essay, a destructive `pyproject.toml` rewrite),
and each cost a human reply. A predicate that decides "this is a template dump, not an answer" is
cheap, checkable, and does not need judgement — so it belongs in code, not in a review queue.

Deliberately **pure**: every function takes data (file names, file texts, issue bodies) and returns
findings. No network, no git, no globals — because the caller is a `pull_request_target` workflow that
must never check out the PR's code (`.github/workflows/pr-shape-guard.yml` checks out the *base* and
passes this module the PR's file *names*, which are data, not code).

Nothing here closes a pull request. It reports; a human decides.

Usage (the workflow does exactly this):

    gh api --paginate repos/{owner}/{repo}/pulls/N/files --jq '.[].filename' > /tmp/changed.txt
    gh api repos/{owner}/{repo}/pulls/N --jq '.body // ""' > /tmp/pr-body.txt
    python3 scripts/pr_shape_guard.py --changed-files /tmp/changed.txt --pr-body /tmp/pr-body.txt \\
        --base-pyproject /tmp/base-pyproject.toml --head-pyproject /tmp/head-pyproject.toml \\
        --issue-bodies /tmp/issue-bodies.json

Prints a JSON array of markdown findings (empty = clean) and exits 0 either way: the workflow decides
what to do with them, so a bug in here cannot block a legitimate contributor by accident.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ── rule 1: a root-level "solution" dump ──────────────────────────────────────────────────────────
#
# Measured shapes: `ai_solution.py` (three PRs, one of them answering a *different* issue than the one
# it claimed), `solutions/issue_2283_solution.ts` (a new top-level directory), and #2061-#2063's
# `solution.py` + `test_solution.py` (the same blob in all three). None of them is the artifact any
# task in this repository names: the deliverable is a lesson under `lessons/`, or code under `scripts/`
# or `workers/` that the issue asked for.
ROOT_SOLUTION = re.compile(r"^(?:ai_|auto_)?solution[\w.-]*\.(?:py|ts|js|md)$", re.IGNORECASE)
ROOT_SOLUTION_TEST = re.compile(r"^test_solution[\w.-]*\.py$", re.IGNORECASE)
SOLUTION_DIR = re.compile(r"^solutions?/")


def root_solution_dump(paths) -> list[str]:
    """Root-level `solution*` files and `solutions/` directories, with what to do instead."""
    hits = [p for p in paths
            if "/" not in p and (ROOT_SOLUTION.match(p) or ROOT_SOLUTION_TEST.match(p))
            or SOLUTION_DIR.match(p)]
    if not hits:
        return []
    return [
        "**Deliverable is not a `solution` file.** This PR adds "
        + ", ".join(f"`{h}`" for h in sorted(set(hits))[:4])
        + ". The task's own *Deliverable* section names the artifact — for a question bounty that is a "
        "lesson under `lessons/` (`## Problem` / `## Root Cause` / `## Solution` / `## Verification`, "
        "frontmatter, `python3 scripts/lesson_gate.py <file>` clean); for a code bounty it is the "
        "script or worker the issue names. A root-level dump is invisible to the corpus and to every "
        "gate, so it cannot satisfy an acceptance criterion even when its content is right."
    ]


# ── rule 2: packaging damage ──────────────────────────────────────────────────────────────────────
#
# #2061-#2063 replaced `pyproject.toml` with two lines, dropping `[build-system]` and the whole
# `[project]` table (distribution name, the release-please-maintained version, dependencies,
# `[project.scripts]`). Six wheel jobs and nine test jobs went red on each, which is how the shape was
# finally noticed — the reviews had already been written by then.
PACKAGING_TABLES = ("[build-system]", "[project]")


def packaging_damage(base_text: str | None, head_text: str | None) -> list[str]:
    """Tables that `pyproject.toml` had and no longer has."""
    if base_text is None or head_text is None:
        return []
    missing = [t for t in PACKAGING_TABLES if t in base_text and t not in head_text]
    if not missing:
        return []
    return [
        "**`pyproject.toml` lost " + " and ".join(f"`{t}`" for t in missing) + ".** "
        "The distribution name, the release-please-maintained version, the dependencies and "
        "`[project.scripts]` all live in that table; removing it breaks the wheel build and every test "
        "job (that is how #2061-#2063 were noticed, after their reviews had been written). If the "
        "change does not need to touch packaging, revert the file."
    ]


# ── rule 3: a question bounty with no lesson ──────────────────────────────────────────────────────
#
# `scripts/question_autopilot.py` opens these tasks with a body that carries
# `<!-- misakanet-question-bounty:anchor-N -->` and a one-sentence *Deliverable*: a lesson under
# `lessons/`. Measured 2026-09-26: four PRs claimed one (two of them the same task) and none added a
# lesson — one patched `scripts/check_provenance.py`, one added a `.ts` essay, two were drafts. The CI
# lesson gate reported **success** on all of them, because it only runs on `lessons/**/*.md` changes.
QUESTION_BOUNTY_MARKER = "misakanet-question-bounty"
LESSON_FILE = re.compile(r"^lessons/(?:core|contrib|en)/.+\.md$")


# `Closes/Fixes/Resolves #N` — a *claim*, not a mention. The distinction is not pedantry: measured on
# the release PR (#2311, 2026-09-27), a body that merely *lists* merged pull requests by number
# (`… (#2332)`) matched a bare-number rule, and one of those PRs discusses this very marker — so a
# release was reported as "claims a question bounty without a lesson". A rule that fires on the release
# train is a rule that gets switched off.
# The noun in between is real: the titles on 2026-09-26 read "fix: solve issue #2283 - [Bounty] …".
# Up to three filler words are allowed between the verb and the number ("solve issue #2283"), because
# that is how the titles on 2026-09-26 read. A colon stops it: `fix: bump (#2332)` — a commit-list line in
# a release body — must never be read as a claim.
CLAIMS_ISSUE = re.compile(
    r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|solve[sd]?|address(?:es|ed)?)\b"
    r"(?:\s+\w+){0,3}?\s+#(\d{1,6})"
)


def linked_issues(pr_text: str) -> list[int]:
    """Issue numbers the PR **claims** to resolve (`Closes`/`Fixes`/`Resolves #N`).

    A bare `#N` is deliberately not enough — see :data:`CLAIMS_ISSUE`. `mentions_issues()` returns those,
    for callers that want to look something up.
    """
    return sorted({int(n) for n in CLAIMS_ISSUE.findall(pr_text or "")})


def mentions_issues(pr_text: str) -> list[int]:
    """Every `#N` in the text, claimed or not (used to fetch issue bodies, never to decide)."""
    return sorted({int(n) for n in re.findall(r"#(\d{1,6})", pr_text or "")})


def question_bounty_without_a_lesson(paths, issue_bodies: dict, pr_text: str = "") -> list[str]:
    """A PR that claims a question bounty while changing no lesson file."""
    bounty_issues = {
        int(number) for number, body in (issue_bodies or {}).items()
        # The caller hands us the bodies of the issues this PR *mentions*; a PR's own body can quote the
        # marker while explaining it, so only a claimed number that carries the marker counts.
        if QUESTION_BOUNTY_MARKER in (body or "")
    }
    claimed = [n for n in linked_issues(pr_text) if n in bounty_issues]
    if not claimed:
        return []
    if any(LESSON_FILE.match(p) for p in paths):
        return []
    return [
        "**This claims a question bounty (#"
        + ", #".join(str(n) for n in claimed[:4])
        + ") but changes no file under `lessons/core`, `lessons/contrib` or `lessons/en`.** "
        "Those tasks are answered by writing a lesson — *Answering means being found*: "
        "`misakanet_search` has to return it for the question text that produced the bounty. A script, "
        "a document, or a file outside `lessons/` is not indexed at all (`INDEXED_DIRS` in "
        "`scripts/update_lessons_json.py`), so the questions still answer `no_match`."
    ]


def findings(*, paths, pr_text: str = "", base_pyproject: str | None = None,
             head_pyproject: str | None = None, issue_bodies: dict | None = None) -> list[str]:
    """Every finding for one pull request, in the order a reviewer should read them."""
    out: list[str] = []
    out += root_solution_dump(paths)
    out += packaging_damage(base_pyproject, head_pyproject)
    out += question_bounty_without_a_lesson(paths, issue_bodies or {}, pr_text)
    return out


def _read(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mechanical shape predicates for a pull request.")
    parser.add_argument("--changed-files", required=True,
                        help="one changed path per line (API order, not the diff)")
    parser.add_argument("--pr-body", help="file holding the PR title+body text")
    parser.add_argument("--base-pyproject", help="file holding the base branch's pyproject.toml")
    parser.add_argument("--head-pyproject", help="file holding the PR's pyproject.toml")
    parser.add_argument("--issue-bodies", help="JSON file: {\"<issue number>\": \"<body>\"}")
    args = parser.parse_args(argv)

    paths = [line.strip() for line in (_read(args.changed_files) or "").splitlines() if line.strip()]
    bodies: dict = {}
    if args.issue_bodies:
        try:
            bodies = json.loads(_read(args.issue_bodies) or "{}")
        except json.JSONDecodeError:
            bodies = {}
    result = findings(paths=paths, pr_text=_read(args.pr_body) or "",
                      base_pyproject=_read(args.base_pyproject),
                      head_pyproject=_read(args.head_pyproject), issue_bodies=bodies)
    # stdout is the interface: the workflow reads it as JSON.
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
