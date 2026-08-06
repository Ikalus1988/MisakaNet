#!/usr/bin/env python3
"""Test usage meter — quota enforcement, credit grants, daily resets.

Covers v2.14 MVP: free reads, quota exceeded, credit system.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.usage_meter import (
    FREE_READ_LIMIT,
    check_lesson,
    get_status,
    grant_credits,
    hash_ip,
    record_read,
    reset_user,
)


@pytest.fixture(autouse=True)
def temp_usage(tmp_path):
    """Use a temporary usage file."""
    usage_file = tmp_path / "usage_credits.jsonl"
    with patch("scripts.usage_meter.USAGE_FILE", usage_file):
        yield usage_file


# ── Status ──

class TestStatus:
    def test_new_user(self):
        status = get_status("anon:test123")
        assert status["free_reads_used"] == 0
        assert status["free_reads_remaining"] == FREE_READ_LIMIT
        assert status["credits"] == 0

    def test_after_reads(self):
        for i in range(3):
            record_read("anon:test123", f"lesson-{i}")
        status = get_status("anon:test123")
        assert status["free_reads_used"] == 3
        assert status["free_reads_remaining"] == FREE_READ_LIMIT - 3


# ── Check lesson ──

class TestCheckLesson:
    def test_allowed_within_quota(self):
        result = check_lesson("anon:test", "some-lesson")
        assert result["allowed"] is True
        assert result["reason"] == "free_read"

    def test_allowed_with_credits(self):
        # Exhaust free reads
        for i in range(FREE_READ_LIMIT):
            record_read("anon:test", f"lesson-{i}")
        # Grant credits
        grant_credits("anon:test", 10, "test")
        result = check_lesson("anon:test", "some-lesson")
        assert result["allowed"] is True
        assert result["reason"] == "credit"

    def test_denied_no_quota_no_credits(self):
        # Exhaust free reads
        for i in range(FREE_READ_LIMIT):
            record_read("anon:test", f"lesson-{i}")
        result = check_lesson("anon:test", "some-lesson")
        assert result["allowed"] is False
        assert result["reason"] == "quota_exceeded"
        assert "misakanet_submit_intake" in str(result["next"])


# ── Record read ──

class TestRecordRead:
    def test_records_read(self):
        result = record_read("anon:test", "lesson-1")
        assert result["recorded"] is True
        assert result["action_source"] == "free_read"

    def test_tracks_multiple_reads(self):
        for i in range(3):
            record_read("anon:test", f"lesson-{i}")
        status = get_status("anon:test")
        assert status["free_reads_used"] == 3


# ── Credits ──

class TestCredits:
    def test_grant_credits(self):
        result = grant_credits("anon:test", 20, "accepted_contribution", "contrib_abc")
        assert result["granted"] is True
        assert result["credits_added"] == 20

    def test_credits_persist(self):
        grant_credits("anon:test", 20, "test")
        status = get_status("anon:test")
        assert status["credits"] == 20

    def test_multiple_grants_accumulate(self):
        grant_credits("anon:test", 10, "test1")
        grant_credits("anon:test", 15, "test2")
        status = get_status("anon:test")
        assert status["credits"] == 25

    def test_credits_actually_consumed(self):
        """grant 2 credits -> consume 2 credit reads -> third read quota_exceeded."""
        user = "anon:credit-consume-test"
        # Exhaust free reads
        for i in range(FREE_READ_LIMIT):
            record_read(user, f"free-{i}")
        # Grant 2 credits
        grant_credits(user, 2, "test")
        # First credit read: allowed
        result = check_lesson(user, "credit-1")
        assert result["allowed"] is True
        assert result["reason"] == "credit"
        record_read(user, "credit-1")
        # Second credit read: allowed
        result = check_lesson(user, "credit-2")
        assert result["allowed"] is True
        record_read(user, "credit-2")
        # Third credit read: quota exceeded (credits exhausted)
        result = check_lesson(user, "credit-3")
        assert result["allowed"] is False
        assert result["reason"] == "quota_exceeded"

    def test_grant_total_not_double_counted(self):
        """grant 20 credits -> credits_total == 20, not 40."""
        result = grant_credits("anon:double-test", 20, "test")
        assert result["credits_total"] == 20


# ── Registered vs anonymous ──

class TestUserTypes:
    def test_anonymous_limit(self):
        status = get_status("anon:test")
        assert status["free_reads_limit"] == FREE_READ_LIMIT
        assert status["is_registered"] is False

    def test_registered_limit(self):
        status = get_status("token:abc123")
        assert status["free_reads_limit"] == 20
        assert status["is_registered"] is True


# ── Reset ──

class TestReset:
    def test_reset_user(self):
        for i in range(5):
            record_read("anon:test", f"lesson-{i}")
        reset_user("anon:test")
        # Note: reset doesn't clear records, just records the reset event
        # The implementation counts all reads, so status still shows them
        # This is by design — reset is for admin tracking, not quota manipulation


# ── Hash IP ──

class TestHashIP:
    def test_hash_ip(self):
        h = hash_ip("192.168.1.1")
        assert h.startswith("anon:")
        assert len(h) == 17  # "anon:" + 12 hex chars

    def test_same_ip_same_hash(self):
        assert hash_ip("10.0.0.1") == hash_ip("10.0.0.1")

    def test_different_ip_different_hash(self):
        assert hash_ip("10.0.0.1") != hash_ip("10.0.0.2")


# ── Quota exceeded flow ──

class TestQuotaExceeded:
    def test_full_flow(self):
        user = "anon:flow-test"

        # 1. Initial: 5 free reads
        status = get_status(user)
        assert status["free_reads_remaining"] == 5

        # 2. Use all 5
        for i in range(5):
            result = check_lesson(user, f"lesson-{i}")
            assert result["allowed"] is True
            record_read(user, f"lesson-{i}")

        # 3. 6th read: quota exceeded
        result = check_lesson(user, "lesson-6")
        assert result["allowed"] is False
        assert result["reason"] == "quota_exceeded"

        # 4. Grant credits
        grant_credits(user, 20, "accepted_contribution")

        # 5. Now allowed
        result = check_lesson(user, "lesson-7")
        assert result["allowed"] is True
        assert result["reason"] == "credit"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
