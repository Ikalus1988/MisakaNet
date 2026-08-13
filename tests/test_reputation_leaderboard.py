"""Static contract tests for the contributor reputation leaderboard (#908)."""

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PAGE = REPO_ROOT / "docs" / "insights" / "reputation-leaderboard.html"
WORKER = REPO_ROOT / "workers" / "register-proxy-sw.js"


class TestReputationLeaderboardPage(unittest.TestCase):
    def setUp(self):
        self.html = PAGE.read_text(encoding="utf-8")
        self.worker = WORKER.read_text(encoding="utf-8")

    def test_page_and_endpoint_are_wired(self):
        self.assertTrue(PAGE.exists())
        self.assertIn("/api/insights/reputation-leaderboard", self.html)
        self.assertIn('value="all-time"', self.html)
        self.assertIn('value="monthly"', self.html)
        self.assertIn('value="weekly"', self.html)
        self.assertIn('url.pathname === "/api/insights/reputation-leaderboard"', self.worker)

    def test_page_is_responsive_and_self_contained(self):
        self.assertIn("@media (max-width: 520px)", self.html)
        self.assertNotIn("<script src=", self.html)
        self.assertNotIn("cdn.", self.html)
        self.assertIn("function escapeHTML", self.html)

    def test_page_discloses_non_monetary_points(self):
        self.assertIn("no cash value", self.html.lower())
        self.assertIn('cashValue: false', self.worker)
        self.assertIn('pointsSource: "data/contributor-points.json"', self.worker)

    def test_backend_caps_and_filters_the_public_shape(self):
        self.assertIn("REPUTATION_MAX_ENTRIES = 20", self.worker)
        self.assertIn('"all-time": null', self.worker)
        self.assertIn("historyPoints", self.worker)
        self.assertIn("totalPoints", self.worker)


if __name__ == "__main__":
    unittest.main()
