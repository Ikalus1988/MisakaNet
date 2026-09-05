"""Unit tests for scripts/sync_answered_questions.py.

Covers:
  - fnv1a_hex parity with JS worker hashString
  - parse_kind_and_problem (kind/problem/error extraction, fallback)
  - extract_answer (marker priority, fallback, rejection of automated markers)
  - ANSWER_MARKERS / AUTOMATED_MARKERS coverage
"""
from __future__ import annotations

import pytest

from scripts.sync_answered_questions import (
    ANSWER_MARKERS,
    AUTOMATED_MARKERS,
    extract_answer,
    fnv1a_hex,
    parse_kind_and_problem,
)


# ── fnv1a_hex ────────────────────────────────────────────────────────────


class TestFnv1aHex:
    """Verify Python impl matches JS worker hashString (FNV-1a 32-bit, hex8)."""

    @pytest.mark.parametrize("input_str, expected", [
        ("", "811c9dc5"),
        ("a", "e40c292c"),
        ("test", "afd071e5"),
        ("hello world", "d58b3fa7"),
        # Real dedupSource-like strings
        ("question:how to fix:Error 500", None),  # length-agnostic smoke
        ("bug:login fails:timeout", None),
    ])
    def test_basic_known_hashes(self, input_str, expected):
        result = fnv1a_hex(input_str)
        assert len(result) == 8
        assert result == result.lower()
        assert all(c in "0123456789abcdef" for c in result)
        if expected is not None:
            assert result == expected

    def test_parity_with_js_hash_known_values(self):
        """These are hand-verified from JS: hashString(''), hashString('a'), etc."""
        assert fnv1a_hex("") == "811c9dc5"
        assert fnv1a_hex("a") == "e40c292c"
        assert fnv1a_hex("test") == "afd071e5"

    def test_deterministic(self):
        s = "question:How do I configure?|:Connection refused"
        assert fnv1a_hex(s) == fnv1a_hex(s)

    def test_different_inputs_different_hashes(self):
        assert fnv1a_hex("question:a:b") != fnv1a_hex("bug:a:b")
        assert fnv1a_hex("question:a:b") != fnv1a_hex("question:a:c")

    def test_unicode(self):
        result = fnv1a_hex("question:如何配置:错误")
        assert len(result) == 8


# ── parse_kind_and_problem ────────────────────────────────────────────────


BODY_QUESTION = """**Kind:** question

## Problem
How do I configure the worker timeout?

## Error
Connection refused on port 8787
"""

BODY_BUG = """**Kind:** bug

## Problem
Login fails intermittently

## Error
500 Internal Server Error
"""

BODY_NO_SECTIONS = """**Kind:** question

Some free-text description of the problem without section headers.
It spans multiple lines and includes <details>hidden content</details>.
"""

BODY_EMPTY = ""
BODY_NO_KIND = """## Problem
Something is broken
"""


class TestParseKindAndProblem:

    def test_extracts_question_kind(self):
        kind, problem, error = parse_kind_and_problem(BODY_QUESTION)
        assert kind == "question"
        assert "configure the worker timeout" in problem
        assert "Connection refused" in error

    def test_extracts_bug_kind(self):
        kind, problem, error = parse_kind_and_problem(BODY_BUG)
        assert kind == "bug"
        assert "Login fails" in problem
        assert "500 Internal Server" in error

    def test_kind_case_insensitive(self):
        body = "**Kind:** Question\n## Problem\nTest"
        kind, _, _ = parse_kind_and_problem(body)
        assert kind == "question"

    def test_fallback_when_no_sections(self):
        kind, problem, error = parse_kind_and_problem(BODY_NO_SECTIONS)
        assert kind == "question"
        assert "free-text description" in problem
        assert error == ""  # No Error section

    def test_strips_details_tags_in_fallback(self):
        body = "**Kind:** question\n\n<details>hidden stuff</details>\nVisible text here"
        _, problem, _ = parse_kind_and_problem(body)
        assert "hidden stuff" not in problem
        assert "Visible text" in problem

    def test_empty_body(self):
        kind, problem, error = parse_kind_and_problem(BODY_EMPTY)
        assert kind == ""
        assert problem == ""
        assert error == ""

    def test_no_kind_header(self):
        kind, problem, _ = parse_kind_and_problem(BODY_NO_KIND)
        assert kind == ""
        assert "Something is broken" in problem

    def test_truncation_at_2000_chars(self):
        long_problem = "x" * 5000
        body = f"**Kind:** question\n## Problem\n{long_problem}"
        _, problem, _ = parse_kind_and_problem(body)
        assert len(problem) <= 2000

    def test_error_truncation_at_1000(self):
        long_error = "e" * 3000
        body = f"**Kind:** question\n## Problem\nP\n## Error\n{long_error}"
        _, _, error = parse_kind_and_problem(body)
        assert len(error) <= 1000

    def test_strips_source_and_dedup_from_fallback(self):
        body = "**Kind:** question\n**Source:** github\n**Dedup:** abc123\nActual content here"
        _, problem, _ = parse_kind_and_problem(body)
        assert "Source" not in problem
        assert "Dedup" not in problem
        assert "Actual content" in problem


# ── extract_answer ────────────────────────────────────────────────────────


def _comment(body: str, login: str = "maintainer", cid: int = 1,
             created_at: str = "2026-01-01T00:00:00Z") -> dict:
    return {"body": body, "user": {"login": login}, "id": cid, "created_at": created_at}


class TestExtractAnswer:

    def test_marker_priority_misakanet_answer(self):
        comments = [
            _comment("some earlier comment", cid=1),
            _comment("<!-- misakanet-answer -->\nThe answer is 42.", cid=2),
        ]
        answer, at, cid = extract_answer(comments)
        assert "The answer is 42" in answer
        assert cid == 2

    def test_marker_priority_answered_header(self):
        comments = [
            _comment("## ✅ Answered\nUse the new config flag.", cid=3),
        ]
        answer, _, cid = extract_answer(comments)
        assert cid == 3

    def test_marker_priority_answer_bracket(self):
        comments = [
            _comment("## [ANSWER]\nSet WORKER_TIMEOUT=30.", cid=4),
        ]
        answer, _, cid = extract_answer(comments)
        assert cid == 4

    def test_rejects_automated_marker(self):
        """A comment with both an answer marker AND an automated marker is skipped."""
        comments = [
            _comment("<!-- misakanet-answer --><!-- misakanet-intake-triage -->auto reply", cid=5),
            _comment("Real maintainer answer here, long enough to pass the 100-character fallback threshold that the function checks.", cid=6),
        ]
        answer, _, cid = extract_answer(comments)
        assert cid == 6

    def test_fallback_to_last_non_bot_comment(self):
        comments = [
            _comment("short", login="bot[bot]", cid=1),
            _comment("<!-- misakanet-intake-triage -->auto", login="bot[bot]", cid=2),
            _comment("This is a substantial maintainer reply with enough length to qualify for the fallback detection logic.", cid=3),
        ]
        answer, _, cid = extract_answer(comments)
        assert cid == 3

    def test_fallback_skips_short_comments(self):
        """Comments under 100 chars are too short for fallback."""
        comments = [
            _comment("ok", login="user", cid=1),
            _comment("sure thing", login="user", cid=2),
            _comment("This is a detailed maintainer response that exceeds the minimum length threshold for fallback detection.", cid=3),
        ]
        answer, _, cid = extract_answer(comments)
        assert cid == 3

    def test_no_answer_found(self):
        comments = [
            _comment("short", login="user", cid=1),
            _comment("<!-- misakanet-intake-triage -->auto reply", login="bot[bot]", cid=2),
        ]
        answer, at, cid = extract_answer(comments)
        assert answer is None
        assert cid is None

    def test_empty_comments(self):
        answer, at, cid = extract_answer([])
        assert answer is None
        assert cid is None

    def test_returns_created_at(self):
        comments = [_comment("<!-- misakanet-answer -->Answer text.", created_at="2026-06-15T10:00:00Z", cid=10)]
        _, at, _ = extract_answer(comments)
        assert at == "2026-06-15T10:00:00Z"

    def test_automated_markers_exhaustive(self):
        """Every AUTOMATED_MARKERS value causes rejection when paired with an answer marker."""
        for marker in AUTOMATED_MARKERS:
            body = f"<!-- misakanet-answer -->{marker}"
            comments = [
                _comment(body, cid=1),
                _comment("Genuine maintainer response that is definitely long enough for the 100-character fallback detection threshold to pass.", cid=2),
            ]
            _, _, cid = extract_answer(comments)
            assert cid == 2, f"marker {marker!r} should have been rejected"


# ── marker constants ─────────────────────────────────────────────────────


class TestMarkerConstants:

    def test_answer_markers_non_empty(self):
        assert len(ANSWER_MARKERS) >= 3

    def test_automated_markers_non_empty(self):
        assert len(AUTOMATED_MARKERS) >= 5

    def test_no_overlap(self):
        overlap = set(ANSWER_MARKERS) & set(AUTOMATED_MARKERS)
        assert not overlap, f"overlapping markers: {overlap}"
