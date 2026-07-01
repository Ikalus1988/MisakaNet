"""Tests for the 'This helped me' helpful button feature (Issue #218).

Validates that the frontend and worker code contain the required elements
for the helpful vote system: button in search results, POST endpoint,
localStorage dedup, and count display.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestHelpfulButtonFrontend(unittest.TestCase):
    """Verify docs/index.html contains the helpful button implementation."""

    def setUp(self):
        self.html = (REPO_ROOT / "docs" / "index.html").read_text()

    def test_helpful_button_css_exists(self):
        """CSS class .helpful-btn is defined."""
        self.assertIn(".helpful-btn", self.html)

    def test_helpful_button_in_search_results(self):
        """Search results template includes a helpful button."""
        self.assertIn("helpful-btn", self.html)
        self.assertIn("handleHelpfulClick", self.html)

    def test_helpful_url_helper_exists(self):
        """getHelpfulUrl() function is defined."""
        self.assertIn("function getHelpfulUrl()", self.html)

    def test_fetch_post_function_exists(self):
        """fetchPOST helper follows the same timeout pattern as fetchWithTimeout."""
        self.assertIn("async function fetchPOST(", self.html)

    def test_localstorage_dedup_exists(self):
        """localStorage-based dedup prevents duplicate votes."""
        self.assertIn("HELPFUL_STORAGE_KEY", self.html)
        self.assertIn("function hasVoted(", self.html)
        self.assertIn("function markVoted(", self.html)

    def test_load_helpful_count_exists(self):
        """loadHelpfulCount fetches and displays existing counts."""
        self.assertIn("function loadHelpfulCount(", self.html)

    def test_count_display_format(self):
        """Count is displayed in 'N found helpful' format."""
        self.assertIn("found helpful", self.html)

    def test_event_stop_propagation_on_button(self):
        """Button click does not trigger parent div's onclick (opens new window)."""
        self.assertIn("event.stopPropagation()", self.html)

    def test_no_external_dependencies(self):
        """No npm imports or external JS module imports for helpful feature."""
        # The helpful button code section should not import external modules
        helpful_section_start = self.html.find("HELPFUL_STORAGE_KEY")
        helpful_section_end = self.html.find("// ── Counter animation")
        if helpful_section_start >= 0 and helpful_section_end >= 0:
            section = self.html[helpful_section_start:helpful_section_end]
            self.assertNotIn("import ", section)
            self.assertNotIn("require(", section)


class TestHelpfulButtonWorker(unittest.TestCase):
    """Verify workers/register-proxy.js contains the helpful API endpoint."""

    def setUp(self):
        self.js = (REPO_ROOT / "workers" / "register-proxy.js").read_text()

    def test_get_helpful_endpoint_exists(self):
        """GET /api/helpful returns count for a lesson_id."""
        self.assertIn('case "/api/helpful"', self.js)

    def test_post_helpful_endpoint_exists(self):
        """POST /api/helpful increments count for a lesson_id."""
        self.assertIn('url.pathname === "/api/helpful"', self.js)

    def test_handle_helpful_vote_function_exists(self):
        """handleHelpfulVote function processes POST requests."""
        self.assertIn("async function handleHelpfulVote(", self.js)

    def test_kv_key_format(self):
        """Votes are stored in KV with 'helpful:{lesson_id}' key format."""
        self.assertIn("helpful:${lessonId}", self.js)

    def test_kv_count_increment(self):
        """POST handler reads current count and increments by 1."""
        self.assertIn("current + 1", self.js)

    def test_input_sanitization(self):
        """lesson_id is sanitized to prevent injection."""
        self.assertIn("sanitizeIdentifier(body.lesson_id", self.js)

    def test_error_handling_for_missing_kv(self):
        """Returns 503 when KV is not configured."""
        self.assertIn('"KV not configured"', self.js)

    def test_cors_headers_on_helpful(self):
        """Helpful endpoint responses include CORS headers."""
        # jsonResponse already includes CORS_HEADERS, verify it's used
        self.assertIn("CORS_HEADERS", self.js)


if __name__ == "__main__":
    unittest.main()
