#!/usr/bin/env python3
"""Tests for scripts/lesson_pr_mergeable.py — offline, no network, no git.

The whole point of keeping the decision in a pure function is that every rule can be
pinned here: the workflow around it holds a write token, so a rule that is only tested by
"we ran it once on a real PR" is a rule nobody has actually verified.

Each rule is exercised twice: once against `decide()` directly, and — for the three
verdicts — through the CLI the workflow actually calls (`--json`), including the exit code,
because the workflow branches on the exit code and not on the printed text.
"""
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "lesson_pr_mergeable.py"
sys.path.insert(0, str(ROOT / "scripts"))

import lesson_pr_mergeable as lpm  # noqa: E402

GREEN_CHECKS = {
    "gate": "success",
    "provenance": "success",
    "dco": "success",
    "audit-shape": "success",
    "test (ubuntu-latest, 3.11)": "success",
    "test (ubuntu-latest, 3.12)": "success",
    "test (windows-latest, 3.13)": "success",
}


def payload(**overrides) -> dict:
    """A payload that must merge, so every test only has to state what it breaks."""
    base = {
        "files": ["lessons/contrib/silent-write-loss.md"],
        "file_stats": {"lessons/contrib/silent-write-loss.md": [58, 0]},
        "checks": dict(GREEN_CHECKS),
        "labels": ["auto-merge-lesson"],
        "draft": False,
        "review_state": "APPROVED",
        "body": "Adds one lesson.\n\n- [x] gate is green\n",
    }
    base.update(overrides)
    return base


def run_cli(payload_obj, *extra) -> subprocess.CompletedProcess:
    """Invoke the script exactly the way the workflow does."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--json", json.dumps(payload_obj), *extra],
        capture_output=True,
        text=True,
        check=False,
    )


def verdict_of(payload_obj) -> tuple[str, str]:
    return lpm.decide(**{k: v for k, v in payload_obj.items()})


# ── the happy path ───────────────────────────────────────────────────────────
def test_all_green_lessons_only_merges():
    verdict, reason = verdict_of(payload())
    assert verdict == lpm.MERGE
    assert "lessons-only" in reason


def test_a_lesson_in_a_subdirectory_is_inside_scope():
    verdict, _ = verdict_of(
        payload(
            files=["lessons/python/pip-install-proxy-timeout.md"],
            file_stats={"lessons/python/pip-install-proxy-timeout.md": [80, 3]},
        )
    )
    assert verdict == lpm.MERGE


def test_cli_prints_merge_and_exits_zero():
    proc = run_cli(payload())
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().startswith("merge: ")


# ── refusals ─────────────────────────────────────────────────────────────────
def test_a_failed_provenance_check_refuses():
    checks = dict(GREEN_CHECKS, provenance="failure")
    verdict, reason = verdict_of(payload(checks=checks))
    assert verdict == lpm.REFUSE
    assert "provenance" in reason


def test_cli_reports_a_failed_check_and_exits_one():
    proc = run_cli(payload(checks=dict(GREEN_CHECKS, provenance="failure")))
    assert proc.returncode == 1
    assert proc.stdout.strip().startswith("refuse: ")
    assert "provenance" in proc.stdout


def test_a_change_outside_lessons_refuses():
    verdict, reason = verdict_of(
        payload(
            files=["lessons/contrib/foo.md", "scripts/fix_gate.py"],
            file_stats={
                "lessons/contrib/foo.md": [10, 0],
                "scripts/fix_gate.py": [4, 1],
            },
        )
    )
    assert verdict == lpm.REFUSE
    assert "scripts/fix_gate.py" in reason


def test_a_path_that_merely_starts_with_lessons_is_outside_scope():
    verdict, reason = verdict_of(payload(files=["lessons-archive/foo.md"]))
    assert verdict == lpm.REFUSE
    assert "outside" in reason


def test_a_workflow_change_refuses_even_though_it_is_text():
    verdict, reason = verdict_of(payload(files=[".github/workflows/auto-merge-lessons.yml"]))
    assert verdict == lpm.REFUSE
    assert "outside" in reason


def test_unaddressed_changes_requested_refuses():
    verdict, reason = verdict_of(payload(review_state="CHANGES_REQUESTED"))
    assert verdict == lpm.REFUSE
    assert "CHANGES_REQUESTED" in reason


def test_a_commented_or_dismissed_review_does_not_block():
    for state in ("APPROVED", "COMMENTED", "DISMISSED", "NONE", ""):
        verdict, _ = verdict_of(payload(review_state=state))
        assert verdict == lpm.MERGE, state


def test_lessons_index_with_five_deletions_refuses():
    verdict, reason = verdict_of(
        payload(
            files=["lessons/contrib/foo.md", "lessons/index.md"],
            file_stats={
                "lessons/contrib/foo.md": [10, 0],
                "lessons/index.md": [3, 5],
            },
        )
    )
    assert verdict == lpm.REFUSE
    assert "index.md" in reason


def test_lessons_index_with_two_additions_refuses():
    verdict, reason = verdict_of(
        payload(
            files=["lessons/index.md"],
            file_stats={"lessons/index.md": [2, 0]},
        )
    )
    assert verdict == lpm.REFUSE
    assert "one-line addition" in reason


def test_lessons_index_with_one_addition_is_allowed():
    verdict, _ = verdict_of(
        payload(files=["lessons/index.md"], file_stats={"lessons/index.md": [1, 0]})
    )
    assert verdict == lpm.MERGE


def test_the_do_not_merge_label_refuses():
    verdict, reason = verdict_of(payload(labels=["auto-merge-lesson", "do-not-merge"]))
    assert verdict == lpm.REFUSE
    assert "do-not-merge" in reason


def test_the_wip_label_refuses():
    verdict, reason = verdict_of(payload(labels=["auto-merge-lesson", "wip"]))
    assert verdict == lpm.REFUSE
    assert "wip" in reason


def test_a_draft_refuses():
    verdict, reason = verdict_of(payload(draft=True))
    assert verdict == lpm.REFUSE
    assert "draft" in reason


def test_cli_refuses_a_draft_and_exits_one():
    proc = run_cli(payload(draft=True))
    assert proc.returncode == 1
    assert "draft" in proc.stdout


# ── waits ────────────────────────────────────────────────────────────────────
def test_a_check_still_running_waits():
    verdict, reason = verdict_of(payload(checks=dict(GREEN_CHECKS, provenance="in_progress")))
    assert verdict == lpm.WAIT
    assert "provenance" in reason


def test_a_check_queued_waits():
    verdict, _ = verdict_of(payload(checks=dict(GREEN_CHECKS, gate="queued")))
    assert verdict == lpm.WAIT


def test_a_required_check_that_never_reported_waits():
    checks = dict(GREEN_CHECKS)
    del checks["audit-shape"]
    verdict, reason = verdict_of(payload(checks=checks))
    assert verdict == lpm.WAIT
    assert "audit-shape" in reason


def test_a_required_check_that_is_absent_waits_but_not_a_matrix_leg_that_never_ran():
    """The four fixed names must *exist* to merge; the `test (...)` legs cannot.

    The matrix legs are discovered from the checks that reported, because the number of
    legs lives in the cross-platform workflow (9 cells minus an exclusion) and not in any
    payload: a leg that never ran is invisible here. That is a real hole, so it is pinned
    by a test rather than left implicit — see docs/maintainer/auto-merge-lessons.md.
    """
    checks = dict(GREEN_CHECKS)
    del checks["dco"]
    verdict, reason = verdict_of(payload(checks=checks))
    assert verdict == lpm.WAIT
    assert "dco" in reason

    checks = dict(GREEN_CHECKS)
    del checks["test (windows-latest, 3.13)"]
    assert verdict_of(payload(checks=checks))[0] == lpm.MERGE


def test_a_matrix_test_leg_that_failed_refuses():
    checks = dict(GREEN_CHECKS, **{"test (macos-latest, 3.12)": "failure"})
    verdict, reason = verdict_of(payload(checks=checks))
    assert verdict == lpm.REFUSE
    assert "test (macos-latest, 3.12)" in reason


def test_a_missing_opt_in_label_waits():
    verdict, reason = verdict_of(payload(labels=["area:lessons", "ready"]))
    assert verdict == lpm.WAIT
    assert "auto-merge-lesson" in reason


def test_cli_waits_on_a_missing_label_and_exits_two():
    proc = run_cli(payload(labels=[]))
    assert proc.returncode == 2
    assert proc.stdout.strip().startswith("wait: ")


def test_no_changed_files_waits_rather_than_merging_a_vacuous_diff():
    verdict, _ = verdict_of(payload(files=[], file_stats={}))
    assert verdict == lpm.WAIT


def test_index_md_without_stats_waits_instead_of_guessing():
    verdict, reason = verdict_of(
        payload(files=["lessons/index.md"], file_stats={})
    )
    assert verdict == lpm.WAIT
    assert "index.md" in reason


# ── the interface the workflow depends on ────────────────────────────────────
@pytest.mark.parametrize(
    "override, expected_code",
    [
        ({}, 0),
        ({"review_state": "CHANGES_REQUESTED"}, 1),
        ({"checks": dict(GREEN_CHECKS, dco="failure")}, 1),
        ({"labels": ["auto-merge-lesson"], "checks": dict(GREEN_CHECKS, dco="queued")}, 2),
    ],
)
def test_cli_exit_codes_are_the_workflow_contract(override, expected_code):
    proc = run_cli(payload(**override))
    assert proc.returncode == expected_code, proc.stdout + proc.stderr
    assert proc.stdout.split(":", 1)[0] in lpm.EXIT_CODES


def test_cli_reads_the_payload_from_stdin_when_json_is_a_dash():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--json", "-"],
        input=json.dumps(payload()),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.startswith("merge: ")


def test_a_broken_payload_exits_three_and_never_looks_like_a_refusal():
    proc = run_cli("{not json")
    assert proc.returncode == 3
    assert "refuse" not in proc.stdout


def test_the_body_is_accepted_and_changes_nothing():
    for body in ("", "- [ ] unchecked box", "<!-- no auto merge -->"):
        verdict, _ = verdict_of(payload(body=body))
        assert verdict == lpm.MERGE, body


def test_decide_tolerates_a_json_file_stats_pair_as_a_list():
    # JSON has no tuples: the workflow sends [additions, deletions].
    verdict, _ = verdict_of(
        payload(files=["lessons/index.md"], file_stats={"lessons/index.md": [1, 0]})
    )
    assert verdict == lpm.MERGE


def test_checks_not_required_by_name_are_ignored():
    checks = dict(GREEN_CHECKS, **{"lint": "failure", "pr-agent": "failure"})
    verdict, _ = verdict_of(payload(checks=checks))
    assert verdict == lpm.MERGE


def test_labels_are_matched_case_insensitively():
    verdict, _ = verdict_of(payload(labels=["Auto-Merge-Lesson"]))
    assert verdict == lpm.MERGE


# ── the pre-merge re-check's normalisation ──────────────────────────────────
# The workflow re-reads `mergeable` from REST right before merging and normalises it with
# this helper. It used to compare the raw value to "MERGEABLE" — the *GraphQL* spelling —
# so on 2026-09-17 the very first real run decided "merge", then refused itself with
# "no longer a clean candidate (mergeable=true …)" and the channel merged nothing.
def test_rest_boolean_true_is_clean():
    assert lpm.mergeable_is_clean(True) is True


def test_graphql_enum_string_is_also_clean():
    # Zero cost to accept it, and it keeps a future GraphQL read working.
    assert lpm.mergeable_is_clean("MERGEABLE") is True
    assert lpm.mergeable_is_clean("mergeable") is True


def test_lazy_null_is_not_clean_and_must_be_retried():
    assert lpm.mergeable_is_clean(None) is False
    assert lpm.mergeable_is_clean("null") is False


def test_conflicting_and_unknown_are_not_clean():
    for value in (False, "CONFLICTING", "UNKNOWN", "", "true", "yes"):
        assert lpm.mergeable_is_clean(value) is False, value


def test_the_workflow_does_not_compare_mergeable_to_the_graphql_spelling():
    """Pin the shipped shell: the re-check must not gate on the raw API spelling again."""
    workflow = (
        pathlib.Path(__file__).resolve().parent.parent
        / ".github"
        / "workflows"
        / "auto-merge-lessons.yml"
    ).read_text(encoding="utf-8")
    assert 'if [ "$MERGEABLE" != "MERGEABLE" ]' not in workflow, (
        "the pre-merge re-check compares `mergeable` to the GraphQL enum while reading the "
        "REST endpoint — that refuses every candidate; normalise with mergeable_is_clean"
    )
    assert "mergeable_is_clean" in workflow
