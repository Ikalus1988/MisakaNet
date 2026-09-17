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
                    return {"total_count": count}
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
    notes = [f for f in findings if f.severity == "note"]
    assert notes and notes[0].rule == "never-ran" and "grace" in notes[0].detail, findings


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
        capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"},
    )
    assert exit_code.returncode == 2
    assert "GITHUB_TOKEN" in exit_code.stderr


def test_the_manifest_probes_are_scoped_to_the_repo_at_call_time():
    """Guards against a probe that would silently read another repository's artifacts."""
    query = audit_mod.AUTOMATIONS[0].probe
    assert query.startswith("in:comments") or query.startswith("is:"), query
    assert "repo:" not in query, "the repo is added by output_count(); a literal here would double it"
