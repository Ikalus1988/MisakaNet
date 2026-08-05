#!/usr/bin/env python3
"""Test contribution queue — submission, dedup, redaction, status transitions.

Covers v2.14 MVP PR 3: contribution queue.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.contribution_queue import (
    VALID_STATUSES,
    get_contribution,
    list_contributions,
    submit_contribution,
    update_status,
)


@pytest.fixture(autouse=True)
def temp_queue(tmp_path):
    """Use a temporary queue file."""
    queue_file = tmp_path / "contribution_queue.jsonl"
    with patch("scripts.contribution_queue.QUEUE_FILE", queue_file):
        yield queue_file


# ── Submit ──

class TestSubmit:
    def test_submit_intake(self):
        result = submit_contribution(
            contrib_type="intake",
            message="pip install timeout behind proxy",
            source="curl",
        )
        assert result["submitted"] is True
        assert result["id"].startswith("contrib_")
        assert result["status"] == "pending"

    def test_submit_lesson(self):
        result = submit_contribution(
            contrib_type="lesson",
            title="Fix DCO sign-off failure",
            problem="DCO check fails after squash merge",
            fix="Use git commit --amend --signoff",
        )
        assert result["submitted"] is True
        assert result["status"] == "pending"

    def test_invalid_type(self):
        result = submit_contribution(contrib_type="bogus", message="test")
        assert "error" in result

    def test_empty_content_rejected(self):
        result = submit_contribution(contrib_type="intake", message="")
        assert "error" in result

    def test_quality_score_returned(self):
        result = submit_contribution(
            contrib_type="lesson",
            title="Fix DCO sign-off failure",
            problem="DCO check fails after squash merge because commit is not signed",
            fix="Use git commit --amend --signoff to add Signed-off-by trailer",
            verification="Run git log --show-signature to confirm",
        )
        assert result["quality_score"] >= 70
        assert isinstance(result["quality_notes"], list)


# ── Dedup ──

class TestDedup:
    def test_duplicate_rejected(self):
        submit_contribution(contrib_type="intake", message="same message")
        result = submit_contribution(contrib_type="intake", message="same message")
        assert result.get("error") == "duplicate"
        assert "existing_id" in result

    def test_different_content_accepted(self):
        submit_contribution(contrib_type="intake", message="message A")
        result = submit_contribution(contrib_type="intake", message="message B")
        assert result["submitted"] is True


# ── Redaction ──

class TestRedaction:
    def test_secrets_redacted(self):
        result = submit_contribution(
            contrib_type="intake",
            message="my token is ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij12",
        )
        assert result["redactions_applied"] >= 1

    def test_no_secrets_no_redaction(self):
        result = submit_contribution(
            contrib_type="intake",
            message="pip install fails",
        )
        assert result["redactions_applied"] == 0


# ── List ──

class TestList:
    def test_list_all(self):
        submit_contribution(contrib_type="intake", message="item 1")
        submit_contribution(contrib_type="lesson", title="item 2")
        items = list_contributions()
        assert len(items) == 2

    def test_filter_by_status(self):
        submit_contribution(contrib_type="intake", message="item 1")
        item2 = submit_contribution(contrib_type="intake", message="item 2")
        update_status(item2["id"], "accepted", "looks good")
        pending = list_contributions(status="pending")
        assert len(pending) == 1


# ── Status transitions ──

class TestStatusTransitions:
    def test_pending_to_accepted(self):
        result = submit_contribution(contrib_type="intake", message="good fix")
        updated = update_status(result["id"], "accepted", "verified")
        assert updated["status"] == "accepted"
        assert len(updated["review_history"]) == 1
        assert updated["review_history"][0]["from"] == "pending"
        assert updated["review_history"][0]["to"] == "accepted"

    def test_pending_to_rejected(self):
        result = submit_contribution(contrib_type="intake", message="bad")
        updated = update_status(result["id"], "rejected", "duplicate")
        assert updated["status"] == "rejected"

    def test_invalid_status(self):
        result = submit_contribution(contrib_type="intake", message="test")
        updated = update_status(result["id"], "bogus")
        assert updated is None

    def test_nonexistent_id(self):
        updated = update_status("contrib_nonexistent", "accepted")
        assert updated is None

    def test_all_valid_statuses(self):
        assert VALID_STATUSES == {"pending", "needs_repro", "accepted", "rejected", "duplicate", "converted"}


# ── Get contribution ──

class TestGetContribution:
    def test_found(self):
        result = submit_contribution(contrib_type="intake", message="find me")
        found = get_contribution(result["id"])
        assert found is not None
        assert found["id"] == result["id"]

    def test_not_found(self):
        assert get_contribution("contrib_nonexistent") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
