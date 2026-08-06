"""Tests for the public demand board / private demand map (Issue #591).

The Worker implementation lives in workers/register-proxy.js and is exercised with
real logic by workers/register-proxy.test.mjs (`node --test`). These tests verify
the pieces pytest/CI can check directly: the required route wiring, the
aggregate-only privacy contract, the task-family whitelist, the maintainer-key
gate, and the public "Share your failure lesson" pointer.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestDemandBoardWorker(unittest.TestCase):
    def setUp(self):
        self.js = (REPO_ROOT / "workers" / "register-proxy.js").read_text(encoding="utf-8")

    def test_public_and_private_routes_exist(self):
        self.assertIn('"/api/insights/demand-board"', self.js)
        self.assertIn('"/api/insights/demand-map"', self.js)

    def test_task_family_whitelist_matches_issue(self):
        expected = [
            "github-auth", "npm-publish", "cloudflare-worker", "mcp-registry",
            "glama-release", "python-env", "database-lock", "crawler-block",
            "agent-tooling", "unclassified",
        ]
        for family in expected:
            self.assertIn(f'"{family}"', self.js)
        self.assertIn("TASK_FAMILY_WHITELIST", self.js)

    def test_public_response_declares_aggregate_only_meta(self):
        self.assertIn('r_level: "R1_descriptive"', self.js)
        self.assertIn('privacy: "aggregate-only"', self.js)
        self.assertIn("raw_query: false", self.js)
        self.assertIn("pii: false", self.js)

    def test_public_response_shape_matches_issue_schema(self):
        self.assertIn("windowDays", self.js)
        self.assertIn("summary:", self.js)
        self.assertIn("unsolved7d", self.js)
        self.assertIn("unsolved30d", self.js)
        self.assertIn("lastSeen", self.js)
        self.assertIn("actionUrl", self.js)

    def test_no_raw_query_or_pii_fields_are_plumbed_into_demand_code(self):
        demand_start = self.js.index("Demand board (Issue #591)")
        demand_section = self.js[demand_start:]
        for forbidden in ("rawQuery", "raw_prompt", "filePath", "user_email", "ip_address"):
            self.assertNotIn(forbidden, demand_section)

    def test_demand_map_requires_maintainer_key(self):
        self.assertIn("MAINTAINER_KEY", self.js)
        self.assertIn("X-Maintainer-Key", self.js)
        self.assertIn("timingSafeEqual", self.js)
        self.assertIn('{ error: "Unauthorized" }, 401', self.js)

    def test_demand_map_returns_bucket_shape_matching_issue_schema(self):
        self.assertIn("bucketDay", self.js)
        self.assertIn("unsolvedReason", self.js)
        self.assertIn("unsolvedCount", self.js)
        self.assertIn("distinctSourceCount", self.js)

    def test_source_ids_are_hashed_not_stored_raw(self):
        self.assertIn("hashSourceId", self.js)
        self.assertIn('crypto.subtle.digest("SHA-256"', self.js)

    def test_insights_routes_do_not_require_register_token(self):
        # The insights branch must be handled before the REGISTER_TOKEN guard,
        # otherwise the public board would 500 whenever the GitHub proxy token
        # isn't configured.
        token_guard_idx = self.js.index("REGISTER_TOKEN not configured on server")
        demand_board_idx = self.js.index('"/api/insights/demand-board"')
        self.assertLess(demand_board_idx, token_guard_idx)


class TestDemandBoardDiscoverability(unittest.TestCase):
    def test_readme_links_to_lesson_feedback(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Share your failure lesson", readme)
        self.assertIn("issues/new?template=lesson-feedback.yml", readme)

    def test_lesson_feedback_issue_template_exists(self):
        template = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "lesson-feedback.yml"
        self.assertTrue(template.exists())


if __name__ == "__main__":
    unittest.main()
