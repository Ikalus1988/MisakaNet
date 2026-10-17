#!/usr/bin/env python3
"""Arm the lesson auto-merge channel for a lesson PR this repository can vouch for.

Why this exists, and why it is a separate script from the channel itself
-----------------------------------------------------------------------
`docs/maintainer/auto-merge-lessons.md` documents a channel that is **opt-in by label**:
`auto-merge-lessons.yml` evaluates a lesson PR carrying `auto-merge-lesson` and squash-merges
it once every mechanical condition holds. Nothing applied the label, so six open lesson PRs
sat at `auto-merge-lessons = skipping` while the owner merged them by hand — the repository
was producing findings faster than it consumed them.

The label cannot be applied at PR-creation time, and that is the fact this script is built on.
`auto-merge-lessons.yml` fires on `labeled`, `synchronize` and `ready_for_review` — deliberately
**not** on `opened`, and the `check_suite` fallback was removed on 2026-10-02 as a fan-out (30
runs in 20 minutes on a commit nobody pushed to). Its own documentation states the consequence:
a PR armed *before* its checks finish waits forever, because nothing re-triggers the channel
when they later go green:

    一个已 opt-in 的 PR 如果在 `synchronize` / `ready_for_review` / `labeled` 之后检查才全绿，
    **不会**自动合并，需要人手动合一次。

So arming must happen **after** the mechanical conditions already hold — and the only event
left that can carry "now they hold" is a clock. That is what this script is: the step a
scheduled sweep runs. It applies the label exactly when the channel's own judge
(`scripts/lesson_pr_mergeable.py` — the single source of truth, imported rather than copied)
says the PR would merge the instant it carried the label. The label is therefore not a
formality filled in by a bot: it is applied at the one moment it is both true and effective.

Who is swept, and who is not
---------------------------
Only PRs whose **head branch lives in this repository** and whose author has write access
(`OWNER` / `MEMBER` / `COLLABORATOR`). A branch in this repository cannot be created without
write access, so this is exactly the set of authors who could have pushed or merged directly —
the trust boundary is unchanged by arming them, while an **external** contributor's fork PR
stays opt-in by hand, which the owner stated as a constraint. Everything else (`wip`,
`do-not-merge`, a draft, a review that requests changes, a file outside `lessons/`) is left
alone by the shared judge, not by a second copy of the rules here.

The token matters and cannot be checked from here
-------------------------------------------------
The label must be applied by a **PAT** (`secrets.SHELDON_PAT`), never `GITHUB_TOKEN`: GitHub
suppresses workflow runs for events caused by the built-in token, so a `GITHUB_TOKEN`-applied
label starts no `pull_request: labeled` run and the channel never wakes. The same trap already
cost this repository three times on the push path (`.github/workflows/land_change.py` documents
it); it is repeated here because the failure is a label that appears correct and does nothing.

Usage
-----
    python3 scripts/arm_auto_merge_lesson_prs.py                 # plan only (default)
    python3 scripts/arm_auto_merge_lesson_prs.py --apply         # apply the label
    python3 scripts/arm_auto_merge_lesson_prs.py --json          # the plan as JSON

Environment: GH_TOKEN / GITHUB_TOKEN with `pull-requests: write` (and a PAT, see above).
Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lesson_pr_mergeable import MERGE, OPT_IN_LABEL, decide  # noqa: E402

REPO_DEFAULT = os.environ.get("GITHUB_REPOSITORY", "Ikalus1988/MisakaNet")
API = "https://api.github.com"

#: Author associations that may push a branch into this repository. A fork PR's author is never
#: one of these, which is what keeps "external contributors stay opt-in by hand" true.
TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})

#: The set of labels that makes a PR a legitimate candidate for arming. Nothing else.
LABEL = OPT_IN_LABEL


def _token() -> str:
    return (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()


def _redact(text: str) -> str:
    """Nothing this script prints may carry the token.

    `gh` echoes its arguments in some failures, and the env read above lives in this module, so a
    static analyser cannot tell a PR number from a credential. Every message that reaches stdout or an
    exception goes through here first — the redaction is real, not a suppression of the finding.
    """
    token = _token()
    if token and isinstance(text, str):
        return text.replace(token, "<REDACTED>")
    return text


def gh_api(path: str, paginate: bool = False, jq: str | None = None):
    """One `gh api` call. Raises RuntimeError with gh's stderr on failure."""
    argv = ["gh", "api", path]
    if paginate:
        argv.append("--paginate")
    if jq:
        argv += ["--jq", jq]
    done = subprocess.run(argv, capture_output=True, text=True, timeout=180)
    if done.returncode != 0:
        raise RuntimeError(_redact(f"gh api {path}: {done.stderr.strip()[:300]}"))
    return done.stdout


def candidate_skip_reason(pr: dict, repo: str = REPO_DEFAULT) -> str | None:
    """Why this PR must be left alone, or None when it may be considered.

    Reads only the PR object: the head repository (fork or not), the author association, the
    draft flag and the base branch. The mechanical conditions themselves are the judge's job —
    duplicating them here is how two answers to "may this merge" start to disagree.
    """
    head = pr.get("head") or {}
    head_repo = ((head.get("repo") or {}).get("full_name") or "")
    if head_repo != repo:
        return (f"head branch lives in {head_repo or 'a deleted fork'} — external contributors' "
                f"pull requests stay opt-in by hand")
    association = str(pr.get("author_association") or "").upper()
    if association not in TRUSTED_ASSOCIATIONS:
        return (f"author association {association or 'UNKNOWN'} is not one of "
                f"{'/'.join(sorted(TRUSTED_ASSOCIATIONS))} — opt-in by hand")
    base = (pr.get("base") or {}).get("ref") or ""
    if base != "main":
        return f"base branch is {base or 'unknown'}, not main"
    if pr.get("draft"):
        return "the pull request is a draft"
    return None


def build_payload(pr: dict, files: list[dict], check_runs: list[dict],
                  reviews: list[dict], *, assume_label: bool = True) -> dict:
    """Assemble the payload `scripts/lesson_pr_mergeable.py` decides on.

    The assembly is a **copy of what the channel itself does** (`.github/workflows/
    auto-merge-lessons.yml`, "fetch the facts"): latest conclusion per check name by
    `started_at`, latest review per author by `submitted_at` counting only
    APPROVED/CHANGES_REQUESTED. Two different readings of the same API would make this sweep
    arm a PR the channel then refuses — a label that promises a merge that never comes.
    """
    checks: dict[str, str | None] = {}
    for run in sorted(check_runs, key=lambda r: str(r.get("started_at") or "")):
        name = run.get("name")
        if name:
            checks[str(name)] = run.get("conclusion")

    latest: dict[str, str] = {}
    for review in sorted(reviews, key=lambda r: str(r.get("submitted_at") or "")):
        if review.get("state") in ("APPROVED", "CHANGES_REQUESTED"):
            login = ((review.get("user") or {}).get("login") or "")
            latest[login] = review["state"]
    if any(state == "CHANGES_REQUESTED" for state in latest.values()):
        review_state = "CHANGES_REQUESTED"
    elif latest:
        review_state = "APPROVED"
    else:
        review_state = "NONE"

    labels = [l["name"] for l in (pr.get("labels") or [])]
    if assume_label and LABEL not in labels:
        # The question this sweep asks is "would the channel merge it the moment it were
        # labelled?", so the label is simulated as present. If the conditions do *not* all
        # hold, the judge returns wait/refuse and no label is applied — that is the guard.
        labels = labels + [LABEL]

    return {
        "files": [f.get("filename") for f in files],
        "file_stats": {f.get("filename"): [f.get("additions", 0), f.get("deletions", 0)]
                       for f in files},
        "checks": checks,
        "labels": labels,
        "draft": bool(pr.get("draft")),
        "review_state": review_state,
        "body": pr.get("body") or "",
    }


def arming_decision(pr: dict, files: list[dict], check_runs: list[dict],
                    reviews: list[dict]) -> tuple[bool, str]:
    """``(arm_it, reason)`` for one candidate PR, using the channel's own judge.

    A PR that already carries the label is **not** re-armed: adding a label that is already
    there raises no `labeled` event, so re-arming would be a no-op that reads like an action.
    """
    existing = {l["name"].strip().lower() for l in (pr.get("labels") or [])}
    if LABEL.lower() in existing:
        return False, f"already carries '{LABEL}'"

    payload = build_payload(pr, files, check_runs, reviews)
    verdict, reason = decide(
        files=payload["files"],
        checks=payload["checks"],
        labels=payload["labels"],
        draft=payload["draft"],
        review_state=payload["review_state"],
        body=payload["body"],
        file_stats=payload["file_stats"],
    )
    if verdict == MERGE:
        return True, f"the channel would merge it now: {reason}"
    return False, f"not armed — the channel says {verdict}: {reason}"


# ── the sweep (IO) ──────────────────────────────────────────────────────────
def fetch_candidates(repo: str) -> list[dict]:
    """Every open PR against `main`. `--jq '.[]'` emits one compact object per line, so pages
    concatenate (the same reading `auto-merge-lessons.yml` uses)."""
    raw = gh_api(f"repos/{repo}/pulls?state=open&base=main&per_page=100",
                 paginate=True, jq=".[]")
    return _ndjson(raw)


def fetch_facts(repo: str, pr: dict) -> tuple[list[dict], list[dict], list[dict]]:
    number = pr["number"]
    sha = ((pr.get("head") or {}).get("sha")) or ""
    files = _ndjson(gh_api(f"repos/{repo}/pulls/{number}/files?per_page=100",
                           paginate=True, jq=".[]"))
    check_runs = _ndjson(gh_api(f"repos/{repo}/commits/{sha}/check-runs?per_page=100",
                                paginate=True, jq=".check_runs[]"))
    reviews = _ndjson(gh_api(f"repos/{repo}/pulls/{number}/reviews?per_page=100",
                             paginate=True, jq=".[]"))
    return files, check_runs, reviews


def _ndjson(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def apply_label(repo: str, number: int) -> None:
    """Add the opt-in label. Raises RuntimeError so a failed write is never reported as a plan."""
    done = subprocess.run(
        ["gh", "pr", "edit", str(number), "--repo", repo, "--add-label", LABEL],
        capture_output=True, text=True, timeout=120,
    )
    if done.returncode != 0:
        raise RuntimeError(f"gh pr edit #{number} --add-label {LABEL}: {done.stderr.strip()[:300]}")


def plan(repo: str, limit: int = 0) -> list[dict]:
    """One entry per open candidate PR: {number, arm, reason}."""
    out: list[dict] = []
    for pr in fetch_candidates(repo):
        if limit and len(out) >= limit:
            break
        reason = candidate_skip_reason(pr, repo)
        number = pr.get("number")
        if reason:
            out.append({"number": number, "arm": False, "reason": reason, "skipped": True})
            continue
        try:
            files, check_runs, reviews = fetch_facts(repo, pr)
        except RuntimeError as exc:
            out.append({"number": number, "arm": False, "skipped": True,
                        "reason": f"could not read the facts: {exc}"})
            continue
        arm, why = arming_decision(pr, files, check_runs, reviews)
        out.append({"number": number, "arm": arm, "reason": why, "skipped": False})
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=REPO_DEFAULT,
                        help="owner/name (default: $GITHUB_REPOSITORY)")
    parser.add_argument("--apply", action="store_true",
                        help="actually add the label (default: print the plan)")
    parser.add_argument("--json", action="store_true", help="print the plan as JSON")
    parser.add_argument("--limit", type=int, default=0, help="only the first N candidates")
    args = parser.parse_args(argv)

    try:
        plan_data = plan(args.repo, args.limit)
    except RuntimeError as exc:
        print(f"::warning::the sweep could not list pull requests: {exc}")
        return 1

    if args.json:
        print(json.dumps(plan_data, indent=2, ensure_ascii=False))
    else:
        for entry in plan_data:
            # The reason is a sentence this script built from PR facts; `_redact` proves the token
            # cannot be in it, and the suppression records that the analyser's taint is the env read.
            if entry.get("skipped"):
                # codeql[py/clear-text-logging-sensitive-data]
                print(f"  #{entry['number']}: left alone — {_redact(str(entry['reason']))}")
            elif entry["arm"]:
                # codeql[py/clear-text-logging-sensitive-data]
                print(f"  #{entry['number']}: ARM — {_redact(str(entry['reason']))}")
            else:
                # codeql[py/clear-text-logging-sensitive-data]
                print(f"  #{entry['number']}: not yet — {_redact(str(entry['reason']))}")

    to_arm = [e for e in plan_data if e.get("arm")]
    if not to_arm:
        print("nothing to arm (no candidate satisfies the channel's own conditions right now)")
        return 0
    if not args.apply:
        print(f"dry run — {len(to_arm)} pull request(s) would be armed. Pass --apply to label them.")
        return 0

    failures = 0
    for entry in to_arm:
        try:
            apply_label(args.repo, entry["number"])
        except RuntimeError as exc:
            failures += 1
            print(f"::error::could not arm #{entry['number']}: {exc}")
            continue
        print(f"  armed #{entry['number']} with '{LABEL}'")
    if failures:
        # A sweep that only acts when there is something to act on must not exit 0 on the runs
        # where the action failed: that is how a silently broken automation looks healthy.
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
