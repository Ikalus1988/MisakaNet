"""Tests for the PR Genius rule engine (Layer 1 + Layer 2)."""

from datetime import datetime, timedelta, timezone

from scripts.pr_genius_report import analyze
from scripts.pr_genius_rules import (
    build_rule_list,
    evaluate_body_rules,
    evaluate_path_rules,
    get_enabled_rules,
)


def commit(message="feat: change\n\nSigned-off-by: Agent <agent@example.com>"):
    return {"sha": "1234567890", "commit": {"message": message}}


# ── Layer 1: Core rules ──


def test_draft_pr_detected():
    pr = {"body": "Fixes #1", "draft": True}
    files = [{"filename": "src/main.py", "additions": 10, "deletions": 0}]
    report = analyze(pr, files, [commit()])
    rules_hit = [p["rule"] for p in report["anti_patterns"]]
    assert "draft_pr" in rules_hit


def test_draft_pr_not_triggered_when_ready():
    pr = {"body": "Fixes #1", "draft": False}
    files = [{"filename": "src/main.py", "additions": 10, "deletions": 0}]
    report = analyze(pr, files, [commit()])
    rules_hit = [p["rule"] for p in report["anti_patterns"]]
    assert "draft_pr" not in rules_hit


def test_review_stale_detected_after_14_days():
    old_date = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    pr = {"body": "Fixes #1", "created_at": old_date, "reviews": []}
    files = [{"filename": "src/main.py", "additions": 10, "deletions": 0}]
    report = analyze(pr, files, [commit()])
    rules_hit = [p["rule"] for p in report["anti_patterns"]]
    assert "review_stale" in rules_hit


def test_review_stale_not_triggered_within_14_days():
    recent = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    pr = {"body": "Fixes #1", "created_at": recent, "reviews": []}
    files = [{"filename": "src/main.py", "additions": 10, "deletions": 0}]
    report = analyze(pr, files, [commit()])
    rules_hit = [p["rule"] for p in report["anti_patterns"]]
    assert "review_stale" not in rules_hit


def test_review_stale_not_triggered_when_approved():
    old_date = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    pr = {
        "body": "Fixes #1",
        "created_at": old_date,
        "reviews": [{"state": "APPROVED"}],
    }
    files = [{"filename": "src/main.py", "additions": 10, "deletions": 0}]
    report = analyze(pr, files, [commit()])
    rules_hit = [p["rule"] for p in report["anti_patterns"]]
    assert "review_stale" not in rules_hit


def test_rules_applied_count_in_report():
    pr = {"body": "Fixes #1"}
    files = [{"filename": "src/main.py", "additions": 10, "deletions": 0}]
    report = analyze(pr, files, [commit()])
    assert "rules_applied" in report
    assert report["rules_applied"]["core"] >= 6  # at least 6 core rules
    assert report["rules_applied"]["repo"] >= 0


# ── Layer 2: Path rules ──


def test_path_rule_triggered_by_matching_file():
    config = {
        "rules": {
            "path_rules": [
                {
                    "id": "db_migration",
                    "trigger": "migrations/**/*.sql",
                    "severity": "high",
                    "message": "Verify rollback script.",
                }
            ]
        }
    }
    pr = {"body": "Fixes #1"}
    files = [{"filename": "migrations/001_create.sql", "additions": 5, "deletions": 0}]
    report = analyze(pr, files, [commit()], config=config)
    rules_hit = [p["rule"] for p in report["anti_patterns"]]
    assert "db_migration" in rules_hit


def test_path_rule_not_triggered_by_non_matching_file():
    config = {
        "rules": {
            "path_rules": [
                {
                    "id": "db_migration",
                    "trigger": "migrations/**/*.sql",
                    "severity": "high",
                }
            ]
        }
    }
    pr = {"body": "Fixes #1"}
    files = [{"filename": "src/main.py", "additions": 5, "deletions": 0}]
    report = analyze(pr, files, [commit()], config=config)
    rules_hit = [p["rule"] for p in report["anti_patterns"]]
    assert "db_migration" not in rules_hit


def test_disabled_path_rule_not_triggered():
    config = {
        "rules": {
            "path_rules": [
                {
                    "id": "db_migration",
                    "trigger": "migrations/**/*.sql",
                    "enabled": False,
                }
            ]
        }
    }
    pr = {"body": "Fixes #1"}
    files = [{"filename": "migrations/001.sql", "additions": 5, "deletions": 0}]
    report = analyze(pr, files, [commit()], config=config)
    rules_hit = [p["rule"] for p in report["anti_patterns"]]
    assert "db_migration" not in rules_hit


# ── Layer 2: Custom patterns ──


def test_custom_pattern_triggered_by_body():
    config = {
        "rules": {
            "custom_patterns": [
                {
                    "id": "breaking_change",
                    "pattern": "(?i)breaking\\s+change",
                    "severity": "high",
                    "message": "Update CHANGELOG.",
                }
            ]
        }
    }
    pr = {"body": "Fixes #1\n\nThis is a BREAKING CHANGE."}
    files = [{"filename": "src/main.py", "additions": 5, "deletions": 0}]
    report = analyze(pr, files, [commit()], config=config)
    rules_hit = [p["rule"] for p in report["anti_patterns"]]
    assert "breaking_change" in rules_hit


def test_custom_pattern_triggered_by_title():
    config = {
        "rules": {
            "custom_patterns": [
                {
                    "id": "wip_check",
                    "pattern": "(?i)\\bWIP\\b",
                    "severity": "info",
                }
            ]
        }
    }
    pr = {"title": "WIP: new feature", "body": "Fixes #1"}
    files = [{"filename": "src/main.py", "additions": 5, "deletions": 0}]
    report = analyze(pr, files, [commit()], config=config)
    rules_hit = [p["rule"] for p in report["anti_patterns"]]
    assert "wip_check" in rules_hit


def test_custom_pattern_not_triggered():
    config = {
        "rules": {
            "custom_patterns": [
                {
                    "id": "breaking_change",
                    "pattern": "(?i)breaking\\s+change",
                }
            ]
        }
    }
    pr = {"body": "Fixes #1 — minor refactor"}
    files = [{"filename": "src/main.py", "additions": 5, "deletions": 0}]
    report = analyze(pr, files, [commit()], config=config)
    rules_hit = [p["rule"] for p in report["anti_patterns"]]
    assert "breaking_change" not in rules_hit


# ── Rule engine unit tests ──


def test_build_rule_list_includes_core_rules():
    rules = build_rule_list({})
    core_ids = [r["id"] for r in rules if r.get("layer") == "core"]
    assert "pr_too_large" in core_ids
    assert "missing_dco" in core_ids
    assert "draft_pr" in core_ids
    assert "review_stale" in core_ids


def test_build_rule_list_includes_repo_rules():
    config = {
        "rules": {
            "path_rules": [{"id": "custom1", "trigger": "*.sql"}],
            "custom_patterns": [{"id": "custom2", "pattern": "WIP"}],
        }
    }
    rules = build_rule_list(config)
    repo_ids = [r["id"] for r in rules if r.get("layer") == "repo"]
    assert "custom1" in repo_ids
    assert "custom2" in repo_ids


def test_get_enabled_rules_filters():
    rules = [
        {"id": "a", "enabled": True, "layer": "core"},
        {"id": "b", "enabled": False, "layer": "core"},
        {"id": "c", "enabled": True, "layer": "repo"},
    ]
    assert len(get_enabled_rules(rules)) == 2
    assert len(get_enabled_rules(rules, "core")) == 1
    assert len(get_enabled_rules(rules, "repo")) == 1


def test_evaluate_path_rules():
    rules = [
        {"id": "r1", "enabled": True, "layer": "repo", "trigger": "*.py", "severity": "medium"},
        {"id": "r2", "enabled": True, "layer": "repo", "trigger": "*.sql", "severity": "high"},
    ]
    findings = evaluate_path_rules(rules, ["main.py", "test.py"])
    assert len(findings) == 1
    assert findings[0]["rule"] == "r1"


def test_evaluate_body_rules():
    rules = [
        {
            "id": "b1", "enabled": True, "layer": "repo",
            "pattern": "(?i)breaking", "severity": "high",
        },
    ]
    findings = evaluate_body_rules(rules, "This is a breaking change", "")
    assert len(findings) == 1
    assert findings[0]["rule"] == "b1"
