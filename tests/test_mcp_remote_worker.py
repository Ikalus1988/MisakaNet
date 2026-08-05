"""Tests for the remote MCP endpoint on the Cloudflare Worker (Issue #804).

Real request/response behaviour is exercised by workers/mcp-remote.test.mjs
(`node --test`), which this module runs when Node is available. The remaining
tests pin the contract that must not silently drift: route wiring, the Phase 1
read-only tool set, the auth/Origin gates, and the version fallback.
"""

import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKER = REPO_ROOT / "workers" / "register-proxy-sw.js"
NODE_TESTS = REPO_ROOT / "workers" / "mcp-remote.test.mjs"


class TestMcpWorkerContract(unittest.TestCase):
    def setUp(self):
        self.js = WORKER.read_text(encoding="utf-8")

    def test_mcp_route_is_wired_for_post_options_and_405(self):
        self.assertIn('const MCP_PATH = "/mcp"', self.js)
        self.assertIn("return handleMcpRequest(request, env)", self.js)
        self.assertIn("return mcpMethodNotAllowed(request, env)", self.js)
        self.assertIn('"Accept-Post": "application/json"', self.js)

    def test_mcp_route_precedes_the_catch_all_get_landing_page(self):
        """GET /mcp must 405 rather than fall through to the HTML page."""
        self.assertLess(
            self.js.index("url.pathname === MCP_PATH"),
            self.js.index("// Catch-all GET — landing page"),
        )

    def test_bearer_auth_uses_a_timing_safe_comparison(self):
        self.assertIn("function mcpTimingSafeEqual(", self.js)
        self.assertIn("mcpTimingSafeEqual(mcpBearerToken(request), String(env.MCP_TOKEN))", self.js)
        self.assertIn("401", self.js)

    def test_origin_allowlist_blocks_dns_rebinding(self):
        self.assertIn("MCP_ALLOWED_ORIGINS", self.js)
        self.assertIn("Forbidden origin", self.js)
        for origin in ("https://misakanet.org", "https://claude.ai", "https://glama.ai"):
            self.assertIn(f'"{origin}"', self.js)

    def test_phase_one_is_read_only(self):
        self.assertIn('name: "misakanet_search"', self.js)
        self.assertIn('name: "misakanet_get_lesson"', self.js)
        # Write tools are Phase 2 — they must not be reachable yet.
        self.assertNotIn("misakanet_submit_usage", self.js)
        self.assertNotIn("misakanet_usage_status", self.js)

    def test_protocol_versions_cover_the_spec_and_the_rc(self):
        self.assertIn('"2025-06-18"', self.js)
        self.assertIn('"2026-07-28"', self.js)
        self.assertIn("MCP_DEFAULT_PROTOCOL", self.js)

    def test_lesson_paths_are_restricted_to_lesson_markdown(self):
        self.assertIn("function mcpSafeLessonPath(", self.js)
        self.assertIn('if (path.includes("..")) return null;', self.js)
        self.assertIn(r"^lessons\/[A-Za-z0-9._/-]+\.md$", self.js)

    def test_no_hardcoded_mcp_token(self):
        """The token only ever comes from env."""
        for match in re.finditer(r"MCP_TOKEN\s*[:=]\s*(.+)", self.js):
            tail = match.group(1).strip()
            self.assertFalse(
                tail.startswith(('"', "'")),
                f"MCP_TOKEN must be read from env, found literal: {tail[:40]}",
            )

    def test_version_fallback_matches_pyproject(self):
        """MCP_VERSION defaults to the packaged version (issue #804 spec)."""
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        version = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', pyproject, re.MULTILINE).group(1)
        self.assertIn(f'const MCP_FALLBACK_VERSION = "{version}"', self.js)
        self.assertIn("env.MCP_VERSION || MCP_FALLBACK_VERSION", self.js)


class TestMcpWorkerDocs(unittest.TestCase):
    def test_connection_doc_exists_and_documents_the_endpoint(self):
        doc = REPO_ROOT / "docs" / "integrations" / "mcp-remote.md"
        self.assertTrue(doc.exists(), "docs/integrations/mcp-remote.md is required by #804")
        text = doc.read_text(encoding="utf-8")
        self.assertIn("https://misakanet.org/mcp", text)
        self.assertIn("Authorization: Bearer", text)
        self.assertIn("misakanet_search", text)
        self.assertIn("misakanet_get_lesson", text)


@unittest.skipIf(shutil.which("node") is None, "node is not installed")
class TestMcpWorkerBehaviour(unittest.TestCase):
    def test_node_unit_tests_pass(self):
        result = subprocess.run(
            ["node", "--test", str(NODE_TESTS)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
