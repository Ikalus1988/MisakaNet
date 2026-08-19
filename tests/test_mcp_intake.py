"""
Tests for MisakaNet MCP intake — misakanet.mcp.intake_client
=============================================================

Covers:
  1. validate_intake_payload — all validation rules
  2. IntakePayload — construction, truncation, to_dict
  3. build_jsonrpc_call — JSON-RPC 2.0 format
  4. IntakeClient.search — mocked HTTP response
  5. IntakeClient.submit_intake — mocked success and error paths
  6. IntakeClient.submit_intake — network error handling

These tests are fully offline (no live HTTP calls).
"""

from __future__ import annotations

import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch, MagicMock

# ── Path setup ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from misakanet.mcp.intake_client import (
    IntakeClient,
    IntakePayload,
    validate_intake_payload,
    build_jsonrpc_call,
    MCP_ENDPOINT,
    MCP_PROTOCOL_VERSION,
    VALID_KINDS,
    MAX_FIELD_LEN,
    MAX_SOURCE_LEN,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_urlopen_mock(response_body: dict):
    """Return a context-manager mock that yields a urllib response."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_body).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ── 1. validate_intake_payload ───────────────────────────────────────────────


class TestValidateIntakePayload(unittest.TestCase):

    def test_valid_minimal_payload(self):
        errs = validate_intake_payload("missing_lesson", "pip install fails on WSL with SSL error")
        self.assertEqual(errs, [])

    def test_valid_full_payload(self):
        errs = validate_intake_payload(
            kind="stale_lesson",
            problem="pip install fails on WSL with SSL certificate error",
            error="ssl.SSLCertVerificationError",
            what_tried="pip install --trusted-host pypi.org",
            fix="pip install --cert /etc/ssl/certs/ca-certificates.crt",
            verification="pip install requests succeeds after applying fix",
            source="cursor-agent/1.0",
        )
        self.assertEqual(errs, [])

    def test_all_valid_kinds_accepted(self):
        for kind in VALID_KINDS:
            errs = validate_intake_payload(kind, "A valid problem description here")
            self.assertEqual(errs, [], f"Kind '{kind}' should be valid")

    def test_invalid_kind_rejected(self):
        errs = validate_intake_payload("bad_kind", "A valid problem description here")
        self.assertTrue(any("kind" in e.lower() or "bad_kind" in e for e in errs))

    def test_empty_problem_rejected(self):
        errs = validate_intake_payload("missing_lesson", "")
        self.assertTrue(any("problem" in e.lower() for e in errs))

    def test_short_problem_rejected(self):
        errs = validate_intake_payload("missing_lesson", "too short")
        self.assertTrue(any("10 character" in e for e in errs))

    def test_exactly_10_char_problem_accepted(self):
        errs = validate_intake_payload("missing_lesson", "1234567890")
        self.assertEqual(errs, [])

    def test_problem_exceeds_max_len(self):
        long_problem = "x" * (MAX_FIELD_LEN + 1)
        errs = validate_intake_payload("missing_lesson", long_problem)
        self.assertTrue(any("problem" in e and str(MAX_FIELD_LEN) in e for e in errs))

    def test_error_field_exceeds_max_len(self):
        errs = validate_intake_payload(
            "missing_lesson",
            "Valid problem description here",
            error="e" * (MAX_FIELD_LEN + 1),
        )
        self.assertTrue(any("error" in e for e in errs))

    def test_source_exceeds_max_len(self):
        errs = validate_intake_payload(
            "missing_lesson",
            "Valid problem description here",
            source="s" * (MAX_SOURCE_LEN + 1),
        )
        self.assertTrue(any("source" in e for e in errs))

    def test_none_problem_rejected(self):
        errs = validate_intake_payload("missing_lesson", None)  # type: ignore
        self.assertTrue(any("problem" in e.lower() for e in errs))

    def test_multiple_errors_returned(self):
        """Invalid kind AND short problem → at least 2 errors."""
        errs = validate_intake_payload("bad", "hi")
        self.assertGreaterEqual(len(errs), 2)


# ── 2. IntakePayload ─────────────────────────────────────────────────────────


class TestIntakePayload(unittest.TestCase):

    def test_valid_payload_constructed(self):
        p = IntakePayload("missing_lesson", "A problem longer than ten characters")
        self.assertEqual(p.kind, "missing_lesson")
        self.assertIn("problem", p.to_dict())

    def test_invalid_payload_raises_value_error(self):
        with self.assertRaises(ValueError):
            IntakePayload("bad_kind", "A valid problem here")

    def test_problem_exceeds_max_len_raises(self):
        """IntakePayload validates before truncating — oversized problem raises."""
        long_problem = "A" * (MAX_FIELD_LEN + 500)
        with self.assertRaises(ValueError) as ctx:
            IntakePayload("missing_lesson", long_problem)
        self.assertIn("problem", str(ctx.exception))

    def test_source_exceeds_max_len_raises(self):
        """IntakePayload validates before truncating — oversized source raises."""
        long_source = "s" * (MAX_SOURCE_LEN + 50)
        with self.assertRaises(ValueError) as ctx:
            IntakePayload("missing_lesson", "Valid problem description", source=long_source)
        self.assertIn("source", str(ctx.exception))

    def test_to_dict_omits_empty_fields(self):
        p = IntakePayload("missing_lesson", "A problem that is long enough")
        d = p.to_dict()
        self.assertIn("kind", d)
        self.assertIn("problem", d)
        # optional fields not set → not in dict
        self.assertNotIn("error", d)
        self.assertNotIn("what_tried", d)

    def test_to_dict_includes_optional_fields_when_set(self):
        p = IntakePayload(
            "missing_lesson",
            "A problem that is long enough",
            error="Some error message",
            fix="Some fix",
        )
        d = p.to_dict()
        self.assertIn("error", d)
        self.assertIn("fix", d)

    def test_all_kinds_accepted(self):
        for kind in VALID_KINDS:
            p = IntakePayload(kind, "A problem that is long enough")
            self.assertEqual(p.kind, kind)


# ── 3. build_jsonrpc_call ────────────────────────────────────────────────────


class TestBuildJsonrpcCall(unittest.TestCase):

    def test_jsonrpc_version(self):
        body = build_jsonrpc_call("tools/list", {})
        data = json.loads(body)
        self.assertEqual(data["jsonrpc"], "2.0")

    def test_method_included(self):
        body = build_jsonrpc_call("tools/call", {"name": "test"})
        data = json.loads(body)
        self.assertEqual(data["method"], "tools/call")

    def test_params_included(self):
        params = {"name": "misakanet_search", "arguments": {"query": "pip"}}
        body = build_jsonrpc_call("tools/call", params)
        data = json.loads(body)
        self.assertEqual(data["params"]["name"], "misakanet_search")

    def test_default_id_is_1(self):
        body = build_jsonrpc_call("tools/list", {})
        data = json.loads(body)
        self.assertEqual(data["id"], 1)

    def test_custom_id(self):
        body = build_jsonrpc_call("tools/list", {}, req_id=42)
        data = json.loads(body)
        self.assertEqual(data["id"], 42)

    def test_returns_bytes(self):
        body = build_jsonrpc_call("tools/list", {})
        self.assertIsInstance(body, bytes)

    def test_valid_json(self):
        body = build_jsonrpc_call("tools/call", {"key": "value"})
        # Should not raise
        data = json.loads(body)
        self.assertIn("jsonrpc", data)


# ── 4. IntakeClient.search ───────────────────────────────────────────────────


class TestIntakeClientSearch(unittest.TestCase):

    def _mock_search_response(self, text: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [{"type": "text", "text": text}]
            },
        }

    @patch("urllib.request.urlopen")
    def test_search_returns_lessons(self, mock_urlopen):
        text = (
            "Found 2 lessons:\n"
            "- [rag] ChromaDB crash on NTFS (lessons/rag-chromadb-ntfs.md)\n"
            "- [devops] WSL terminal underscore corruption (lessons/wsl-terminal.md)\n"
            "\nIf none match, use misakanet_submit_intake."
        )
        mock_urlopen.return_value = _make_urlopen_mock(self._mock_search_response(text))
        client = IntakeClient()
        results = client.search("chromadb ntfs")
        self.assertEqual(len(results), 2)
        self.assertIn("ChromaDB", results[0]["raw"])

    @patch("urllib.request.urlopen")
    def test_search_returns_empty_on_no_match(self, mock_urlopen):
        text = 'No lessons found for "unknown query". Use misakanet_submit_intake.'
        mock_urlopen.return_value = _make_urlopen_mock(self._mock_search_response(text))
        client = IntakeClient()
        results = client.search("unknown query nobody has this")
        self.assertEqual(results, [])

    @patch("urllib.request.urlopen")
    def test_search_sends_correct_method(self, mock_urlopen):
        mock_urlopen.return_value = _make_urlopen_mock(
            self._mock_search_response("No lessons found.")
        )
        client = IntakeClient()
        client.search("pip timeout")

        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        body = json.loads(req.data)
        self.assertEqual(body["method"], "tools/call")
        self.assertEqual(body["params"]["name"], "misakanet_search")
        self.assertEqual(body["params"]["arguments"]["query"], "pip timeout")


# ── 5. IntakeClient.submit_intake ────────────────────────────────────────────


class TestIntakeClientSubmitIntake(unittest.TestCase):

    def _success_response(self) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "submitted": True,
                "intake_id": "issue-1234",
                "status": "pending_review",
                "issue_url": "https://github.com/Ikalus1988/MisakaNet/issues/1234",
                "content": [
                    {
                        "type": "text",
                        "text": "Intake submitted successfully.\n\nintake_id: issue-1234",
                    }
                ],
            },
        }

    @patch("urllib.request.urlopen")
    def test_submit_returns_intake_id(self, mock_urlopen):
        mock_urlopen.return_value = _make_urlopen_mock(self._success_response())
        client = IntakeClient()
        result = client.submit_intake(
            "missing_lesson",
            "pip install fails on macOS with SSL certificate error in CI",
            source="test-agent",
        )
        self.assertTrue(result["submitted"])
        self.assertEqual(result["intake_id"], "issue-1234")
        self.assertEqual(result["status"], "pending_review")
        self.assertIn("github.com", result["issue_url"])

    @patch("urllib.request.urlopen")
    def test_submit_sends_correct_method(self, mock_urlopen):
        mock_urlopen.return_value = _make_urlopen_mock(self._success_response())
        client = IntakeClient()
        client.submit_intake(
            "missing_lesson",
            "A problem that is longer than ten chars",
        )
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data)
        self.assertEqual(body["method"], "tools/call")
        self.assertEqual(body["params"]["name"], "misakanet_submit_intake")
        self.assertIn("kind", body["params"]["arguments"])
        self.assertEqual(body["params"]["arguments"]["kind"], "missing_lesson")

    @patch("urllib.request.urlopen")
    def test_submit_sends_mcp_protocol_header(self, mock_urlopen):
        mock_urlopen.return_value = _make_urlopen_mock(self._success_response())
        client = IntakeClient()
        client.submit_intake("missing_lesson", "A valid problem description here")
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_header("Mcp-protocol-version"), MCP_PROTOCOL_VERSION)

    @patch("urllib.request.urlopen")
    def test_submit_raises_on_rpc_error(self, mock_urlopen):
        error_resp = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32602, "message": "problem is required"},
        }
        mock_urlopen.return_value = _make_urlopen_mock(error_resp)
        client = IntakeClient()
        with self.assertRaises(RuntimeError) as ctx:
            client.submit_intake("missing_lesson", "A problem that is long enough")
        self.assertIn("-32602", str(ctx.exception))

    def test_submit_validates_locally_before_network(self):
        """Invalid payload → ValueError before any HTTP call."""
        client = IntakeClient()
        with self.assertRaises(ValueError):
            client.submit_intake("bad_kind", "Too short")

    @patch("urllib.request.urlopen")
    def test_submit_full_payload(self, mock_urlopen):
        mock_urlopen.return_value = _make_urlopen_mock(self._success_response())
        client = IntakeClient()
        result = client.submit_intake(
            kind="stale_lesson",
            problem="ChromaDB on NTFS crashes on SQLite open — lesson is outdated",
            error="sqlite3.OperationalError: unable to open database file",
            what_tried="Upgraded ChromaDB to 0.5.0 — still fails",
            fix="Move DB to ext4 partition: mv ~/.chromadb /mnt/ext4/",
            verification="python3 -c \"import chromadb; c=chromadb.Client(); print(c.heartbeat())\"",
            source="cursor-agent/2.0",
        )
        self.assertTrue(result["submitted"])

        req = mock_urlopen.call_args[0][0]
        args = json.loads(req.data)["params"]["arguments"]
        self.assertEqual(args["kind"], "stale_lesson")
        self.assertIn("source", args)
        self.assertEqual(args["source"], "cursor-agent/2.0")


# ── 6. Network error handling ────────────────────────────────────────────────


class TestIntakeClientNetworkErrors(unittest.TestCase):

    @patch("urllib.request.urlopen")
    def test_network_timeout_propagates(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("timed out")
        client = IntakeClient()
        with self.assertRaises(urllib.error.URLError):
            client.search("any query here that matters")

    @patch("urllib.request.urlopen")
    def test_http_error_response_parsed(self, mock_urlopen):
        """HTTP 500 from the server — urlopen raises HTTPError, client reads the body."""
        import urllib.error
        err_body = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "Server error"}}
        ).encode()
        http_err = urllib.error.HTTPError(
            MCP_ENDPOINT, 500, "Internal Server Error",
            {}, BytesIO(err_body)
        )
        # HTTPError is raised by urlopen; the client catches it and reads the body
        mock_urlopen.side_effect = http_err
        client = IntakeClient()
        # submit_intake should raise RuntimeError wrapping the -32000 code
        with self.assertRaises(RuntimeError) as ctx:
            client.submit_intake("missing_lesson", "A valid problem description here")
        self.assertIn("-32000", str(ctx.exception))


# ── Doctest sanity check ─────────────────────────────────────────────────────


class TestModuleConstants(unittest.TestCase):
    def test_endpoint_is_https(self):
        self.assertTrue(MCP_ENDPOINT.startswith("https://"))

    def test_protocol_version_format(self):
        # Must be ISO-date-like
        import re
        self.assertRegex(MCP_PROTOCOL_VERSION, r"^\d{4}-\d{2}-\d{2}$")

    def test_valid_kinds_non_empty(self):
        self.assertGreater(len(VALID_KINDS), 0)
        for k in VALID_KINDS:
            self.assertIsInstance(k, str)


if __name__ == "__main__":
    unittest.main()
