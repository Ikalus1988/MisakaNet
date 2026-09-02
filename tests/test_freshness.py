"""Tests for freshness decay model."""

import pytest
from datetime import datetime

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from misakanet.freshness import (
    BOOST_VALUES,
    DECAY_CONFIG,
    FRESHNESS_TIERS,
    compute_freshness,
    get_tier,
    parse_date,
)


# ── parse_date ──

class TestParseDate:
    def test_iso_date(self):
        assert parse_date("2026-08-01") == datetime(2026, 8, 1)

    def test_iso_datetime(self):
        assert parse_date("2026-08-01T12:00:00") == datetime(2026, 8, 1, 12, 0, 0)

    def test_empty(self):
        assert parse_date("") is None
        assert parse_date(None) is None

    def test_invalid(self):
        assert parse_date("not-a-date") is None


# ── get_tier ──

class TestGetTier:
    def test_fresh(self):
        tier = get_tier(90)
        assert tier["tier"] == "fresh"
        assert tier["badge"] == "🟢"

    def test_stable(self):
        tier = get_tier(70)
        assert tier["tier"] == "stable"

    def test_aging(self):
        tier = get_tier(45)
        assert tier["tier"] == "aging"

    def test_stale(self):
        tier = get_tier(25)
        assert tier["tier"] == "stale"

    def test_outdated(self):
        tier = get_tier(5)
        assert tier["tier"] == "outdated"
        assert tier["badge"] == "🔴"

    def test_boundary_80(self):
        assert get_tier(80)["tier"] == "fresh"
        assert get_tier(79)["tier"] == "stable"

    def test_boundary_60(self):
        assert get_tier(60)["tier"] == "stable"
        assert get_tier(59)["tier"] == "aging"

    def test_boundary_40(self):
        assert get_tier(40)["tier"] == "aging"
        assert get_tier(39)["tier"] == "stale"

    def test_boundary_20(self):
        assert get_tier(20)["tier"] == "stale"
        assert get_tier(19)["tier"] == "outdated"


# ── compute_freshness ──

class TestComputeFreshness:
    def test_new_lesson_no_decay(self):
        """Lesson merged today — full score, protected."""
        today = datetime(2026, 8, 23)
        lesson = {
            "created": "2026-08-23",
            "provenance": {"merged_at": "2026-08-23"},
        }
        result = compute_freshness(lesson, today=today)
        assert result["score"] == 100
        assert result["protected"] is True
        assert result["days_since_merge"] == 0

    def test_protection_period(self):
        """Lesson within 14-day protection — no decay."""
        today = datetime(2026, 8, 23)
        lesson = {
            "provenance": {"merged_at": "2026-08-10"},  # 13 days ago
        }
        result = compute_freshness(lesson, today=today)
        assert result["score"] == 100
        assert result["protected"] is True
        assert result["days_since_merge"] == 13

    def test_after_protection_decay(self):
        """Lesson after protection — decay starts."""
        today = datetime(2026, 8, 23)
        lesson = {
            "provenance": {"merged_at": "2026-08-01"},  # 22 days ago
        }
        result = compute_freshness(lesson, today=today)
        # 22 - 14 = 8 days of decay at 1.0/day = 8 points
        assert result["score"] == 92.0
        assert result["protected"] is False
        assert result["days_since_merge"] == 22

    def test_slow_decay_below_threshold(self):
        """Below 50, decay slows to 0.5/day."""
        today = datetime(2026, 8, 23)
        lesson = {
            "provenance": {"merged_at": "2026-06-01"},  # 83 days ago
        }
        result = compute_freshness(lesson, today=today)
        # 83 - 14 = 69 decay days
        # 50 days at 1.0/day to reach 50, then 19 days at 0.5/day = 9.5
        # 100 - 50 - 9.5 = 40.5
        assert result["score"] == 40.5
        assert result["tier"]["tier"] == "aging"

    def test_pinned_exempt(self):
        """Pinned lesson — no decay."""
        today = datetime(2026, 12, 23)  # 4 months later
        lesson = {
            "pinned": True,
            "provenance": {"merged_at": "2026-08-01"},
        }
        result = compute_freshness(lesson, today=today)
        assert result["score"] == 100
        assert result["is_pinned"] is True

    def test_pin_field(self):
        """pin: true also works."""
        today = datetime(2026, 12, 23)
        lesson = {"pin": True, "provenance": {"merged_at": "2026-08-01"}}
        result = compute_freshness(lesson, today=today)
        assert result["is_pinned"] is True
        assert result["score"] == 100

    def test_was_used_boost(self):
        """was_used event adds +5."""
        today = datetime(2026, 8, 23)
        lesson = {
            "created": "2026-08-23",
            "freshness_boosts": ["was_used"],
        }
        result = compute_freshness(lesson, today=today)
        # Base 100 + 5 = 105, capped at 100
        assert result["score"] == 100
        assert len(result["boosts_applied"]) == 1

    def test_helpful_vote_boost(self):
        """helpful_vote adds +3."""
        today = datetime(2026, 8, 23)
        lesson = {
            "created": "2026-08-23",
            "freshness_boosts": ["helpful_vote"],
        }
        result = compute_freshness(lesson, today=today)
        assert result["score"] == 100  # 100 + 3 capped
        assert result["boosts_applied"][0]["type"] == "helpful_vote"

    def test_maintainer_edit_boost(self):
        """maintainer_edit adds +10."""
        today = datetime(2026, 9, 10)  # 18 days later
        lesson = {
            "created": "2026-08-23",
            "freshness_boosts": ["maintainer_edit"],
        }
        result = compute_freshness(lesson, today=today)
        # 18 - 14 = 4 days decay at 1.0/day = 4 points
        # 100 + 10 = 110, capped at 100, then -4 = 96
        assert result["score"] == 96.0

    def test_no_date_old(self):
        """No date found — assume very old."""
        today = datetime(2026, 8, 23)
        lesson = {"title": "No date lesson"}
        result = compute_freshness(lesson, today=today)
        assert result["days_since_merge"] == 365
        assert result["score"] < 50

    def test_multiple_boosts(self):
        """Multiple boosts stack."""
        today = datetime(2026, 8, 23)
        lesson = {
            "created": "2026-08-23",
            "freshness_boosts": ["was_used", "helpful_vote", "maintainer_edit"],
        }
        result = compute_freshness(lesson, today=today)
        # 100 + 5 + 3 + 10 = 118, capped at 100
        assert result["score"] == 100
        assert len(result["boosts_applied"]) == 3

    def test_custom_config(self):
        """Custom config overrides defaults."""
        today = datetime(2026, 8, 23)
        lesson = {"provenance": {"merged_at": "2026-08-01"}}  # 22 days
        config = {"protection_days": 0, "decay_rate": 2.0}
        result = compute_freshness(lesson, config=config, today=today)
        # 22 days at 2.0/day = 44 points
        assert result["score"] == 56.0

    def test_real_lesson_format(self):
        """Real lesson with provenance.merged_at."""
        today = datetime(2026, 8, 23)
        lesson = {
            "title": "Data Quality Fix",
            "domain": "data-engineering",
            "created": "2026-08-06",
            "provenance": {
                "merged_at": "2026-07-25",
            },
        }
        result = compute_freshness(lesson, today=today)
        # 29 days - 14 protection = 15 decay at 1.0/day
        assert result["score"] == 85.0
        assert result["tier"]["tier"] == "fresh"


# ── Tier badges ──

class TestTierBadges:
    def test_all_tiers_have_badge(self):
        for name, info in FRESHNESS_TIERS.items():
            assert "badge" in info, f"{name} missing badge"
            assert info["badge"], f"{name} has empty badge"

    def test_all_tiers_have_label(self):
        for name, info in FRESHNESS_TIERS.items():
            assert "label" in info, f"{name} missing label"


# ── Edge cases ──

class TestEdgeCases:
    def test_score_never_negative(self):
        """Score should never go below 0."""
        today = datetime(2030, 1, 1)
        lesson = {"provenance": {"merged_at": "2026-01-01"}}
        result = compute_freshness(lesson, today=today)
        assert result["score"] >= 0

    def test_score_never_above_100(self):
        """Score should never exceed 100 (before boosts, capped after)."""
        today = datetime(2026, 8, 23)
        lesson = {"created": "2026-08-23"}
        result = compute_freshness(lesson, today=today)
        assert result["score"] <= 100

    def test_pinned_with_boosts(self):
        """Pinned lesson ignores boosts (already at 100)."""
        today = datetime(2026, 8, 23)
        lesson = {
            "pinned": True,
            "freshness_boosts": ["was_used", "maintainer_edit"],
        }
        result = compute_freshness(lesson, today=today)
        assert result["score"] == 100
        assert result["is_pinned"] is True
        # Boosts are not applied for pinned lessons
        assert result["boosts_applied"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
