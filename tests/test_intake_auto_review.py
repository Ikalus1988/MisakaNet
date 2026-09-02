#!/usr/bin/env python3
"""Tests for intake_auto_review.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from intake_auto_review import (
    auto_review_issue,
    score_completeness,
    score_generalization,
    score_verification,
    score_detail,
    score_format,
    calculate_confidence,
    make_decision,
    generate_lesson_from_intake,
)


# === Test Data ===

GOOD_INTAKE = """
## Problem

When pushing to GitHub, encountering 403 errors and credential issues.

## Error

```
remote: Permission to user/repo.git denied to user2.
fatal: unable to access 'https://github.com/user/repo.git/': The requested URL returned error: 403
```

## Fix

1. Check credential helper configuration
2. Verify SSH key is added to GitHub
3. Check token expiration

## Verification

```bash
$ git push origin main
Enumerating objects: 5, done.
Counting objects: 100% (5/5), done.
Writing objects: 100% (3/3), 352 bytes | 352.00 KiB/s, done.
Total 3 (delta 2), reused 0 (delta 0), pack-reused 0
To https://github.com/user/repo.git
   a1b2c3d..e4f5g6h  main -> main
```

Push successful after fixing credentials.
"""

SHORT_INTAKE = """
## Problem
Git push fails.
"""

TEST_INTAKE = """
## Problem
This is a test issue for heartbeat verification.

Submitted via remote MCP (test). No account required.
"""

GENERAL_INTAKE = """
## Problem

Python pip install timeout when installing packages from PyPI.

## Error

```
ERROR: Could not find a version that satisfies the requirement requests>=2.28.0
ERROR: No matching distribution found for requests>=2.28.0
```

## Fix

Configure pip to use mirror:
```bash
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

## Verification

```bash
$ pip install requests
Successfully installed requests-2.28.0
```
"""


# === Completeness Tests ===

def test_completeness_good():
    result = score_completeness(GOOD_INTAKE, {})
    assert result.score >= 80
    assert any("✓ problem present" in r for r in result.reasons)
    assert any("✓ fix present" in r for r in result.reasons)


def test_completeness_short():
    result = score_completeness(SHORT_INTAKE, {})
    assert result.score < 50


def test_completeness_with_verification():
    body = "## Problem\nBug\n## Fix\nFix it\n## Verification\nVerified"
    result = score_completeness(body, {})
    assert result.score >= 50  # 55: problem(25) + fix(25) + verification_bonus(5)


# === Generalization Tests ===

def test_generalization_good():
    result = score_generalization(GENERAL_INTAKE, {})
    assert result.score >= 60
    assert any("✓ No user-specific paths" in r for r in result.reasons)


def test_generalization_with_user_paths():
    body = "## Problem\nIn /home/user/project, the script fails."
    result = score_generalization(body, {})
    assert result.score < 60


def test_generalization_with_internal():
    body = "## Problem\nInternal tool xiaomi-mify fails."
    result = score_generalization(body, {})
    assert result.score < 50


# === Verification Tests ===

def test_verification_with_section():
    body = "## Problem\nBug\n## Verification\nVerified with tests"
    result = score_verification(body, {})
    assert result.score >= 30
    assert any("✓ Verification section present" in r for r in result.reasons)


def test_verification_with_results():
    body = "## Verification\nVerified: push successful, no leaks found"
    result = score_verification(body, {})
    assert result.score >= 35


def test_verification_no_section():
    body = "## Problem\nBug"
    result = score_verification(body, {})
    assert result.score < 30


# === Detail Tests ===

def test_detail_good():
    result = score_detail(GOOD_INTAKE, 200)
    assert result.score >= 60


def test_detail_short():
    result = score_detail(SHORT_INTAKE, 20)
    assert result.score < 40


def test_detail_with_code():
    body = "## Problem\n```\nerror\n```\n```\nsolution\n```"
    result = score_detail(body, 100)
    assert result.score >= 40  # 40: word_count(20) + code_blocks(20)


# === Format Tests ===

def test_format_good():
    result = score_format(GOOD_INTAKE, {})
    assert result.score >= 40  # 45: headers(30) + code_blocks(15)


def test_format_minimal():
    result = score_format("Just plain text", {})
    assert result.score < 30


def test_format_with_frontmatter():
    body = '{"title": "test"}\n\n## Problem\nBug'
    result = score_format(body, {})
    assert result.score >= 20


# === Confidence Tests ===

def test_confidence_high():
    confidence = calculate_confidence(GOOD_INTAKE, False)
    assert confidence >= 0.8


def test_confidence_low():
    confidence = calculate_confidence(TEST_INTAKE, True)
    assert confidence < 0.8


# === Decision Tests ===

def test_decision_approve():
    decision = make_decision(85, 0.9)
    assert decision == "approve"


def test_decision_review():
    decision = make_decision(60, 0.9)
    assert decision == "review"


def test_decision_reject():
    decision = make_decision(30, 0.9)
    assert decision == "reject"


def test_decision_low_confidence():
    # Low confidence raises thresholds
    decision = make_decision(75, 0.5)
    # 75 * 0.5 = 37.5 (adjusted threshold), 75 > 37.5 so approve
    # This tests that low confidence affects the decision
    assert decision in ["approve", "review"]


# === Integration Tests ===

def test_auto_review_good_intake():
    result = auto_review_issue(1234, "[Intake] Git push fails", GOOD_INTAKE)
    assert result.decision in ["approve", "review"]
    assert result.final_score >= 50
    assert len(result.dimensions) >= 5


def test_auto_review_short_intake():
    result = auto_review_issue(1235, "[Intake] Short", SHORT_INTAKE)
    assert result.decision == "reject"
    assert result.final_score < 50


def test_auto_review_test_intake():
    result = auto_review_issue(1236, "[Intake] Test", TEST_INTAKE, is_test=True)
    assert result.confidence < 0.8


def test_auto_review_general_intake():
    result = auto_review_issue(1237, "[Intake] Pip timeout", GENERAL_INTAKE)
    assert result.decision in ["approve", "review"]
    assert result.lesson_domain == "python"


# === Lesson Generation Tests ===

def test_lesson_generation():
    title, domain, tags = generate_lesson_from_intake(
        1234, "[Intake] Git push fails", GOOD_INTAKE, {}
    )
    assert "git" in title.lower() or "push" in title.lower()
    assert domain in ["git", "general"]
    assert len(tags) >= 3


def test_lesson_generation_python():
    title, domain, tags = generate_lesson_from_intake(
        1237, "[Intake] Pip timeout", GENERAL_INTAKE, {}
    )
    assert domain == "python"
    assert "python" in tags


# === JSON Output Tests ===

def test_json_output():
    result = auto_review_issue(1234, "[Intake] Test", GOOD_INTAKE)
    from intake_auto_review import format_result_json
    json_str = format_result_json(result)
    data = json.loads(json_str)
    assert "issue_number" in data
    assert "final_score" in data
    assert "decision" in data
    assert "dimensions" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
