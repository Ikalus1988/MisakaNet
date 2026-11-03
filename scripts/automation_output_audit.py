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

A fourth shape turned out to be the worst of them: **a run that failed without ever starting.**
GitHub refuses a workflow file it will not parse — an `${{ }}` inside a comment, a job key beside a
reusable-workflow `uses:`, an illegal permission scope — before any job exists, so the run has zero
jobs, no log, and no annotation, and its check-suite name falls back to the file path. That is how
`guarded-repository.yml` failed every run for a month (#3232) and how `provenance-gate.yml` produced
a red run on every push for eight days (#2957), both while every static gate in this repository was
green. No YAML parser sees those refusals, which is why this rule asks GitHub what actually ran.

Nothing watched the ratio of *runs* to *output*, so all four were invisible. This script does, and
it fails the job it runs in when the numbers say something is wrong. It is deliberately a small
manifest plus one general rule rather than an oracle: an automation is listed with the artifact it
exists to produce, and the probe is the cheapest query that can see that artifact.

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

# ── the zero-job rule ────────────────────────────────────────────────────────────────────────
# `head_branch` on a run tells us which ref it came from, which is the whole verdict: a file GitHub
# refuses on `main` is a defect in the default branch, while the same shape on a feature branch is
# usually an older copy of that file in a branch someone re-pushed — real, but not a verdict on
# `main`. Splitting the two is what keeps this rule from becoming the alarm people mute.
DEFAULT_BRANCH = "main"

# One runs listing covers the window; every failed run in it needs one jobs listing to tell
# "failed" from "never started". The cap keeps the weekly job to a dozen calls. When the cap is
# reached the table says how much of the window was examined instead of implying it was all of it.
ZERO_JOB_PROBES = 12

# This rule asks a different question from the rest of the audit: not "how has the month gone" but
# "is anything refused *now*". A refused workflow fails on every trigger, so one week is enough to
# see it, and the job runs weekly. Measuring it over the audit's 30-day window instead fails the
# build for incidents that were fixed weeks ago: on 2026-11-03 the first draft flagged two
# `startup_failure` runs from 2026-10-07 — the same incident as #3232/#2957, already fixed — and
# would have kept doing so until they aged out.
ZERO_JOB_WINDOW_DAYS = 7

RUNS_PER_PAGE = 100


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


def _run_label(run: dict) -> str:
    """What to call the workflow in a finding.

    A path here is itself the symptom: GitHub falls back to the file path when it cannot read the
    file's `name:`, so a finding that says `.github/workflows/x.yml` is telling the reader that
    #2957's registration state is back. Kept verbatim rather than prettified, because that fallback
    is the one clue the run gives.
    """
    label = run.get("name") or run.get("path") or f"workflow {run.get('workflow_id', '?')}"
    return str(label)


def _runs_with_status(repo: str, status: str, since: datetime, token: str,
                      fetch=api_get) -> dict:
    """One page of runs GitHub has already concluded with `status`, newest first.

    The `status` filter is not cosmetic: this repository produced 494 failed runs on `main` in the
    30 days to 2026-11-03, so an unfiltered page of 100 runs covers about three days and would miss
    a workflow that broke a fortnight ago. Asking for the status makes the page about failures.
    """
    query = urllib.parse.urlencode({
        "status": status,
        "created": f">={since:%Y-%m-%d}",
        "per_page": RUNS_PER_PAGE,
    })
    return fetch(f"{API}/repos/{repo}/actions/runs?{query}", token)


def zero_job_findings(repo: str, since: datetime, token: str, fetch=api_get,
                      max_probes: int = ZERO_JOB_PROBES) -> tuple[list[Finding], dict]:
    """Runs that concluded failure without ever starting a job.

    Two sources, because GitHub labels the same defect two ways:

    * `startup_failure` — GitHub says outright that the run never started. Definitive, no probe.
    * `failure` with zero jobs — what #3232 and #2957 carry: the conclusion is an ordinary failure,
      and only the jobs endpoint reveals that no job ever existed.

    The first is cheap, so it is exhaustive; the second costs one call per run, so it is sampled —
    default-branch failures first, because that is the only branch where this is a defect in the
    repository rather than in someone's stale branch. `stats` carries the coverage so the table can
    say "examined N of M" instead of implying that unexamined runs were healthy.
    """
    failed_data = _runs_with_status(repo, "failure", since, token, fetch)
    failed = failed_data.get("workflow_runs") or []
    never_data = _runs_with_status(repo, "startup_failure", since, token, fetch)
    never_started = never_data.get("workflow_runs") or []

    findings: list[Finding] = []
    on_default: dict[str, list[dict]] = {}
    on_branches: list[dict] = []

    def record(run: dict) -> None:
        if run.get("head_branch") == DEFAULT_BRANCH:
            on_default.setdefault(_run_label(run), []).append(run)
        else:
            on_branches.append(run)

    for run in never_started:
        record(run)

    # Default branch first, stable within each group: the verdict that matters is `main`'s, and the
    # sample has to spend its probes there before it spends them on feature branches.
    ordered = sorted(failed, key=lambda run: run.get("head_branch") != DEFAULT_BRANCH)
    probed = 0
    for run in ordered:
        if probed >= max_probes:
            break
        probed += 1
        jobs = fetch(f"{API}/repos/{repo}/actions/runs/{run.get('id')}/jobs?per_page=1", token)
        if int(jobs.get("total_count") or 0) > 0:
            continue  # a real failure with a log to read — other rules and people handle those
        record(run)

    total_failed = int(failed_data.get("total_count") or len(failed))
    total_never = int(never_data.get("total_count") or len(never_started))
    examined = len(never_started) + probed
    stats = {
        "failed_runs": total_failed + total_never,
        "examined": examined,
        "zero_job": sum(len(hits) for hits in on_default.values()) + len(on_branches),
        "truncated": examined < total_failed + total_never,
    }

    for label, hits in on_default.items():
        newest = hits[0]
        findings.append(Finding(
            label, "zero-job-failure",
            f"{len(hits)} failed run(s) on {DEFAULT_BRANCH} never started (0 jobs) — newest "
            f"{newest.get('created_at', '?')} at {newest.get('html_url', '')}. GitHub refused the "
            "workflow before any job existed, so there is no log and no annotation to read: look "
            "for what GitHub will not parse (an expression in a comment, a key beside a "
            "reusable-workflow `uses:`, a permission scope it does not know).",
            "fail",
        ))
    if on_branches:
        newest = on_branches[0]
        findings.append(Finding(
            "feature branches", "zero-job-failure",
            f"{len(on_branches)} failed run(s) on non-default branches never started (0 jobs) — "
            f"newest {newest.get('created_at', '?')} on {newest.get('head_branch', '?')} "
            f"({newest.get('html_url', '')}). Usually a branch still carrying a file version "
            "GitHub refuses; it is not a verdict on the default branch, so this is a note.",
            "note",
        ))
    return findings, stats


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

    # The general rule, last: it is the only one that reads *runs* rather than a manifest entry.
    # Its window is its own (see ZERO_JOB_WINDOW_DAYS) — it asks whether anything is refused now.
    zero_findings, zero_stats = zero_job_findings(
        repo, now - timedelta(days=ZERO_JOB_WINDOW_DAYS), token, fetch)
    findings.extend(zero_findings)
    coverage = (f"examined {zero_stats['examined']} of {zero_stats['failed_runs']} "
                "failed run(s)")
    table.append({
        "workflow": "(all workflows)",
        "runs_in_window": zero_stats["examined"],
        "outputs_ever": zero_stats["zero_job"],
        "produces": (f"runs that actually start — {coverage} in the last "
                     f"{ZERO_JOB_WINDOW_DAYS}d for 0 jobs"
                     + ("; the window's failures are sampled, not exhaustively probed"
                        if zero_stats["truncated"] else "")),
    })

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
                     f"ran fewer than {MIN_RUNS_WITHOUT_OUTPUT} times in the window, and no failed "
                     "run in the window had zero jobs.")
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
