#!/usr/bin/env python3
"""The automation output audit, tested offline against the failures it exists to catch.

Three automations looked healthy while producing nothing in September 2026, and no check anywhere
looked at the ratio of runs to output: `pr-genius-check.yml` (1,459 runs, zero comments ever — a
403 on every attempt), `intake-bot-demo.yml` (21,126 runs, 98.1% skipped, no output) and
`arch-review.yml` (active, scheduled, zero runs ever). These tests feed the audit the numbers that
were true then and assert it fails; then they feed it the numbers that are true after the fixes and
assert it passes. That pair is the point: a gate that cannot fail on a known-bad input is not a
gate.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "automation_output_audit.py"
sys.path.insert(0, str(REPO_ROOT))

import scripts.automation_output_audit as audit_mod  # noqa: E402
from subprocess_env import child_env  # tests/subprocess_env.py


def fake_fetch(window_runs: dict[str, int], output_counts: dict[str, int], ever_runs: dict[str, int],
               created: dict[str, str] | None = None):
    """A `fetch` stand-in keyed on what each URL is asking for."""
    created = created if created is not None else {}

    def fetch(url: str, token: str) -> dict:
        if "/actions/workflows/" in url and "/runs" not in url:
            for workflow, stamp in created.items():
                if url.endswith(f"/workflows/{workflow}"):
                    return {"created_at": stamp}
            return {"created_at": "2026-01-01T00:00:00Z"}  # old by default: judgeable
        if "/search/issues?" in url:
            for marker, count in output_counts.items():
                if marker in url:
                    return {"total_count": count}
            return {"total_count": 0}
        if "/runs?" in url:
            for workflow, count in window_runs.items():
                if f"workflows/{workflow}/runs" in url and "created=" in url:
                    return {"total_count": count}
            for workflow, count in ever_runs.items():
                if f"workflows/{workflow}/runs" in url:
                    runs = [{"created_at": "2026-06-22T00:00:00Z"}] if count else []
                    return {"total_count": count, "workflow_runs": runs}
            return {"total_count": 0}
        raise AssertionError(f"unexpected URL: {url}")

    return fetch


def run_audit(window_runs, output_counts, ever_runs, created=None):
    return audit_mod.audit(
        "owner/repo", 30, "token",
        fetch=fake_fetch(window_runs, output_counts, ever_runs, created),
        now=datetime(2026, 9, 17, tzinfo=timezone.utc),
    )


# ── the historical failures: the audit must fail on them ───────────────────────────────
def test_it_would_have_caught_pr_genius_producing_nothing_for_months():
    findings, table = run_audit(
        window_runs={"pr-genius-check.yml": 300},
        output_counts={},  # zero comments, ever — the 403 state
        ever_runs={"arch-review.yml": 5},
    )
    failures = [f for f in findings if f.severity == "fail"]
    assert failures, table
    assert failures[0].workflow == "pr-genius-check.yml"
    assert failures[0].rule == "runs-without-output"
    assert "300 runs" in failures[0].detail


def test_it_would_have_caught_the_intake_demo_spinning():
    findings, _ = run_audit(
        window_runs={"intake-bot-demo.yml": 900},
        output_counts={},
        ever_runs={"arch-review.yml": 5},
    )
    assert any(f.workflow == "intake-bot-demo.yml" and f.rule == "runs-without-output"
               for f in findings), findings


def test_it_catches_a_scheduled_workflow_that_never_ran_once_it_is_old_enough():
    """An old, scheduled workflow with zero runs is the `arch-review.yml` shape — a real defect."""
    findings, _ = run_audit({}, {}, ever_runs={"arch-review.yml": 0},
                            created={"arch-review.yml": "2026-01-01T00:00:00Z"})
    failures = [f for f in findings if f.severity == "fail"]
    assert any(f.workflow == "arch-review.yml" and f.rule == "never-ran" for f in failures), findings


def test_a_new_workflow_is_not_called_dead_before_its_first_scheduled_slot():
    """The false positive this rule shipped with and had to lose.

    `arch-review.yml` was added 2026-09-06 with a monthly cron (`0 2 1 * *`) — due 2026-10-01. The
    first version of this audit failed it for "never ran", which is just the schedule not having
    come around yet.
    """
    findings, _ = run_audit({}, {}, ever_runs={"arch-review.yml": 0},
                            created={"arch-review.yml": "2026-09-06T00:00:00Z"})
    failures = [f for f in findings if f.severity == "fail"]
    assert failures == [], findings
    arch = [f for f in findings if f.workflow == "arch-review.yml"]
    assert arch and arch[0].severity == "note" and arch[0].rule == "never-ran", findings
    assert "grace" in arch[0].detail, arch[0].detail


# ── the fixed state: the audit must pass ──────────────────────────────────────────────
def test_the_fixed_state_passes():
    findings, table = run_audit(
        # pr-genius now posts comments, so it is no longer "runs without output"
        window_runs={"pr-genius-check.yml": 300, "auto-merge-lessons.yml": 40,
                     "intake-salvage-digest.yml": 30, "intake-bot-demo.yml": 2},
        output_counts={"PR+Genius+Analysis": 12, "auto-merge-lesson": 1,
                       "salvage-digest": 1},
        ever_runs={"arch-review.yml": 6},
    )
    assert [f for f in findings if f.severity == "fail"] == [], (findings, table)


def test_a_quiet_workflow_without_output_is_not_flagged():
    """The narrowed intake-bot demo runs a handful of times and may produce nothing yet.

    This is the line between "broken" and "has not had a reason to fire": below the threshold the
    audit stays quiet, which is what keeps it from becoming the kind of alarm people mute.
    """
    findings, _ = run_audit(
        window_runs={"intake-bot-demo.yml": audit_mod.MIN_RUNS_WITHOUT_OUTPUT - 1},
        output_counts={},
        ever_runs={"arch-review.yml": 3},
    )
    assert [f for f in findings if f.severity == "fail"] == [], findings


def test_the_table_always_reports_every_listed_automation():
    _, table = run_audit({}, {}, ever_runs={"arch-review.yml": 1})
    listed = {row["workflow"] for row in table}
    assert {a.workflow for a in audit_mod.AUTOMATIONS} <= listed
    assert set(audit_mod.MUST_HAVE_RUN) <= listed
    for row in table:
        assert row["produces"], row  # an entry must say what it is supposed to produce


# ── failure modes of the audit itself ─────────────────────────────────────────────────
def test_cli_exits_zero_with_a_warning_when_the_api_is_unreachable(monkeypatch, capsys):
    def broken(url, token):
        raise RuntimeError("GET … → HTTP 403")

    monkeypatch.setattr(audit_mod, "api_get", broken)
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    assert audit_mod.main(["--repo", "owner/repo"]) == 0
    captured = capsys.readouterr()
    assert "::warning::" in captured.out
    assert "could not run" in captured.out


def test_cli_requires_a_token(capsys):
    exit_code = subprocess.run(
        [sys.executable, str(SCRIPT), "--token", ""],
        capture_output=True, text=True, env=child_env(),
    )
    assert exit_code.returncode == 2
    assert "GITHUB_TOKEN" in exit_code.stderr


def test_the_manifest_probes_are_scoped_to_the_repo_at_call_time():
    """Guards against a probe that would silently read another repository's artifacts."""
    query = audit_mod.AUTOMATIONS[0].probe
    assert query.startswith("in:comments") or query.startswith("is:"), query
    assert "repo:" not in query, "the repo is added by output_count(); a literal here would double it"


def test_manual_only_workflows_are_listed_and_never_fail_the_run():
    """The objective named these two as "dead and unreconciled"; now their state is on the screen.

    They are dispatch-only, so zero runs in a window is normal — the audit lists the last run and
    says it is worth a decision, but never fails the run for it. A note is the right severity for
    "nothing is wrong, yet".
    """
    findings, table = run_audit({}, {}, ever_runs={"arch-review.yml": 3, "auto-draft.yml": 1,
                                                  "intake-pipeline-test.yml": 0})
    listed = {row["workflow"] for row in table}
    assert {"auto-draft.yml", "intake-pipeline-test.yml"} <= listed, listed
    assert [f for f in findings if f.severity == "fail"] == [], findings
    notes = {f.workflow: f for f in findings if f.severity == "note"}
    assert notes["auto-draft.yml"].rule == "manual-only"
    assert "last run 2026-06-22" in notes["auto-draft.yml"].detail
    assert "never run" in notes["intake-pipeline-test.yml"].detail

# ── the zero-job rule: a run that failed without ever starting ────────────────────────────────
# GitHub refuses a workflow file it will not parse *before* any job exists. The run then has zero
# jobs, no log, no annotation, and a name that may fall back to the file path. Two issues in this
# repository (#3232 guarded-repository 100/100 failures, #2957 a red run on every push) were this
# one shape, and each took weeks to diagnose because no gate looked at runs at all.
def run_entry(run_id, name, branch, conclusion="failure", created="2026-10-22T15:21:44Z"):
    return {
        "id": run_id,
        "name": name,
        "head_branch": branch,
        "conclusion": conclusion,
        "created_at": created,
        "html_url": f"https://github.com/owner/repo/actions/runs/{run_id}",
        "workflow_id": 1,
    }


def fake_fetch_all(failed=(), startup=(), jobs=None, total_failed=None, total_startup=None):
    """A `fetch` for the whole audit. Records which runs were probed for jobs."""
    probed = []

    def fetch(url, token):
        if "/actions/runs?" in url:
            if "status=startup_failure" in url:
                return {"total_count": total_startup if total_startup is not None else len(startup),
                        "workflow_runs": list(startup)}
            return {"total_count": total_failed if total_failed is not None else len(failed),
                    "workflow_runs": list(failed)}
        if "/jobs" in url:
            run_id = int(url.split("/actions/runs/")[1].split("/")[0])
            probed.append(run_id)
            return {"total_count": (jobs or {}).get(run_id, 0)}
        if "/actions/workflows/" in url and "/runs?" in url:
            return {"total_count": 5, "workflow_runs": [{"created_at": "2026-06-22T00:00:00Z"}]}
        if "/search/issues?" in url:
            return {"total_count": 5}
        if "/actions/workflows/" in url:
            return {"created_at": "2026-01-01T00:00:00Z"}
        raise AssertionError(f"unexpected URL: {url}")

    fetch.probed = probed
    return fetch


def run_zero_job(failed=(), startup=(), jobs=None, max_probes=audit_mod.ZERO_JOB_PROBES,
                 total_failed=None, total_startup=None):
    return audit_mod.zero_job_findings(
        "owner/repo", datetime(2026, 10, 1, tzinfo=timezone.utc), "token",
        fetch=fake_fetch_all(failed, startup, jobs, total_failed, total_startup),
        max_probes=max_probes,
    )


def test_a_default_branch_run_that_never_started_is_a_failure():
    """#2957's main-branch shape, and #3232's: the run exists, the job does not."""
    findings, stats = run_zero_job(
        failed=[run_entry(41574856776, "Provenance Gate", "main")],
        jobs={41574856776: 0},
    )
    failures = [f for f in findings if f.severity == "fail"]
    assert failures, findings
    assert failures[0].rule == "zero-job-failure"
    assert failures[0].workflow == "Provenance Gate"
    assert "0 jobs" in failures[0].detail
    assert "no log" in failures[0].detail
    assert stats == {"failed_runs": 1, "examined": 1, "zero_job": 1, "truncated": False}


def test_a_failed_run_that_did_start_is_not_flagged():
    """A red gate with a real job is a verdict on the code, not on the workflow file.

    `provenance-gate.yml` fails on pull requests that cite a source that does not resolve — a
    designed failure with one job and a log. Counting that as "never started" would make the rule
    cry wolf on exactly the gate that is working.
    """
    findings, stats = run_zero_job(
        failed=[run_entry(41171382374, "Provenance Gate", "main")],
        jobs={41171382374: 1},
    )
    assert findings == [], findings
    assert stats["zero_job"] == 0


def test_a_startup_failure_on_main_fails_without_spending_a_jobs_call():
    """GitHub already said this run never started; asking for its jobs would be redundant.

    `status=startup_failure` is a real conclusion in this repository's history (11 runs), so it is
    read exhaustively while `failure` has to be sampled.
    """
    fetch = fake_fetch_all(
        startup=[run_entry(424242, "Intake Bot Demo", "main", conclusion="startup_failure")],
    )
    findings, stats = audit_mod.zero_job_findings(
        "owner/repo", datetime(2026, 10, 1, tzinfo=timezone.utc), "token", fetch=fetch,
    )
    assert [f.severity for f in findings] == ["fail"], findings
    assert findings[0].workflow == "Intake Bot Demo"
    assert fetch.probed == [], "startup_failure runs must not be probed for jobs"
    assert stats["examined"] == 1


def test_a_zero_job_failure_on_a_feature_branch_is_a_note_not_a_failure():
    """The real 2026-10-22 run came from a branch still carrying the pre-fix file (dc0f8679).

    That is worth seeing, but it says nothing about `main` — and a rule that fails the weekly job
    for a stale branch is a rule people learn to ignore.
    """
    findings, stats = run_zero_job(
        failed=[run_entry(39804103965, ".github/workflows/provenance-gate.yml",
                          "fix/retry-action-quotes")],
        jobs={39804103965: 0},
    )
    assert [f for f in findings if f.severity == "fail"] == [], findings
    notes = [f for f in findings if f.severity == "note"]
    assert notes and notes[0].rule == "zero-job-failure"
    assert "fix/retry-action-quotes" in notes[0].detail
    assert "not a verdict on the default branch" in notes[0].detail
    assert stats["zero_job"] == 1


def test_the_path_shaped_name_is_reported_verbatim():
    """GitHub falls back to the file path when it cannot read `name:` — that fallback is the clue.

    #2957 spent a month on "`gh workflow list` reports the name as a path"; a finding that
    prettified `.github/workflows/provenance-gate.yml` into "provenance-gate" would delete the one
    piece of evidence the run gives.
    """
    findings, _ = run_zero_job(
        failed=[run_entry(1, ".github/workflows/provenance-gate.yml", "main")], jobs={1: 0},
    )
    assert findings[0].workflow == ".github/workflows/provenance-gate.yml", findings[0]


def test_the_default_branch_is_probed_before_feature_branches():
    """The sample has to spend its probes where a zero-job failure is actually a defect.

    #3232's history is mostly feature-branch runs; if those consumed the budget, the main-branch
    verdict — the only one that fails the job — would be the starved one.
    """
    failed = [run_entry(1, "Some Workflow", "fix/branch-a"),
              run_entry(2, "Some Workflow", "main")]
    findings, stats = run_zero_job(failed=failed, jobs={1: 0, 2: 0}, max_probes=1)
    assert stats["examined"] == 1
    assert [f.severity for f in findings] == ["fail"], findings
    assert "on main" in findings[0].detail


def test_the_sample_says_how_much_of_the_window_it_looked_at():
    """A sampled read is not a clean read: 12 probes of 494 failures must say so in the table."""
    failed = [run_entry(i, "Some Workflow", "main") for i in range(1, 21)]
    findings, table = audit_mod.audit(
        "owner/repo", 30, "token",
        fetch=fake_fetch_all(failed=failed, jobs={i: 1 for i in range(1, 21)}, total_failed=494),
        now=datetime(2026, 11, 3, tzinfo=timezone.utc),
    )
    assert [f for f in findings if f.severity == "fail"] == [], findings
    row = next(r for r in table if r["workflow"] == "(all workflows)")
    assert "examined 12 of 494" in row["produces"], row
    assert "sampled, not exhaustively probed" in row["produces"], row


def test_a_green_window_reports_nothing():
    findings, stats = run_zero_job()
    assert findings == []
    assert stats == {"failed_runs": 0, "examined": 0, "zero_job": 0, "truncated": False}


def test_the_rule_is_wired_into_the_audit():
    """The rule has to be in the report the weekly job prints, or nobody reads it."""
    findings, table = audit_mod.audit(
        "owner/repo", 30, "token",
        fetch=fake_fetch_all(failed=[run_entry(7, "Guarded Repository", "main")], jobs={7: 0}),
        now=datetime(2026, 11, 3, tzinfo=timezone.utc),
    )
    assert any(f.severity == "fail" and f.rule == "zero-job-failure" for f in findings), findings
    assert any(r["workflow"] == "(all workflows)" for r in table), table


def test_the_rule_uses_its_own_week_not_the_audits_month(monkeypatch):
    """A refused workflow fails on every trigger, so one week is a full sample of it.

    Measuring it over the audit's 30-day window instead fails the build for incidents fixed weeks
    earlier: the first live run on 2026-11-03 flagged two `startup_failure` runs from 2026-10-07 —
    the #3232/#2957 incident, already fixed — and would have kept failing until they aged out.
    """
    seen = {}

    def fake(repo, since, token, fetch, max_probes=audit_mod.ZERO_JOB_PROBES):
        seen["since"] = since
        return [], {"failed_runs": 0, "examined": 0, "zero_job": 0, "truncated": False}

    monkeypatch.setattr(audit_mod, "zero_job_findings", fake)
    now = datetime(2026, 11, 3, tzinfo=timezone.utc)
    audit_mod.audit("owner/repo", 30, "token", fetch=fake_fetch_all(), now=now)
    assert (now - seen["since"]).days == audit_mod.ZERO_JOB_WINDOW_DAYS
