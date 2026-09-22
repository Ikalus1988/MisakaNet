import pytest
from salvage_digest.core import Issue, ReviewAction, parse_digest, review_issue, sanitize_text, render_review


def test_parse_digest_extracts_valid_rows_and_normalizes_title():
    text = '| #1630 | [Intake] Roleplay chat app (Go): user wrote "Arlet | 2026-09-11 | [Review](https://github.com/a/issues/1630) |\n'
    issues = parse_digest(text)
    assert issues == [Issue(1630, '[Intake] Roleplay chat app (Go): user wrote "Arlet', '2026-09-11', 'https://github.com/a/issues/1630')]


def test_parser_ignores_malformed_rows_and_rejects_non_text():
    assert parse_digest('| #x | bad | 2026-01-01 | [Review](https://x) |') == []
    with pytest.raises(TypeError):
        parse_digest(None)


def test_review_with_error_and_verification_is_improvable():
    report = review_issue(Issue(1, "bug", "2026-01-01", "https://example.test"), error="boom", example="x()", verification="run test")
    assert report.action is ReviewAction.IMPROVE
    assert not any("missing evidence" in x for x in report.checklist)


def test_review_without_evidence_requires_human_triage():
    report = review_issue(Issue(2, "idea", "2026-01-01", "https://example.test"))
    assert report.action is ReviewAction.CONVERT
    assert "Error" in report.checklist[0]


def test_sanitize_text_removes_paths_and_secret_values():
    value = sanitize_text("/Users/alice/project/app.py token=abc123")
    assert "alice" not in value and "abc123" not in value
    assert "<REDACTED_PATH>" in value and "<REDACTED>" in value


def test_render_review_is_explicitly_read_only():
    issue = Issue(3, "x", "2026-01-01", "https://example.test")
    output = render_review([review_issue(issue)])
    assert "No external GitHub changes were performed." in output
