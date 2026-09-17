#!/usr/bin/env python3
"""Reconcile automations against their output (2026-09-17).

Why this exists
---------------
Three separate failures in one week had the same shape: **a workflow that looked healthy while
producing nothing.**

* `pr-genius-check.yml` — 1,459 runs, and **zero** comments ever posted: the permission was
  `pull-requests: read` and every attempt answered `403 Forbidden`, printed to stderr and never
  surfaced. Its check stayed green for months.
* `intake-bot-demo.yml` — 21,126 runs, 98.1% `skipped`, and a non-skipped run usually logged
  "No associated PR found, skipping comment".
* `arch-review.yml` — active, scheduled monthly, **never ran once** (`total_count = 0`).

Nothing watched the ratio of *runs* to *output*, so all three were invisible. This script does, and
it fails the job it runs in when the ratio says something is wrong. It is deliberately a small
manifest rather than a general oracle: an automation is listed with the artifact it exists to
produce, and the probe is the cheapest query that can see that artifact.

Usage
-----
    python3 scripts/automation_output_audit.py                       # window = 30 days
    python3 scripts/automation_output_audit.py --window-days 7
    python3 scripts/automation_output_audit.py --json

Requires `GITHUB_TOKEN` (or `GH_TOKEN`) with `actions: read` and public-repo search access; reads
only, and it never writes to GitHub.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

DEFAULT_REPO = "Ikalus1988/MisakaNet"
API = "https://api.github.com"

# A workflow that runs this often and still produces nothing is not "quiet", it is broken. Below
# the threshold the workflow may simply not have had a reason to fire yet (which is why the
# intake-bot demo, once its wildcard trigger was narrowed, no longer trips this rule).
MIN_RUNS_WITHOUT_OUTPUT = 20

# Scheduled automations that must have run at least once. Dispatch-only workflows are excluded on
# purpose: "never ran" is their normal state until a human asks.
MUST_HAVE_RUN = ("arch-review.yml",)

# Manual-only automations: they are *supposed* to be quiet, so zero runs in the window is not a
# defect — but their state should still be visible, because "configured but nobody has run it in
# three months" is a decision waiting to be made (delete it, or give it a trigger). Listed here
# rather than in AUTOMATIONS: they have no artifact to reconcile, only a last-run date.
MANUAL_ONLY = ("auto-draft.yml", "intake-pipeline-test.yml")

# A new automation has to reach its first scheduled slot before "never ran" means anything. This
# repository's longest schedule is monthly (`arch-review.yml`: `0 2 1 * *`), so anything younger
# than this is reported as *too new to judge* rather than broken — the first draft of this rule
# failed `arch-review.yml`, which was added on 2026-09-06 and is not due until 2026-10-01. A rule
# that fails a legitimate state is a rule people learn to mute.
GRACE_DAYS = 45


@dataclass(frozen=True)
class Automation:
    """One workflow and the artifact it exists to produce."""

    workflow: str
    # A GitHub search query (always scoped to the repo) that finds that artifact. `total_count` is
    # what we read, so the query only has to be *findable*, not exhaustive.
    probe: str
    produces: str


AUTOMATIONS = (
    Automation(
        "pr-genius-check.yml",
        'in:comments "PR Genius Analysis"',
        "a PR comment carrying the analysis",
    ),
    Automation(
        "auto-merge-lessons.yml",
        "is:pr is:merged label:auto-merge-lesson",
        "a PR it merged by itself",
    ),
    Automation(
        "intake-salvage-digest.yml",
        "is:issue label:salvage-digest",
        "the digest issue it opens",
    ),
    Automation(
        "intake-bot-demo.yml",
        'in:comments "MisakaNet: Lesson Found"',
        "the lesson-suggestion comment on a failing PR",
    ),
)


@dataclass
class Finding:
    workflow: str
    rule: str
    detail: str
    severity: str  # "fail" | "note"


def api_get(url: str, token: str) -> dict:
    """The single network seam — tests replace this, so the rules are testable offline."""
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "misakanet-automation-output-audit",
    })
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # keep the caller's report nameable
        raise RuntimeError(f"GET {url} → HTTP {exc.code}") from exc


def runs_in_window(repo: str, workflow: str, since: datetime, token: str, fetch=api_get) -> int:
    """How many runs this workflow started on/after `since` (uses the API's own count)."""
    query = urllib.parse.urlencode({"created": f">={since:%Y-%m-%d}", "per_page": 1})
    data = fetch(f"{API}/repos/{repo}/actions/workflows/{workflow}/runs?{query}", token)
    return int(data.get("total_count") or 0)


def runs_ever(repo: str, workflow: str, token: str, fetch=api_get) -> int:
    query = urllib.parse.urlencode({"per_page": 1})
    data = fetch(f"{API}/repos/{repo}/actions/workflows/{workflow}/runs?{query}", token)
    return int(data.get("total_count") or 0)


def workflow_created_at(repo: str, workflow: str, token: str, fetch=api_get) -> datetime | None:
    """When the workflow file appeared, per the API — used only for the "never ran" grace period."""
    try:
        data = fetch(f"{API}/repos/{repo}/actions/workflows/{workflow}", token)
    except RuntimeError:
        return None
    raw = data.get("created_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def last_run_at(repo: str, workflow: str, token: str, fetch=api_get) -> str | None:
    """The most recent run's timestamp, or None if there has never been one."""
    query = urllib.parse.urlencode({"per_page": 1})
    try:
        data = fetch(f"{API}/repos/{repo}/actions/workflows/{workflow}/runs?{query}", token)
    except RuntimeError:
        return None
    runs = data.get("workflow_runs") or []
    return (runs[0].get("created_at") if runs else None)


def output_count(repo: str, probe: str, token: str, fetch=api_get) -> int:
    """How many artifacts the probe can find, ever (the artifact is what persists)."""
    query = urllib.parse.urlencode({"q": f"repo:{repo} {probe}", "per_page": 1})
    data = fetch(f"{API}/search/issues?{query}", token)
    return int(data.get("total_count") or 0)


def audit(repo: str, days: int, token: str, fetch=api_get, now: datetime | None = None) -> tuple[list[Finding], list[dict]]:
    """Return (findings, table). `fail` findings mean the job should fail."""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    findings: list[Finding] = []
    table: list[dict] = []

    for automation in AUTOMATIONS:
        runs = runs_in_window(repo, automation.workflow, since, token, fetch)
        produced = output_count(repo, automation.probe, token, fetch)
        table.append({
            "workflow": automation.workflow,
            "runs_in_window": runs,
            "outputs_ever": produced,
            "produces": automation.produces,
        })
        if produced == 0 and runs >= MIN_RUNS_WITHOUT_OUTPUT:
            findings.append(Finding(
                automation.workflow, "runs-without-output",
                f"{runs} runs in {days} days and no {automation.produces} "
                f"(probe: {automation.probe!r})",
                "fail",
            ))

    for workflow in MANUAL_ONLY:
        ever = runs_ever(repo, workflow, token, fetch)
        last = last_run_at(repo, workflow, token, fetch)
        table.append({"workflow": workflow, "runs_in_window": None, "outputs_ever": None,
                      "produces": "nothing on its own — manual dispatch only"})
        if ever == 0:
            findings.append(Finding(
                workflow, "manual-only",
                "dispatch-only and never run: either wire a trigger or delete it, so the file does "
                "not read as a working automation",
                "note",
            ))
        elif last:
            findings.append(Finding(
                workflow, "manual-only",
                f"manual dispatch only; last run {last[:10]} — fine if that is intended, worth a "
                "decision otherwise",
                "note",
            ))

    for workflow in MUST_HAVE_RUN:
        ever = runs_ever(repo, workflow, token, fetch)
        created = workflow_created_at(repo, workflow, token, fetch)
        age = None if created is None else (now - created).days
        table.append({"workflow": workflow, "runs_in_window": None, "outputs_ever": None,
                      "produces": "at least one run, ever"})
        if ever:
            continue
        if age is not None and age < GRACE_DAYS:
            findings.append(Finding(
                workflow, "never-ran",
                f"added {age} days ago and has not run yet — its first scheduled slot may simply "
                f"not have arrived (grace: {GRACE_DAYS} days, the longest schedule here is monthly)",
                "note",
            ))
        else:
            findings.append(Finding(
                workflow, "never-ran",
                "the workflow is active and scheduled, but has never run once — either its trigger "
                "is broken or nobody wants it; delete it or fix the trigger",
                "fail",
            ))

    return findings, table


def render(findings: list[Finding], table: list[dict], repo: str, days: int) -> str:
    lines = [f"# Automation output audit — {repo}, window {days}d", "",
             "| workflow | runs (window) | outputs (ever) | expected artifact |",
             "|---|---|---|---|"]
    for row in table:
        runs = "—" if row["runs_in_window"] is None else row["runs_in_window"]
        outs = "—" if row["outputs_ever"] is None else row["outputs_ever"]
        lines.append(f"| `{row['workflow']}` | {runs} | {outs} | {row['produces']} |")
    lines.append("")
    if findings:
        lines.append("## Findings")
        for finding in findings:
            lines.append(f"- **{finding.severity.upper()}** `{finding.workflow}` [{finding.rule}]: "
                         f"{finding.detail}")
    else:
        lines.append("## Findings\n\nNone: every listed automation either produced its artifact or "
                     f"ran fewer than {MIN_RUNS_WITHOUT_OUTPUT} times in the window.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile automations against their output")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "")
    args = parser.parse_args(argv)

    if not args.token:
        print("GITHUB_TOKEN (or GH_TOKEN) is required: the audit reads the Actions API", file=sys.stderr)
        return 2

    try:
        findings, table = audit(args.repo, args.window_days, args.token)
    except RuntimeError as exc:
        # A read failure is not a verdict on the automations: say so and stay green, the same rule
        # the gates in this repo follow (only fail on evidence).
        print(f"::warning::automation output audit could not run: {exc}")
        return 0

    if args.json:
        print(json.dumps({"repo": args.repo, "window_days": args.window_days,
                          "table": table, "findings": [f.__dict__ for f in findings]},
                         indent=2, ensure_ascii=False))
    else:
        print(render(findings, table, args.repo, args.window_days))

    failures = [f for f in findings if f.severity == "fail"]
    for finding in failures:
        print(f"::error title={finding.rule}::{finding.workflow}: {finding.detail}",
              file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
