#!/usr/bin/env python3
"""Test PR Genius config loading and pattern enable/disable."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.pr_genius_report import analyze, load_config


def test_load_config_returns_defaults_when_no_file(tmp_path, monkeypatch):
    """Without .pr-genius.yaml, returns defaults."""
    monkeypatch.setattr("scripts.pr_genius_report.CONFIG_FILE", tmp_path / "missing.yaml")
    config = load_config()
    assert "rules" in config
    assert "patterns" in config["rules"]
    assert config["rules"]["pr_size"]["max_lines"] == 500


def test_load_config_reads_yaml(tmp_path, monkeypatch):
    """Reads .pr-genius.yaml and merges with defaults."""
    cfg_file = tmp_path / ".pr-genius.yaml"
    cfg_file.write_text(
        "rules:\n"
        "  pr_size:\n"
        "    max_lines: 300\n"
        "  patterns:\n"
        "    missing_tests:\n"
        "      enabled: false\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("scripts.pr_genius_report.CONFIG_FILE", cfg_file)
    config = load_config()
    assert config["rules"]["pr_size"]["max_lines"] == 300
    assert config["rules"]["patterns"]["missing_tests"]["enabled"] is False
    # Other defaults preserved
    assert config["rules"]["patterns"]["pr_too_large"]["enabled"] is True


def test_disabled_pattern_not_detected():
    """Disabled patterns should not appear in analysis."""
    pr = {"body": "no issue ref"}
    files = [{"filename": "src/app.py", "additions": 10, "deletions": 0}]
    commits = [{"sha": "abc1234", "commit": {"message": "feat: test"}}]

    config = {
        "rules": {
            "issue_link": {"patterns": [], "required": True},
            "pr_size": {"max_lines": 500, "warning_lines": 300},
            "patterns": {
                "missing_tests": {"enabled": False, "severity": "medium"},
                "no_issue_reference": {"enabled": False, "severity": "low"},
                "missing_dco": {"enabled": False, "severity": "medium"},
                "pr_too_large": {"enabled": True, "severity": "high"},
                "doc_code_mismatch": {"enabled": True, "severity": "low"},
                "mixed_concerns": {"enabled": True, "severity": "medium"},
            },
        }
    }
    report = analyze(pr, files, commits, config=config)
    rule_ids = [p["rule"] for p in report["anti_patterns"]]
    assert "missing_tests" not in rule_ids
    assert "no_issue_reference" not in rule_ids
    assert "missing_dco" not in rule_ids


def test_custom_severity_applied():
    """Custom severity from config is used."""
    pr = {"body": "no issue ref"}
    files = [{"filename": "src/app.py", "additions": 10, "deletions": 0}]
    commits = [{"sha": "abc1234", "commit": {"message": "feat: test\n\nSigned-off-by: a <b@c>"}}]

    config = {
        "rules": {
            "issue_link": {"patterns": [], "required": True},
            "pr_size": {"max_lines": 500, "warning_lines": 300},
            "patterns": {
                "missing_tests": {"enabled": True, "severity": "critical"},
                "no_issue_reference": {"enabled": True, "severity": "high"},
                "missing_dco": {"enabled": True, "severity": "medium"},
                "pr_too_large": {"enabled": True, "severity": "high"},
                "doc_code_mismatch": {"enabled": True, "severity": "low"},
                "mixed_concerns": {"enabled": True, "severity": "medium"},
            },
        }
    }
    report = analyze(pr, files, commits, config=config)
    rules = {p["rule"]: p["severity"] for p in report["anti_patterns"]}
    assert rules.get("missing_tests") == "critical"
    assert rules.get("no_issue_reference") == "high"


def test_custom_pr_size_threshold():
    """Custom max_lines threshold is respected."""
    pr = {"body": "Fixes #1"}
    # 400 lines — over default 300 warning but under 500 max
    files = [{"filename": "src/app.py", "additions": 400, "deletions": 0}]
    commits = [{"sha": "abc1234", "commit": {"message": "feat: test\n\nSigned-off-by: a <b@c>"}}]

    config = {
        "rules": {
            "issue_link": {"patterns": [], "required": True},
            "pr_size": {"max_lines": 350, "warning_lines": 200},
            "patterns": {
                "pr_too_large": {"enabled": True, "severity": "high"},
                "missing_tests": {"enabled": True, "severity": "medium"},
                "no_issue_reference": {"enabled": True, "severity": "low"},
                "missing_dco": {"enabled": True, "severity": "medium"},
                "doc_code_mismatch": {"enabled": True, "severity": "low"},
                "mixed_concerns": {"enabled": True, "severity": "medium"},
            },
        }
    }
    report = analyze(pr, files, commits, config=config)
    rule_ids = [p["rule"] for p in report["anti_patterns"]]
    assert "pr_too_large" in rule_ids  # 400 > 350
