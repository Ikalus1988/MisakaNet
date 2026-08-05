#!/usr/bin/env python3
"""Test contribution review CLI — accept, reject, credit grants.

Covers v2.14 MVP PR 4: maintainer review and credit grant.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.contribution_queue import submit_contribution
from scripts.contribution_review import (
    accept_contribution,
    reject_contribution,
    show_review_summary,
)
from scripts.usage_meter import get_status


@pytest.fixture(autouse=True)
def temp_files(tmp_path):
    """Use temporary queue and usage files."""
    queue_file = tmp_path / "contribution_queue.jsonl"
    usage_file = tmp_path / "usage_credits.jsonl"
    with patch("scripts.contribution_queue.QUEUE_FILE", queue_file), \
         patch("scripts.usage_meter.USAGE_FILE", usage_file), \
         patch("scripts.contribution_review.grant_credits") as mock_grant:
        # Make grant_credits actually work by importing the real function
        from scripts.usage_meter import grant_credits as real_grant
        mock_grant.side_effect = real_grant
        yield queue_file


# ── Accept ──

class TestAccept:
    def test_accept_grants_credits(self):
        result = submit_contribution(contrib_type="intake", message="good fix", user="anon:test")
        accepted = accept_contribution(result["id"], credits=20, note="verified")
        assert accepted["accepted"] is True
        assert accepted["credits_granted"] == 20

    def test_accept_auto_credits_intake(self):
        result = submit_contribution(contrib_type="intake", message="intake report")
        accepted = accept_contribution(result["id"])
        assert accepted["credits_granted"] == 5  # default for intake

    def test_accept_auto_credits_lesson(self):
        result = submit_contribution(contrib_type="lesson", title="lesson draft", problem="X", fix="Y")
        accepted = accept_contribution(result["id"])
        assert accepted["credits_granted"] == 20  # default for lesson

    def test_accept_nonexistent(self):
        result = accept_contribution("contrib_nonexistent")
        assert "error" in result

    def test_accept_already_accepted(self):
        result = submit_contribution(contrib_type="intake", message="test")
        accept_contribution(result["id"])
        again = accept_contribution(result["id"])
        assert "error" in again


# ── Reject ──

class TestReject:
    def test_reject_no_credits(self):
        result = submit_contribution(contrib_type="intake", message="bad")
        rejected = reject_contribution(result["id"], reason="duplicate")
        assert rejected["rejected"] is True

    def test_reject_nonexistent(self):
        result = reject_contribution("contrib_nonexistent")
        assert "error" in result

    def test_reject_already_accepted(self):
        result = submit_contribution(contrib_type="intake", message="test")
        accept_contribution(result["id"])
        rejected = reject_contribution(result["id"])
        assert "error" in rejected


# ── Summary ──

class TestSummary:
    def test_summary_counts(self):
        submit_contribution(contrib_type="intake", message="item 1")
        r2 = submit_contribution(contrib_type="intake", message="item 2")
        accept_contribution(r2["id"])
        summary = show_review_summary()
        assert summary["pending"] == 1
        assert summary["accepted"] == 1
        assert summary["rejected"] == 0


# ── Convert ──

class TestConvert:
    def test_convert_to_draft(self, tmp_path):
        from scripts.contribution_review import convert_to_draft
        from unittest.mock import patch as mock_patch

        result = submit_contribution(
            contrib_type="lesson",
            title="Fix DCO sign-off failure",
            problem="DCO check fails after squash merge",
            fix="Use git commit --amend --signoff",
        )

        drafts_dir = tmp_path / "lessons" / "drafts"
        with mock_patch("scripts.contribution_review.REPO_ROOT", tmp_path):
            converted = convert_to_draft(result["id"], "lesson", "devops")
            assert converted["converted"] is True
            assert "drafts" in converted["draft_path"]

            # Check draft file exists and has content
            draft_file = tmp_path / converted["draft_path"]
            assert draft_file.exists()
            content = draft_file.read_text()
            assert "Fix DCO sign-off failure" in content
            assert "DCO check fails" in content

    def test_convert_nonexistent(self):
        from scripts.contribution_review import convert_to_draft
        result = convert_to_draft("contrib_nonexistent")
        assert "error" in result


# ── End-to-end: submit -> accept -> credits consumed ──

class TestE2E:
    def test_contribution_to_credits_flow(self):
        """Submit -> accept -> credits available for lesson reads."""
        from scripts.usage_meter import check_lesson, record_read, FREE_READ_LIMIT

        user = "anon:e2e-test"

        # Exhaust free reads
        for i in range(FREE_READ_LIMIT):
            record_read(user, f"free-{i}")

        # Verify quota exceeded
        result = check_lesson(user, "test-lesson")
        assert result["allowed"] is False

        # Submit contribution
        contrib = submit_contribution(contrib_type="intake", message="e2e test", user=user)

        # Accept it
        accepted = accept_contribution(contrib["id"], credits=10)
        assert accepted["credits_granted"] == 10

        # Now can read again
        result = check_lesson(user, "test-lesson")
        assert result["allowed"] is True
        assert result["reason"] == "credit"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
