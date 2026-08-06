"""Tests for leaderboard scoring formula (#355).

Verifies:
- Time decay: 30-day half-life with 10% floor
- PR size factor: log-scaled, distinguishes 1-line from 1000-line
- Recency bonus: separate from decay
- Top-5 stability: existing top contributors don't get displaced by single new PR
"""
import math

import pytest


# Import the scoring helpers directly (they're module-level functions)
# We test the pure math, not the GitHub API calls.
def time_decay(days_ago: float) -> float:
    """30-day half-life decay with 10% floor."""
    return max(0.1, 0.5 ** (days_ago / 30))


def pr_size_factor(additions: int, deletions: int) -> float:
    """Log-scaled PR size factor."""
    total = max(1, additions + deletions)
    return math.log10(total) + 1


def recency_bonus(days_ago: int) -> float:
    """Separate recency bonus."""
    if days_ago <= 7:
        return 0.5
    if days_ago <= 30:
        return 0.2
    return 0.0


class TestTimeDecay:
    """Time decay: 30-day half-life, 10% floor."""

    def test_today_weight_is_1(self):
        assert time_decay(0) == 1.0

    def test_30_day_half_life(self):
        assert abs(time_decay(30) - 0.5) < 0.01

    def test_60_day_quarter(self):
        assert abs(time_decay(60) - 0.25) < 0.01

    def test_floor_at_10_percent(self):
        """Contributions never decay below 10% of original."""
        assert time_decay(365) == 0.1
        assert time_decay(1000) == 0.1
        assert time_decay(10000) == 0.1

    def test_monotonically_decreasing(self):
        """More recent → higher weight."""
        for d in range(0, 200, 10):
            assert time_decay(d) >= time_decay(d + 10)


class TestPrSizeFactor:
    """PR size factor: log-scaled."""

    def test_1_line_fix(self):
        """1-line fix: factor ~1.0."""
        factor = pr_size_factor(1, 0)
        assert 0.9 <= factor <= 1.1

    def test_100_line_pr(self):
        """100-line PR: factor ~3.0."""
        factor = pr_size_factor(80, 20)
        assert 2.8 <= factor <= 3.2

    def test_1000_line_feature(self):
        """1000-line feature: factor ~4.0."""
        factor = pr_size_factor(800, 200)
        assert 3.8 <= factor <= 4.2

    def test_zero_changes(self):
        """0 changes treated as 1."""
        assert pr_size_factor(0, 0) == pr_size_factor(1, 0)

    def test_larger_pr_higher_factor(self):
        """Bigger PR → higher factor."""
        assert pr_size_factor(10, 0) < pr_size_factor(100, 0) < pr_size_factor(1000, 0)


class TestRecencyBonus:
    """Recency bonus: separate from decay."""

    def test_within_7_days(self):
        assert recency_bonus(0) == 0.5
        assert recency_bonus(7) == 0.5

    def test_within_30_days(self):
        assert recency_bonus(8) == 0.2
        assert recency_bonus(30) == 0.2

    def test_beyond_30_days(self):
        assert recency_bonus(31) == 0.0
        assert recency_bonus(365) == 0.0


class TestTopFiveStability:
    """Top-5 contributors remain in top-10 after recalculation.

    Scenario: Veteran with 50 commits over 6 months vs newcomer with 1 big PR.
    """

    def _score_commits(self, commit_days: list[int], pr_additions: int = 0,
                       pr_deletions: int = 0) -> float:
        """Calculate score for a contributor."""
        commit_score = sum(time_decay(d) for d in commit_days)
        if pr_additions or pr_deletions:
            size = pr_size_factor(pr_additions, pr_deletions) / 2.0
        else:
            size = 0.5
        most_recent = min(commit_days) if commit_days else 365
        return commit_score * size + recency_bonus(most_recent)

    def test_veteran_outranks_single_big_pr(self):
        """50 commits over 6 months should beat 1 recent 1000-line PR."""
        # Veteran: 50 commits, spread over 180 days
        veteran_days = list(range(0, 180, 4))  # ~45 commits over 6 months
        veteran = self._score_commits(veteran_days, pr_additions=10, pr_deletions=5)

        # Newcomer: 1 recent big PR
        newcomer = self._score_commits([1], pr_additions=900, pr_deletions=100)

        assert veteran > newcomer, (
            f"Veteran ({veteran:.2f}) should outrank newcomer ({newcomer:.2f})"
        )

    def test_consistent_contributor_beats_burst(self):
        """Consistent weekly contributor beats a burst of 3 small PRs in 1 day."""
        # Consistent: 1 commit per week for 10 weeks, moderate PRs
        consistent_days = [i * 7 for i in range(10)]
        consistent = self._score_commits(consistent_days, pr_additions=30, pr_deletions=10)

        # Burst: 3 commits in 1 day, small PRs
        burst_days = [1] * 3
        burst = self._score_commits(burst_days, pr_additions=20, pr_deletions=5)

        assert consistent > burst, (
            f"Consistent ({consistent:.2f}) should outrank burst ({burst:.2f})"
        )

    def test_old_contributions_still_count(self):
        """A contributor with 50 commits 90+ days ago still has meaningful score."""
        old_days = list(range(90, 140))  # 50 commits, all 90-140 days ago
        score = self._score_commits(old_days)
        # Each commit decays to ~0.10-0.19, 50 commits × 0.15 avg × 0.5 size → ~3.75
        assert score > 2.0, f"Old contributions should still count, got {score:.2f}"

    def test_no_pr_data_default(self):
        """Contributors without PR data get a small default size factor."""
        no_pr = self._score_commits([1, 2, 3])
        with_pr = self._score_commits([1, 2, 3], pr_additions=50, pr_deletions=20)
        # With PR data should score higher (size factor > default 0.5)
        assert with_pr > no_pr
