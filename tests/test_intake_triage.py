"""Tests for intake triage logic (Issue #1253).

Validates the classification, priority scoring, and label assignment
logic used in the issue-intake-triage workflow.
"""
from __future__ import annotations

import pytest

_BT = "`"


def _code_block(code: str, lang: str = "") -> str:
    """Create a markdown code block."""
    return f"{_BT * 3}{lang}\n{code}\n{_BT * 3}"


# ── Priority scoring logic (mirrors workflow) ──

def compute_priority_score(
    body: str,
    title: str = "",
    source: str = "",
    is_test: bool = False,
    has_problem: bool = False,
    has_fix: bool = False,
    has_verification: bool = False,
    has_tried: bool = False,
    has_core_structure: bool = False,
) -> int:
    """Compute priority score (0-100) for an intake issue."""
    text = f"{title}\n{body}"
    score = 50  # baseline

    # Structure bonus
    if has_core_structure:
        score += 15
    if has_problem:
        score += 5
    if has_fix:
        score += 5
    if has_verification:
        score += 5
    if has_tried:
        score += 5

    # Content quality
    word_count = len(body.split())
    if word_count >= 100:
        score += 10
    elif word_count >= 50:
        score += 5

    # Code/error evidence
    if _BT * 3 in body:
        score += 5
    import re
    if re.search(r"Error:|Traceback|Exception|ENOENT|EACCES|404|500", body):
        score += 5

    # Source bonus
    if source and not is_test:
        score += 5

    # Penalties
    if is_test:
        score -= 30
    if word_count < 20:
        score -= 20
    if not has_problem and not has_fix:
        score -= 15

    return max(0, min(100, score))


def classify_issue_type(text: str) -> str:
    """Classify issue type from text content."""
    import re
    is_bug = bool(re.search(r"\b(error|crash|fail|bug|broken|exception|traceback|segfault)\b", text, re.I))
    is_feature = bool(re.search(r"\b(feature|enhancement|enhance|add|support|implement|improve|new)\b", text, re.I))
    is_question = bool(re.search(r"\b(how|why|what|question|help|docs|documentation)\b", text, re.I)) and not is_bug

    if is_bug:
        return "bug"
    elif is_feature:
        return "feature"
    elif is_question:
        return "question"
    return "unknown"


def priority_label(score: int) -> str:
    """Get priority label from score."""
    if score >= 80:
        return "priority:high"
    elif score >= 60:
        return "priority:medium"
    return "priority:low"


# ── Tests ──

class TestPriorityScoring:
    """Priority scoring tests."""

    def test_baseline_score(self):
        """Minimal body gets baseline score."""
        body = " ".join(["word"] * 25)  # 25 words to avoid short penalty
        score = compute_priority_score(body)
        assert 30 <= score <= 60

    def test_high_quality_intake(self):
        """Well-structured intake with code and errors scores high."""
        body = (
            "## Problem\n"
            "\n"
            "The MCP server crashes when handling concurrent requests with Python 3.14.\n"
            "\n"
            "## Error\n"
            "\n"
            + _code_block(
                'Traceback (most recent call last):\n'
                '  File "mcp_server.py", line 42\n'
                "    TypeError: 'str' object has no attribute 'get'"
            )
            + "\n\n"
            "## Fix\n"
            "\n"
            "Replace `get_settings().get()` with dict access.\n"
            "\n"
            "## Verification\n"
            "\n"
            "1. Run `python3 mcp_server.py`\n"
            "2. Send 10 concurrent requests\n"
            "3. Verify no crashes\n"
        )
        score = compute_priority_score(
            body,
            has_problem=True,
            has_fix=True,
            has_verification=True,
            has_core_structure=True,
        )
        assert score >= 80

    def test_low_quality_intake(self):
        """Short, unstructured intake scores low."""
        score = compute_priority_score(
            "Doesn't work",
            has_problem=False,
            has_fix=False,
        )
        assert score < 40

    def test_test_intake_penalized(self):
        """Test intakes get penalized."""
        score = compute_priority_score(
            "This is a test submission with enough words to avoid the short penalty.",
            is_test=True,
        )
        assert score < 50

    def test_code_block_bonus(self):
        """Code blocks add to score."""
        score_with = compute_priority_score(
            "Some text\n" + _code_block("print('hi')", "python")
        )
        score_without = compute_priority_score("Some text without code")
        assert score_with >= score_without

    def test_error_pattern_bonus(self):
        """Error patterns add to score."""
        body = "Error: FileNotFoundError: /tmp/test.db " + " ".join(["word"] * 50)
        score_with = compute_priority_score(body)
        score_without = compute_priority_score(" ".join(["word"] * 50))
        assert score_with > score_without

    def test_source_bonus(self):
        """Source metadata adds to score."""
        body = " ".join(["word"] * 50)
        score_with = compute_priority_score(body, source="mcp-v2.18")
        score_without = compute_priority_score(body)
        assert score_with > score_without

    def test_word_count_bonus(self):
        """Longer content gets bonus."""
        short = compute_priority_score("Short text")
        long_text = " ".join(["word"] * 120)
        long_score = compute_priority_score(long_text)
        assert long_score > short

    def test_score_clamped(self):
        """Score is clamped to 0-100."""
        # Very low
        score = compute_priority_score("", is_test=True)
        assert score >= 0

        # Very high
        body = (
            " ".join(["word"] * 200)
            + "\n"
            + _code_block("code", "python")
            + "\nError: test\nTraceback"
        )
        score = compute_priority_score(
            body,
            has_problem=True,
            has_fix=True,
            has_verification=True,
            has_tried=True,
            has_core_structure=True,
            source="mcp",
        )
        assert score <= 100


class TestIssueTypeClassification:
    """Issue type classification tests."""

    def test_bug_detection(self):
        """Detects bug reports."""
        assert classify_issue_type("Server crashes with error") == "bug"
        assert classify_issue_type("Traceback in mcp_server.py") == "bug"
        assert classify_issue_type("Exception when loading") == "bug"

    def test_feature_detection(self):
        """Detects feature requests."""
        assert classify_issue_type("Add support for SSE transport") == "feature"
        assert classify_issue_type("Implement new search algorithm") == "feature"
        assert classify_issue_type("New feature for intake validation") == "feature"

    def test_question_detection(self):
        """Detects questions."""
        assert classify_issue_type("How to configure the proxy?") == "question"
        assert classify_issue_type("What is the best practice for") == "question"

    def test_bug_takes_precedence(self):
        """Bug detection takes precedence over question."""
        assert classify_issue_type("How to fix this error?") == "bug"

    def test_unknown_type(self):
        """Ambiguous text returns unknown."""
        assert classify_issue_type("Hello world") == "unknown"


class TestPriorityLabel:
    """Priority label tests."""

    def test_high_priority(self):
        assert priority_label(80) == "priority:high"
        assert priority_label(100) == "priority:high"

    def test_medium_priority(self):
        assert priority_label(60) == "priority:medium"
        assert priority_label(79) == "priority:medium"

    def test_low_priority(self):
        assert priority_label(0) == "priority:low"
        assert priority_label(59) == "priority:low"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
