from scripts.pr_genius_report import analyze, render


def commit(message="feat: change\n\nSigned-off-by: Agent <agent@example.com>"):
    return {"sha": "1234567890", "commit": {"message": message}}


def test_medium_pr_report_has_size_impact_and_passing_checklist():
    pr = {"body": "Fixes #951"}
    files = [
        {"filename": "scripts/bench.py", "additions": 250, "deletions": 50},
        {"filename": "tests/test_bench.py", "additions": 100, "deletions": 54},
    ]

    report = analyze(
        pr,
        files,
        [commit()],
        [{"name": "unit tests", "status": "completed", "conclusion": "success"}],
    )

    assert report["size"] == {
        "additions": 350,
        "deletions": 104,
        "total": 454,
        "label": "medium",
    }
    assert report["impact"] == {
        "files_changed": 2,
        "components": ["scripts", "tests"],
    }
    assert report["anti_patterns"] == []
    output = render(report, "low_risk")
    assert "PR Size:** +350/-104 (454 lines, medium)" in output
    assert "ci_passing (PASS)" in output
    assert "dco_signoff (PASS)" in output
    assert "Anti-Patterns Detected\n- None detected" in output


def test_detects_large_untested_unsigned_code_without_issue():
    report = analyze(
        {"body": "Adds a feature"},
        [{"filename": "misakanet/feature.py", "additions": 501, "deletions": 1}],
        [commit("feat: unsigned")],
    )

    detected = {item["rule"] for item in report["anti_patterns"]}
    assert detected == {"pr_too_large", "missing_tests", "no_issue_reference", "missing_dco"}
    statuses = {item["name"]: item["status"] for item in report["checklist"]}
    assert statuses == {
        "ci_passing": "UNKNOWN",
        "dco_signoff": "FAIL",
        "tests_updated": "FAIL",
        "issue_reference": "FAIL",
    }


def test_ci_checklist_reports_failures_and_ignores_current_job():
    report = analyze(
        {"body": "Fixes #1"},
        [],
        [commit()],
        [
            {"name": "PR Genius Check", "status": "in_progress", "conclusion": None},
            {"name": "tests", "status": "completed", "conclusion": "failure"},
        ],
    )
    assert report["checklist"][0] == {
        "name": "ci_passing",
        "status": "FAIL",
        "detail": "one or more checks failed",
    }


def test_detects_documentation_only_and_mixed_concerns():
    docs = analyze(
        {"body": "Closes #7"},
        [{"filename": "docs/guide.md", "additions": 5, "deletions": 0}],
        [commit()],
    )
    assert [item["rule"] for item in docs["anti_patterns"]] == ["doc_code_mismatch"]

    mixed = analyze(
        {"body": "Resolves owner/repo#8"},
        [
            {"filename": "src/app.py", "additions": 10, "deletions": 0},
            {"filename": "tests/test_app.py", "additions": 10, "deletions": 0},
            {"filename": "docs/app.md", "additions": 10, "deletions": 0},
        ],
        [commit()],
    )
    assert [item["rule"] for item in mixed["anti_patterns"]] == ["mixed_concerns"]


# ── delivery (added 2026-09-17: the publish path had zero coverage) ───────────────────
#
# The analysis worked on every run; posting it did not. `pr-genius-check.yml` granted
# `pull-requests: read` while commenting on a pull request needs `pull-requests: write`, so the
# comment request answered `HTTP Error 403: Forbidden` — visible in 11 of 11 job logs, invisible
# to everyone else, because the failure was written to stderr only and the check stayed green.
# PR-Genius therefore shipped zero visible output for months and nothing noticed.
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "pr-genius-check.yml"


def test_delivery_failure_is_reported_in_three_places(capsys, tmp_path):
    """A failed comment must be loud: stderr, an annotation, and the job summary."""
    from scripts.pr_genius_report import report_delivery_failure

    summary = tmp_path / "summary.md"
    summary.write_text("## PR Genius Analysis\n", encoding="utf-8")

    message = report_delivery_failure(
        Exception("HTTP Error 403: Forbidden"), str(summary))

    assert "403" in message
    captured = capsys.readouterr()
    assert "::warning" in captured.out, "an annotation is what makes it visible on the run page"
    assert "pull-requests: write" in captured.out, "name the permission that fixes it"
    assert "not delivered" in captured.err
    assert "never posted" in summary.read_text(encoding="utf-8")


def test_delivery_failure_survives_a_missing_summary_file(capsys, tmp_path):
    """A failure to report the failure must not become the new crash."""
    from scripts.pr_genius_report import report_delivery_failure

    # `tmp_path/missing/s.md` rather than "/nonexistent/dir/s.md": on Windows a POSIX-rooted path is
    # drive-relative, and whether the append fails then depends on whether some *other* test had
    # already created that directory at the drive root (tests/test_demand_board_gaps.py used to).
    message = report_delivery_failure(
        Exception("HTTP Error 403: Forbidden"), str(tmp_path / "missing" / "s.md"))
    assert "403" in message
    capsys.readouterr()


def test_the_workflow_grants_pull_requests_write():
    """Pin the shipped permission: commenting on a PR needs `pull-requests: write`."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r"^\s*pull-requests:\s*write\s*$", workflow, re.MULTILINE), (
        "pr-genius-check.yml must grant `pull-requests: write`; with `read`, the comment request "
        "returns 403 and the tool produces nothing visible (11/11 job logs, run 35205310232)")


def test_the_report_step_still_reads_the_token_from_the_environment():
    """The posting step passes GITHUB_TOKEN; the script must keep using it, not a literal."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "GITHUB_TOKEN: ${{ github.token }}" in workflow


def test_a_degraded_rule_set_is_reported_not_silent(capsys, tmp_path):
    """Without PyYAML the fallback parser loses every list, and that used to be invisible.

    pr-genius-check.yml installs PyYAML before running, so this is the *guard*: if that stops
    being true, the run says which rules it lost instead of quietly analysing with fewer of them.
    """
    from scripts.pr_genius_report import report_degraded_config

    summary = tmp_path / "summary.md"
    summary.write_text("", encoding="utf-8")

    lost = report_degraded_config({"rules": {"path_rules": [], "custom_patterns": []}})

    assert "rules.path_rules" in lost and "rules.issue_link.patterns" in lost
    captured = capsys.readouterr()
    assert "::warning" in captured.err and "degraded" in captured.err


def test_a_healthy_config_reports_no_degradation():
    from scripts.pr_genius_report import report_degraded_config

    lost = report_degraded_config({
        "rules": {"path_rules": [{"path": "x", "note": "y"}], "custom_patterns": [{"pattern": "z"}]},
        "issue_link": {"patterns": ["Fixes #"]},
    })
    assert [] == lost
