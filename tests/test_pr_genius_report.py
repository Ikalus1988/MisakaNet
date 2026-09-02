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
