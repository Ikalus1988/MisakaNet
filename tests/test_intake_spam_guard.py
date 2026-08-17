#!/usr/bin/env python3
"""Regression test suite for MCP anonymous intake spam guard and payload validation.

Acceptance criteria:
- Regression corpus for body size limit, spam keywords, empty/vague submissions,
  markdown-heavy input, and secret-like strings.
- Tests verify redaction runs before GitHub issue body construction.
- Tests verify blocked submissions return an error/hint and do not fallback to local JSONL.
- Tests verify valid concise intakes still pass.
- Deterministic and inspectable rules (no ML classifier).
"""
import json
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.intake_redact import redact_text
from scripts.mcp_http_server import misakanet_submit_intake

FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "intake_spam_guard_corpus.json"


def load_corpus() -> list[dict]:
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestIntakeSpamGuardRegressionCorpus:
    """Validate each case in the spam guard regression corpus."""

    @pytest.fixture(autouse=True)
    def reset_rate_limits(self):
        """Clear rate limit windows before each test."""
        import scripts.mcp_http_server as server
        server._intake_rate_window.clear()
        server.INTAKE_IP_WINDOW.clear()
        server.INTAKE_TOKEN = ""

    def test_corpus_fixture_exists_and_valid(self):
        corpus = load_corpus()
        assert len(corpus) >= 8
        categories = {item["category"] for item in corpus}
        assert "body_size_limit" in categories
        assert "spam_keywords" in categories
        assert "empty_vague" in categories
        assert "markdown_heavy" in categories
        assert "secret_strings" in categories
        assert "valid_concise" in categories

    def test_spam_keywords_are_blocked_with_error(self):
        """Spam keywords must be blocked deterministically without executing gh."""
        corpus = load_corpus()
        spam_cases = [c for c in corpus if c["category"] == "spam_keywords"]
        assert len(spam_cases) >= 2

        with patch("subprocess.run") as mock_subproc:
            for case in spam_cases:
                payload = case["payload"]
                res = misakanet_submit_intake(
                    problem=payload.get("problem", ""),
                    error=payload.get("error", ""),
                    source=payload.get("source", "spammer"),
                )
                assert "error" in res, f"Expected error for case {case['id']}, got {res}"
                assert "spam" in res["error"].lower()
                assert res.get("voice") == "failure-warning"
            # subprocess.run (gh issue create) must NEVER be called for blocked spam
            mock_subproc.assert_not_called()

    def test_empty_and_vague_submissions_are_blocked(self):
        """Empty or whitespace-only problem submissions must be rejected."""
        corpus = load_corpus()
        empty_cases = [c for c in corpus if c["category"] == "empty_vague"]
        assert len(empty_cases) >= 2

        with patch("subprocess.run") as mock_subproc:
            for case in empty_cases:
                payload = case["payload"]
                res = misakanet_submit_intake(
                    problem=payload.get("problem", ""),
                    source=payload.get("source", "anon"),
                )
                assert "error" in res
                assert "problem is required" in res["error"].lower()
            mock_subproc.assert_not_called()

    def test_body_size_limit_truncation(self):
        """Submissions with oversized fields are bounded to limits and do not crash."""
        with patch("subprocess.run") as mock_subproc:
            mock_subproc.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/Ikalus1988/MisakaNet/issues/9999\n",
                stderr="",
            )
            oversized_problem = "A" * 15000
            oversized_error = "B" * 5000
            oversized_fix = "C" * 8000

            res = misakanet_submit_intake(
                problem=oversized_problem,
                error=oversized_error,
                fix=oversized_fix,
                source="stress-tester",
            )
            assert res.get("submitted") is True
            assert mock_subproc.called

            # Check that the command arguments sent to gh have body capped under 8000 chars
            cmd_args = mock_subproc.call_args[0][0]
            body_flag_idx = cmd_args.index("--body")
            body_content = cmd_args[body_flag_idx + 1]
            assert len(body_content.encode("utf-8")) <= 8000

    def test_markdown_heavy_sanitizes_title(self):
        """Markdown headers and backticks in problem must not pollute issue title."""
        with patch("subprocess.run") as mock_subproc:
            mock_subproc.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/Ikalus1988/MisakaNet/issues/8888\n",
                stderr="",
            )
            raw_problem = "# # # Header 1\n```bash\ncurl http://test\n```\nActual description of bug"
            res = misakanet_submit_intake(problem=raw_problem, source="md-tester")

            assert res.get("submitted") is True
            cmd_args = mock_subproc.call_args[0][0]
            title_flag_idx = cmd_args.index("--title")
            title = cmd_args[title_flag_idx + 1]

            # Title must not contain markdown # or backticks
            assert not title.startswith("[Intake] #")
            assert "```" not in title
            assert "\n" not in title

    def test_redaction_runs_before_github_issue_body_construction(self):
        """Secrets must be redacted inside the generated GitHub issue body."""
        with patch("subprocess.run") as mock_subproc:
            mock_subproc.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/Ikalus1988/MisakaNet/issues/7777\n",
                stderr="",
            )
            secret_problem = "Failed with postgres://admin:P@ssw0rd123@prod.db:5432/main"
            secret_error = "GitHub PAT error: ghp_1234567890abcdefghijklmnopqrstuvwxyz"
            secret_fix = "Bearer sk-ant-api03-abcdef12345678901234567890"

            res = misakanet_submit_intake(
                problem=secret_problem,
                error=secret_error,
                fix=secret_fix,
                source="sec-auditor",
            )
            assert res.get("submitted") is True
            assert res.get("redactions_applied", 0) >= 2

            cmd_args = mock_subproc.call_args[0][0]
            body_flag_idx = cmd_args.index("--body")
            body_content = cmd_args[body_flag_idx + 1]

            # Assert secrets are completely absent from issue body
            assert "ghp_1234567890" not in body_content
            assert "P@ssw0rd123" not in body_content
            assert "sk-ant-api03" not in body_content
            assert "[REDACTED:" in body_content

    def test_blocked_submission_returns_error_and_no_fallback_to_jsonl(self, tmp_path):
        """When GitHub issue creation fails or is blocked, an error is returned and no local JSONL is written."""
        with patch("subprocess.run") as mock_subproc:
            mock_subproc.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="gh: authentication required",
            )
            res = misakanet_submit_intake(
                problem="Standard failure with no local fallback expected",
                source="test-no-fallback",
            )
            assert res.get("submitted") is False
            assert "error" in res
            assert "GitHub issue creation failed" in res["error"]
            assert "hint" in res
            assert "NOT saved" in res["hint"]

    def test_valid_concise_intake_passes(self):
        """Valid concise intake report succeeds with all expected output fields."""
        with patch("subprocess.run") as mock_subproc:
            mock_subproc.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/Ikalus1988/MisakaNet/issues/1097\n",
                stderr="",
            )
            res = misakanet_submit_intake(
                kind="missing_lesson",
                problem="FastMCP server raises TypeError when client sends empty params object on tools/list",
                error="TypeError: FastMCP.list_tools() takes 0 positional arguments but 1 was given",
                what_tried="Tested passing params: {} vs omitting params",
                fix="Decorate list_tools handler with optional arguments check",
                verification="Ran pytest tests/test_mcp_server.py and verified both pass",
                source="valid-agent",
            )
            assert res.get("submitted") is True
            assert res.get("intake_id") == "issue-1097"
            assert res.get("status") == "pending_review"
            assert "dedup_hash" in res
            assert res.get("voice") == "pair-success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
