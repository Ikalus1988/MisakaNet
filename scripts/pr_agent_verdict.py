#!/usr/bin/env python3
"""Say what each recent pr-agent red *meant* — the runtime half of #2972.

The check's conclusion cannot carry that meaning. `failure` is what a reviewer sees for "the model
reviewed and refused", for "the model timed out", and for "the secret was missing"; `success` was
also what a `synchronize` run reported when it skipped before calling the model at all (removed from
the trigger 2026-11-03). The logs *can* tell them apart, and this reads them:

    Reviewing PR                                  → the model was actually called
    APITimeoutError / ReadTimeout / "Failed to review PR"
                                                  → the model or the network, not the diff
    OPENAI_KEY ... not set / 401                  → no secret on this run (a fork, usually)
    Skipping action                               → the action declined before the model call

Usage
-----
    python3 scripts/pr_agent_verdict.py                  # last 10 failed runs, human table
    python3 scripts/pr_agent_verdict.py --limit 3 --json # machine-readable
    GH_TOKEN=... python3 scripts/pr_agent_verdict.py     # CI: reads the Actions API

Why a script and not a gate: a timeout red cannot be *fixed* by a pull request, and a workflow that
failed every time the model timed out would be a second red saying the same thing. The product is the
classification, so a maintainer (or the scheduled verdict workflow) reads one line instead of a log.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

WORKFLOW = "pr-agent-review.yml"
REPO = "Ikalus1988/MisakaNet"
API = "https://api.github.com"

#: In priority order: a log that contains both a model call and a timeout is a timeout (the call
#: started and did not finish), and a skipped action never reached the model at all.
TIMEOUT = re.compile(r"APITimeoutError|ReadTimeout|Read timed out|exceeded the maximum execution "
                     r"time|Failed to review PR|TimeoutError", re.I)
MISSING_SECRET = re.compile(r"OPENAI_KEY\b.{0,40}(not set|missing)|401 Unauthorized|Incorrect API key",
                            re.I | re.S)
SKIPPED = re.compile(r"Skipping action", re.I)
REVIEWED = re.compile(r"Reviewing PR", re.I)


def classify(text: str) -> str:
    """What the log says this run was. The error wins over the marker, in both directions."""
    if TIMEOUT.search(text):
        return "model_timeout"
    if MISSING_SECRET.search(text):
        return "missing_secret"
    if SKIPPED.search(text):
        return "skipped"
    if REVIEWED.search(text):
        return "reviewed"
    return "unknown"


class _StripAuthOnCrossHostRedirect(urllib.request.HTTPRedirectHandler):
    """The log endpoint redirects to a blob URL; that host rejects the API's Bearer token (401).

    Measured 2026-11-04: every `logs` request came back as `HTTP Error 401: Server failed to
    authenticate the request` because urllib replayed `Authorization` to the redirected host. The
    token authenticates the API call, not the signed URL it hands back.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            return None
        if urllib.parse.urlsplit(newurl).netloc != urllib.parse.urlsplit(req.full_url).netloc:
            for store in (redirected.headers, redirected.unredirected_hdrs):
                for key in list(store):
                    if key.lower() == "authorization":
                        del store[key]
        return redirected


_OPENER = urllib.request.build_opener(_StripAuthOnCrossHostRedirect)


def _get(url: str, token: str, *, text: bool = False):
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "misakanet-pr-agent-verdict",
    })
    with _OPENER.open(request, timeout=60) as response:
        raw = response.read()
    return raw.decode("utf-8", "replace") if text else json.loads(raw)


def failed_runs(limit: int, token: str) -> list[dict]:
    url = (f"{API}/repos/{REPO}/actions/workflows/{WORKFLOW}/runs"
           f"?status=failure&per_page={max(limit * 2, 20)}")
    return _get(url, token)["workflow_runs"][:limit]


def job_log(run_id: int, token: str) -> str:
    jobs = _get(f"{API}/repos/{REPO}/actions/runs/{run_id}/jobs", token).get("jobs") or []
    chunks = []
    for job in jobs:
        try:
            chunks.append(_get(f"{API}/repos/{REPO}/actions/jobs/{job['id']}/logs", token,
                               text=True))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            chunks.append(f"[[log unavailable: {error}]]")
    return "\n".join(chunks)


def verdicts(limit: int, token: str) -> list[dict]:
    out = []
    for run in failed_runs(limit, token):
        text = job_log(run["id"], token)
        out.append({
            "run": run["id"],
            "created_at": run.get("created_at"),
            "head_sha": (run.get("head_sha") or "")[:9],
            "url": run.get("html_url"),
            "verdict": classify(text),
        })
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=10, help="how many failed runs to read")
    parser.add_argument("--json", action="store_true", help="print the verdicts as JSON")
    args = parser.parse_args(argv)

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GH_TOKEN (or GITHUB_TOKEN) is required: the verdicts are read from the Actions API",
              file=sys.stderr)
        return 2

    rows = verdicts(args.limit, token)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0

    print(f"# pr-agent verdicts — last {len(rows)} failed run(s)")
    print()
    print("| run | when | verdict | url |")
    print("|---|---|---|---|")
    for row in rows:
        print(f"| `{row['run']}` | {row['created_at']} | **{row['verdict']}** | {row['url']} |")
    if not rows:
        print("(no failed runs in the window — which is not the same as `reviewed`)")
    counts = {}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    if counts:
        print()
        print("| verdict | runs | what it means for a reader |")
        print("|---|---|---|")
        meanings = {
            "model_timeout": "infra — the model did not answer; re-run `/review`, do not read the red as a code verdict",
            "missing_secret": "the run had no model secret (fork); the `/review` path on the base repo is the one that reviews",
            "skipped": "the action declined before the model call — nothing was reviewed",
            "reviewed": "the model was called (the run failed afterwards)",
            "unknown": "no marker in the log — this is the one worth a human's time",
        }
        for verdict, count in sorted(counts.items(), key=lambda item: -item[1]):
            print(f"| `{verdict}` | {count} | {meanings[verdict]} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
