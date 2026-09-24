#!/usr/bin/env python3
"""A red site build must not be invisible (#2136).

`Workers Builds: misakanet-web` is Cloudflare's Git integration deploying `docs/` to misakanet.org. It
is **not** one of the three checks the ruleset requires (`DCO / Signed-off-by`, `test (ubuntu-latest,
3.11)`, `gate`), and its check-run carries no summary, no annotation and no log beyond a dashboard
link — so it can be red on every commit for a day while merges keep landing and the site keeps not
updating. That is not hypothetical: measured 2026-09-24, the live site was still byte-identical to
`7fcebbf2a` (2026-09-23T17:29Z) while ~25 commits had landed on top of it, and the only place the
failure was visible at all was a red check-run nobody was required to look at.

There are two ways to fix that, and they cost very different things:

* **make the check required** — every merge is blocked until the site build is green, including the
  merge that *fixes* the build. That trades a silent failure for a stuck repository.
* **make it loud** — one issue, in the place a maintainer actually looks. No merge is ever blocked.

This is the second one. The state machine is deliberately small, because a watcher that comments on
every push is just a different kind of noise:

| tracker issue | current state | action |
|---|---|---|
| absent | red | **open** the tracking issue |
| last comment `red` | red | nothing (repeated failures are not 25 comments) |
| last comment `red` | green | comment "back to green" |
| last comment `green` | red | comment "red again" |
| last comment `green` | green | nothing |
| absent | green, or unknown | nothing |

**Transitions only** — the same reason a good alert fires on state change rather than on every sample.

The tracking issue is *whichever open issue carries the `site-build-red` label*. That is the whole
contract with the maintainer: label an existing issue and the watcher comments there instead of opening
a duplicate (as #2136 was), and unlabel or close it and the next red build opens a fresh one. The
watcher never closes an issue itself — a green build is evidence, and whether that closes the issue is
the maintainer's call, not a script's.

Usage::

    python3 scripts/workers_builds_watch.py --event "$GITHUB_EVENT_PATH"   # from check_suite
    python3 scripts/workers_builds_watch.py --branch main                  # scheduled safety net
    python3 scripts/workers_builds_watch.py --dry-run ...                  # print, write nothing

Env: `GH_TOKEN` (or `GITHUB_TOKEN`), `GH_REPO` (default `Ikalus1988/MisakaNet`), `GH_API_BASE`
(overridden by the tests, which run this file against a stub GitHub).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_REPO = "Ikalus1988/MisakaNet"
LABEL = "site-build-red"
LABEL_COLOR = "b60205"
# GitHub rejects a label description longer than 100 characters, and the first version of this string
# was 157: creating the label answered `422 Validation Failed … description is too long`. Measured
# 2026-09-24. The `[:100]` at the call site is a belt on top of a short string, not a substitute for
# one — a silently truncated sentence is a worse label than a short one.
LABEL_DESCRIPTION = "Tracking issue for the Cloudflare Workers Builds site deploy (scripts/workers_builds_watch.py)"
CHECK_PREFIX = "Workers Builds"

# The transition is recorded in a comment rather than in a file, so the state lives where the reader
# is looking instead of in a snapshot nobody opens.
MARKER = "workers-builds-watch"
TITLE = "bug(infra): the site build (Workers Builds) is red — the site is not deploying"

RED, GREEN, UNKNOWN = "red", "green", "unknown"


def token() -> str:
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    sys.exit("no GitHub token: set GH_TOKEN (or GITHUB_TOKEN)")


class GitHub:
    def __init__(self, repo: str, token_value: str, base: str) -> None:
        self.repo = repo
        self.token = token_value
        self.base = base.rstrip("/")

    def __call__(self, method: str, path: str, body: dict | None = None):
        url = path if path.startswith("http") else f"{self.base}/repos/{self.repo}{path}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "misakanet-site-build-watch",
        })
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:400]
            raise RuntimeError(f"GitHub API {method} {path} -> HTTP {error.code}\n{detail}") from None


# ── the two facts the decision needs ────────────────────────────────────────────────────────────────

def site_build_state(gh: GitHub, sha: str) -> tuple[str, str]:
    """(state, evidence) for one commit's Workers Builds checks.

    `red` wins over `green` when both are present: a commit can carry more than one Workers Builds
    run (a preview trigger and the production one), and reporting the healthy half of a split pair is
    the exact mistake this watcher exists to prevent. Anything unfinished is `unknown`, which is not
    a state to act on — a queued build is not a failure.
    """
    runs = gh("GET", f"/commits/{sha}/check-runs?per_page=100") or {}
    builds = [r for r in (runs.get("check_runs") or [])
              if str(r.get("name") or "").startswith(CHECK_PREFIX)]
    if not builds:
        return UNKNOWN, "no Workers Builds check-run on this commit"
    finished = [r for r in builds if r.get("status") == "completed"]
    if not finished:
        return UNKNOWN, f"{len(builds)} Workers Builds check-run(s), none completed yet"
    failing = [r for r in finished if r.get("conclusion") == "failure"]
    if failing:
        run = failing[0]
        return RED, (f"{len(failing)}/{len(finished)} failed — "
                     f"[build {run.get('external_id')}]({run.get('details_url')})")
    if all(r.get("conclusion") == "success" for r in finished):
        run = finished[0]
        return GREEN, f"all {len(finished)} succeeded — [build {run.get('external_id')}]({run.get('details_url')})"
    conclusions = ", ".join(sorted({str(r.get("conclusion")) for r in finished}))
    return UNKNOWN, f"inconclusive ({conclusions})"


def open_tracker(gh: GitHub) -> dict | None:
    """The open issue carrying the label, or None. Newest first, so a re-labeled duplicate loses."""
    issues = gh("GET", f"/issues?labels={LABEL}&state=open&sort=created&direction=desc&per_page=10") or []
    # `GET /issues` returns pull requests too; a PR is not a tracker issue.
    issues = [i for i in issues if "pull_request" not in i]
    return issues[0] if issues else None


def last_state(gh: GitHub, issue_number: int) -> str:
    """The state recorded by the newest watcher comment on the tracker (UNKNOWN if there is none)."""
    comments = gh("GET", f"/issues/{issue_number}/comments?per_page=100") or []
    for comment in reversed(comments):
        body = str(comment.get("body") or "")
        if f"<!-- {MARKER}:" not in body:
            continue
        for part in body.split(f"<!-- {MARKER}:", 1)[1].split("-->", 1)[0].split():
            if part.startswith("state="):
                return part.split("=", 1)[1]
    return UNKNOWN


def comment_body(state: str, sha: str, evidence: str, branch: str) -> str:
    marker = f"<!-- {MARKER}: state={state} sha={sha} -->"
    if state == RED:
        head = f"🔴 **The site build is red on `{branch}`** at `{sha[:9]}`."
        tail = ("The site is not deploying, so every documentation change since the last successful "
                "build is not live. The watcher opened this rather than blocking merges, because a "
                "required check that is red blocks the merge that would fix it.\n\n"
                "The build log needs the Builds API (a user-scoped `CF_BUILDS_TOKEN`): dispatch "
                "**CF diagnostics** — its `Workers Builds` step prints the trigger, the recent builds "
                "and the failing build's log:")
    elif state == GREEN:
        head = f"🟢 **The site build is green again** at `{sha[:9]}`."
        tail = ("The site is deploying again. Whether that closes this issue is your call — the "
                "watcher only reports.")
    else:  # pragma: no cover - defensive, the state machine never writes this
        head = f"⚪ **The site build state is unclear** at `{sha[:9]}`."
        tail = "Nothing to do; recorded so the next transition has a baseline."
    return (f"{head}\n\nEvidence: {evidence}\n\n{tail}\n\n"
            f"<sub>Automated by `scripts/workers_builds_watch.py` — transitions only, never on every "
            f"push.</sub>\n\n{marker}")


# ── the decision, as a pure function so it can be tested without a network ───────────────────────────

def plan(state: str, tracker_exists: bool, previous: str) -> str:
    """One of `create`, `comment`, `none` — the whole policy, in one readable place."""
    if state == UNKNOWN:
        return "none"
    if not tracker_exists:
        return "create" if state == RED else "none"
    if previous == state:
        return "none"
    return "comment"


def resolve_target(gh: GitHub, args) -> tuple[str, str, str]:
    """(sha, branch, why) — the commit to check, and which route produced it.

    `why` exists so the log says the true reason for declining. The first version returned an empty
    sha for a feature branch and then printed "no commit for main (branch main is not visible?)", which
    would send a reader hunting a permissions problem that is not there: the branch was skipped **on
    purpose**, because a red site build on a feature branch is its author's business, not something to
    file on the maintainer's tracker.
    """
    if args.sha:
        return args.sha, args.branch, "explicit --sha"
    if args.event:
        payload = json.loads(Path(args.event).read_text(encoding="utf-8"))
        suite = payload.get("check_suite") or {}
        sha = suite.get("head_sha") or (payload.get("after") if payload else None)
        if sha:
            branch = suite.get("head_branch") or args.branch
            if branch != args.branch and not args.any_branch:
                return "", branch, "not-the-deploying-branch"
            return sha, branch, "event payload"
    head = gh("GET", f"/branches/{args.branch}") or {}
    return str(((head.get("commit") or {}).get("sha")) or ""), args.branch, "branch tip"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--event", help="a GitHub event payload (the check_suite that just completed)")
    parser.add_argument("--repo", default=os.environ.get("GH_REPO", DEFAULT_REPO),
                        help=f"owner/name (default $GH_REPO, else {DEFAULT_REPO})")
    parser.add_argument("--sha", help="check this commit instead of reading an event")
    parser.add_argument("--branch", default="main", help="the branch that deploys the site (default main)")
    parser.add_argument("--any-branch", action="store_true",
                        help="also report builds on other branches (default: main only)")
    parser.add_argument("--dry-run", action="store_true", help="print the decision, write nothing")
    args = parser.parse_args()

    repo = args.repo
    gh = GitHub(repo, token(), os.environ.get("GH_API_BASE", "https://api.github.com"))

    sha, branch, why = resolve_target(gh, args)
    if not sha:
        if why == "not-the-deploying-branch":
            print(f"skipped on purpose: {branch} is not {args.branch}, and only the branch that "
                  f"deploys the site is worth a tracker issue (use --any-branch to report others)")
        else:
            print(f"nothing to check: no commit resolved for {args.branch} (is it visible to this token?)")
        return 0
    print(f"repo={repo} branch={branch} sha={sha[:9]} ({why})")

    state, evidence = site_build_state(gh, sha)
    print(f"site build: {state} — {evidence}")

    tracker = open_tracker(gh)
    previous = last_state(gh, tracker["number"]) if tracker else UNKNOWN
    action = plan(state, tracker is not None, previous)
    print(f"tracker={tracker['number'] if tracker else 'none'} last={previous} -> {action}")

    if action == "none":
        return 0

    if action == "create":
        body = (f"`Workers Builds: misakanet-web` is the Cloudflare Git integration that deploys "
                f"`docs/` to misakanet.org. It is not one of the checks the ruleset requires, and its "
                f"check-run carries no log — so this is how a red site build becomes visible instead "
                f"of blocking merges.\n\n" + comment_body(state, sha, evidence, branch))
        if args.dry_run:
            print("--- would create the tracking issue ---")
            print(body)
            return 0
        # Tolerate "already exists": this is a label the repository may already have, and a 422 here
        # must not stop the issue from being opened.
        try:
            gh("POST", "/labels", {"name": LABEL, "color": LABEL_COLOR,
                                   "description": LABEL_DESCRIPTION[:100]})
        except RuntimeError as error:
            print(f"(label not created: {str(error).splitlines()[0]})")
        issue = gh("POST", "/issues", {"title": TITLE, "body": body, "labels": [LABEL]})
        print(f"opened #{issue['number']}: {issue['html_url']}")
        return 0

    if args.dry_run:
        print(f"--- would comment on #{tracker['number']} ---")
        print(comment_body(state, sha, evidence, branch))
        return 0
    comment = gh("POST", f"/issues/{tracker['number']}/comments",
                 {"body": comment_body(state, sha, evidence, branch)})
    print(f"commented: {comment['html_url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
