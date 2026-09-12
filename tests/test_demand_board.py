"""Tests for the public demand board (Issue #591).

These read the *deployed* worker source (`wrangler.toml` main = register-proxy-sw.js)
and check the pieces pytest can verify directly: the route wiring, the aggregate-only
privacy contract, and the public "Share your failure lesson" pointer.

History (2026-09-12): this file used to read `workers/register-proxy.js`, a 658-line
legacy copy that no workflow deploys, and asserted a design the live worker no longer
implements — `/api/insights/demand-map`, `TASK_FAMILY_WHITELIST`, bucketed unsolved
counts and the `MAINTAINER_KEY` gate. Those assertions (and the 17 node cases in
`workers/register-proxy.test.mjs`, which imported the same file) guarded code that
never ran, which is worse than no test at all: they stayed green while production
behaviour went unverified. The legacy file and its node suite are gone; what follows
describes the live worker. If the demand-map feature is wanted again, it belongs in
`register-proxy-sw.js` with tests pointing at it.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKER = REPO_ROOT / "workers" / "register-proxy-sw.js"


class TestDemandBoardWorker(unittest.TestCase):
    def setUp(self):
        self.js = WORKER.read_text(encoding="utf-8")

    def test_public_board_route_exists(self):
        self.assertIn('"/api/insights/demand-board"', self.js)

    def test_public_response_declares_aggregate_only_meta(self):
        self.assertIn('privacy: "aggregate-only"', self.js)
        self.assertIn("raw_query: false", self.js)
        self.assertIn("pii: false", self.js)

    def test_public_response_shape_matches_issue_schema(self):
        self.assertIn("windowDays", self.js)
        self.assertIn("unsolved7d", self.js)
        self.assertIn("unsolved30d", self.js)
        self.assertIn("lastSeen", self.js)

    def test_no_raw_query_or_pii_fields_are_plumbed_into_the_board(self):
        start = self.js.index("GET /api/insights/demand-board")
        section = self.js[start:start + 2000]
        for forbidden in ("rawQuery", "raw_prompt", "filePath", "user_email", "ip_address"):
            self.assertNotIn(forbidden, section, f"{forbidden} must not reach the public board")


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
