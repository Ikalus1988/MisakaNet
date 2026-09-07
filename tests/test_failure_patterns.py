"""Tests for error-signature index (failure_patterns) and search/intake fusion (Issue #1527)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from misakanet.search.patterns import (
    PATTERNS_FILE,
    extract_failure_patterns_from_markdown,
    extract_key_tokens,
    find_best_pattern_match,
    get_pattern_bonus,
    load_failure_patterns,
    match_failure_pattern,
    normalize_error,
)
from misakanet.search.engine import CachedDoc, _get_match_reason, _get_why_matched, _rank_docs_impl
from scripts.intake_bot import precheck


def test_normalize_error_tokens():
    """Verify that variable paths, hashes, numbers, and URLs are normalized into static tokens."""
    raw = "Error at /home/ubuntu/app/node_modules/pkg/index.js:42:15 with hash 8f9b1c2d3e4f5a6b and 192.168.1.100"
    normalized = normalize_error(raw)
    assert "<PATH>" in normalized
    assert "<NUM>" in normalized
    assert "<SHA>" in normalized
    assert "<IP>" in normalized


def test_extract_key_tokens():
    """Verify key token extraction with stop words filtered."""
    tokens = extract_key_tokens("ModuleNotFoundError: No module named 'requests'")
    assert "modulenotfounderror" in tokens
    assert "requests" in tokens
    assert "error" not in tokens


def test_extract_failure_patterns_from_markdown():
    """Verify error patterns extracted from markdown title, problem, and code blocks."""
    content = """---
title: Fix Node.js ECONNRESET Connection Reset Error
domain: automation
---
# Problem
NodeApiError: read ECONNRESET at TCP.onStreamRead

```bash
curl https://api.example.com
```
"""
    extracted = extract_failure_patterns_from_markdown(
        content=content,
        title="Fix Node.js ECONNRESET Connection Reset Error",
        lesson_id="n8n-nodejs-econnreset-connection-reset-fix",
        domain="automation",
    )
    assert extracted["lesson_id"] == "n8n-nodejs-econnreset-connection-reset-fix"
    assert len(extracted["templates"]) > 0
    assert any("econnreset" in t.lower() for t in extracted["templates"])


def test_match_failure_pattern():
    """Verify matching scoring logic across exact, template, and key tokens."""
    pattern = {
        "lesson_id": "test-lesson",
        "templates": ["modulenotfounderror: no module named <IDENT>"],
        "regexes": [r"modulenotfounderror:\s*no\s*module\s*named\s*.*"],
        "key_tokens": ["modulenotfounderror", "requests"],
    }
    score, desc = match_failure_pattern("ModuleNotFoundError: No module named 'requests'", pattern)
    assert score >= 0.90
    assert desc is not None

    score_nomatch, desc_nomatch = match_failure_pattern("Completely unrelated text about gardening", pattern)
    assert score_nomatch == 0.0
    assert desc_nomatch is None


def test_sidecar_index_exists_and_populated():
    """Verify failure_patterns.json sidecar index exists and covers canonical corpus."""
    assert PATTERNS_FILE.exists()
    patterns = load_failure_patterns()
    assert isinstance(patterns, dict)
    assert len(patterns) >= 300


def test_ten_spot_checks_accuracy():
    """Verify all 10 benchmark error-lesson pairs resolve with >= 80% accuracy."""
    spot_checks = [
        (
            "dco-auto-fix-workflow",
            "Commit sha: 8f9b1c2, Author: user, Committer: user; Expected \"Signed-off-by: user <user@example.com>\", but got \"\"",
        ),
        (
            "fehler-python-modul-nicht-gefunden",
            "ModuleNotFoundError: No module named 'requests'",
        ),
        (
            "aider-windows-unicode-error",
            "UnicodeEncodeError: 'gbk' codec can't encode character in position 14: illegal multibyte sequence",
        ),
        (
            "hermes-state-database-lock-issues-cleanup-protocol",
            "sqlite3.OperationalError: database is locked on SQLite state.db",
        ),
        (
            "pull-request-welcome-trigger-trap",
            "Skipping pr-welcome.yml: condition 'contains(fromJSON('[\"FIRST_TIMER\", \"FIRST_TIME_CONTRIBUTOR\"]'), github.event.pull_request.author_association)' evaluated to false",
        ),
        (
            "gitguardian-placeholder-url-credential-safe-form",
            "GitGuardian: Secret type: Basic Auth String detected at lessons/xxx.md:32",
        ),
        (
            "asyncio-cancellederror-swallows-resources",
            "Python asyncio CancelledError Silently Swallows Resources in Long-Running Services",
        ),
        (
            "n8n-nodejs-econnreset-connection-reset-fix",
            "NodeApiError: read ECONNRESET at TCP.onStreamRead",
        ),
        (
            "aider-litellm-model-name-rejection",
            "LiteLLM requires provider prefix for custom endpoints: anthropic/claude-sonnet-4-6",
        ),
        (
            "lesson-07-uv-venv-seed-fix-no-pip",
            "ModuleNotFoundError: No module named 'pip' in Ubuntu WSL",
        ),
    ]

    patterns = load_failure_patterns()
    hits = 0
    for expected_id, query in spot_checks:
        matched_id, score, desc = find_best_pattern_match(query, patterns)
        if matched_id == expected_id:
            hits += 1

    accuracy = hits / len(spot_checks)
    assert accuracy >= 0.80
    assert hits == 10


def test_search_engine_pattern_fusion():
    """Verify search engine scoring and why_matched integration for failure patterns."""
    doc_match = CachedDoc(
        filename="n8n-nodejs-econnreset-connection-reset-fix.md",
        filepath=Path("lessons/contrib/n8n-nodejs-econnreset-connection-reset-fix.md"),
        content="NodeApiError: read ECONNRESET at TCP.onStreamRead",
        mtime=1000.0,
        title="Fix Node.js ECONNRESET Connection Reset Error in n8n Webhook HTTP Requests",
        domain="automation",
    )
    doc_other = CachedDoc(
        filename="other-lesson.md",
        filepath=Path("lessons/contrib/other-lesson.md"),
        content="General guide about networking and sockets",
        mtime=1000.0,
        title="General Networking Guide",
        domain="devops",
    )

    query = "NodeApiError: read ECONNRESET at TCP.onStreamRead"
    ranked = _rank_docs_impl(query, [doc_other, doc_match])
    assert ranked[0][1].filepath.stem == "n8n-nodejs-econnreset-connection-reset-fix"

    reason = _get_match_reason(query, doc_match, score=2.0)
    assert "failure_pattern" in reason
    why = _get_why_matched(reason)
    assert "failure_pattern" in why["match_fields"]


def test_intake_bot_precheck_pattern_match():
    """Verify intake bot precheck leverages error patterns to resolve known failures."""
    query = "ModuleNotFoundError: No module named 'requests'"
    result = precheck(query, sim_threshold=0.30)
    assert result is not None
    assert result["id"] == "fehler-python-modul-nicht-gefunden"
    assert result["_sim"] >= 0.70
