"""Tests for CI lesson search workflow logic (Issue #1174)."""
from __future__ import annotations

import json
import pytest


def test_error_extraction_patterns():
    """Test error pattern matching for common CI failures."""
    error_patterns = [
        r"Error:",
        r"FAILED",
        r"Exception:",
        r"Traceback",
        r"fatal:",
        r"error\[",
    ]

    test_lines = [
        "Error: FileNotFoundError: /tmp/test.db",
        "FAILED tests/test_mcp_server.py::test_search",
        "Exception: Connection timeout",
        "Traceback (most recent call last):",
        "fatal: unable to access remote",
        "error[TS2322]: Type mismatch",
        "PASS tests/test_basic.py",  # Should NOT match
        "normal log output",  # Should NOT match
    ]

    import re
    matched = []
    for line in test_lines:
        if any(re.search(p, line, re.IGNORECASE) for p in error_patterns):
            matched.append(line)

    assert len(matched) == 6
    assert "PASS" not in " ".join(matched)
    assert "normal log" not in " ".join(matched)


def test_pr_comment_format():
    """Test PR comment markdown formatting."""
    results = [
        {
            "title": "pip timeout behind proxy",
            "problem": "pip install hangs when behind corporate proxy",
            "fix": "Add --proxy flag or set HTTP_PROXY env var",
            "link": "https://example.com/lesson/1"
        },
        {
            "title": "DCO sign-off missing",
            "problem": "PR fails DCO check",
            "fix": "git commit -s to add sign-off",
            "link": "https://example.com/lesson/2"
        }
    ]

    lines = ['## 🔍 MisakaNet found matching lessons', '',
             '| Lesson | Problem | Fix |',
             '|--------|---------|-----|']
    for r in results[:3]:
        title = r.get('title', 'Untitled')
        problem = r.get('problem', '')[:80]
        fix = r.get('fix', '')[:80]
        link = r.get('link', '')
        if link:
            lines.append(f'| [{title}]({link}) | {problem} | {fix} |')
        else:
            lines.append(f'| {title} | {problem} | {fix} |')
    lines.extend(['', '> Powered by [MisakaNet](https://github.com/Ikalus1988/MisakaNet)'])

    comment = '\n'.join(lines)

    assert "MisakaNet found matching lessons" in comment
    assert "pip timeout behind proxy" in comment
    assert "DCO sign-off missing" in comment
    assert "https://example.com/lesson/1" in comment
    assert "| Lesson | Problem | Fix |" in comment


def test_empty_results():
    """Test that empty results produce no comment."""
    results = []
    if len(results) > 0:
        comment = "Should not be generated"
    else:
        comment = ""

    assert comment == ""


def test_comment_truncation():
    """Test long problem/fix text gets truncated."""
    long_text = "A" * 200
    truncated = long_text[:80] + ('...' if len(long_text) > 80 else '')

    assert len(truncated) == 83
    assert truncated.endswith('...')


def test_rate_limit_logic():
    """Test that existing comment detection works."""
    existing_comments = [
        {"id": 1, "body": "Some other comment", "user": {"login": "user1"}},
        {"id": 2, "body": "## 🔍 MisakaNet found matching lessons", "user": {"login": "github-actions[bot]"}},
    ]

    found = any(
        c.get("body", "").includes("MisakaNet found matching lessons") if hasattr(c.get("body", ""), "includes") else "MisakaNet found matching lessons" in c.get("body", "")
        for c in existing_comments
        if c.get("user", {}).get("login") == "github-actions[bot]'
    )

    # Simpler check
    found = False
    for c in existing_comments:
        if c.get("user", {}).get("login") == "github-actions[bot]" and "MisakaNet found matching lessons" in c.get("body", ""):
            found = True
            break

    assert found is True


if __name__ == "__main__":
    test_error_extraction_patterns()
    test_pr_comment_format()
    test_empty_results()
    test_comment_truncation()
    test_rate_limit_logic()
    print("All tests passed ✓")
