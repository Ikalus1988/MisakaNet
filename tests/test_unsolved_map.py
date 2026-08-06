"""Tests for the privacy-preserving unsolved failure map (Issue #788).

Behaviour is exercised by workers/unsolved-map.test.mjs (`node --test`), which
this module runs when Node is available. The rest pins the privacy contract:
only derived family labels and enum reasons may be stored or emitted.
"""

import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKER = REPO_ROOT / "workers" / "register-proxy-sw.js"
NODE_TESTS = REPO_ROOT / "workers" / "unsolved-map.test.mjs"
SEARCH_PAGE = REPO_ROOT / "docs" / "search" / "index.html"
MAP_PAGE = REPO_ROOT / "docs" / "insights" / "unsolved-map.html"


class TestUnsolvedMapWorker(unittest.TestCase):
    def setUp(self):
        self.js = WORKER.read_text(encoding="utf-8")
        start = self.js.index("Unsolved failure map (Issue #788)")
        end = self.js.index("async function probeKeepaliveEndpoint")
        self.section = self.js[start:end]

    def test_endpoints_exist(self):
        self.assertIn('url.pathname === "/api/insights/unsolved-map"', self.js)
        self.assertIn('url.pathname === "/api/search-signal"', self.js)

    def test_reason_enum_matches_the_issue(self):
        for reason in ("no_match", "low_confidence", "not_helpful"):
            self.assertIn(f'"{reason}"', self.section)
        self.assertIn("function normalizeUnsolvedReason(", self.section)

    def test_family_labels_are_derived_not_user_supplied(self):
        """Labels come from the keyword table, never from request fields."""
        self.assertIn("function classifyTaskFamily(", self.section)
        self.assertIn("classifyTaskFamily(query)", self.js)
        self.assertNotIn("body.task_family", self.js)
        self.assertNotIn("body.taskFamily", self.js)

    def test_query_is_never_persisted_by_the_signal_endpoint(self):
        """The KV writes in the signal path must not carry the query."""
        handler = self.section[self.section.index("async function handleSearchSignal("):]
        kv_writes = re.findall(r"MISAKANET_KV\.put\(([^;]+)\)", handler)
        for write in kv_writes:
            self.assertNotIn("query", write, f"query must not be written to KV: {write}")

    def test_output_declares_the_privacy_contract(self):
        self.assertIn('privacy: "aggregate-only"', self.section)
        for field in ("raw_query: false", "prompts: false", "logs: false", "paths: false", "pii: false"):
            self.assertIn(field, self.section)

    def test_window_and_pruning(self):
        self.assertIn("const UNSOLVED_WINDOW_DAYS = 30", self.section)
        self.assertIn("function pruneUnsolvedDays(", self.section)

    def test_signal_endpoint_is_rate_limited_and_size_capped(self):
        handler = self.section[self.section.index("async function handleSearchSignal("):]
        self.assertIn("rate:signal:", handler)
        self.assertIn("429", handler)
        self.assertIn("413", handler)

    def test_logging_never_includes_the_query(self):
        for line in re.findall(r"console\.log\(`\[unsolved\][^`]*`\)", self.section):
            self.assertNotIn("query", line)


class TestUnsolvedMapFrontend(unittest.TestCase):
    def test_search_page_reports_only_unsolved_searches(self):
        html = SEARCH_PAGE.read_text(encoding="utf-8")
        self.assertIn("/api/search-signal", html)
        self.assertIn("function reportUnsolvedSearch(", html)
        # Solved searches return before the fetch.
        body = html[html.index("function reportUnsolvedSearch("):]
        self.assertIn("return; // solved", body)

    def test_public_page_exists_and_states_the_privacy_rules(self):
        self.assertTrue(MAP_PAGE.exists(), "docs/insights/unsolved-map.html is the public view for #788")
        html = MAP_PAGE.read_text(encoding="utf-8")
        self.assertIn("/api/insights/unsolved-map", html)
        self.assertIn("aggregate counts only", html.lower())
        self.assertIn("escapeHTML", html, "rendered values must be escaped")

    def test_public_page_has_no_external_dependencies(self):
        html = MAP_PAGE.read_text(encoding="utf-8")
        self.assertNotIn("<script src=", html)
        self.assertNotIn("cdn.", html)


@unittest.skipIf(shutil.which("node") is None, "node is not installed")
class TestUnsolvedMapBehaviour(unittest.TestCase):
    def test_node_unit_tests_pass(self):
        result = subprocess.run(
            ["node", "--test", str(NODE_TESTS)],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
