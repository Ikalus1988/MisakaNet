#!/usr/bin/env python3
"""`misakanet_me_inbox` — check an intake's status without re-submitting it.

Why this file was rewritten
---------------------------
The original tests patched `misakanet.server.handlers.inbox._query_d1`. **That name has never
existed**: `handle_me_inbox` calls the hosted worker over HTTP (`_url_request.urlopen`), because
the local server holds no durable state and cannot answer a status lookup on its own. The tests
and the handler came from different generations of the same change, so `test_me_inbox.py` failed
**6 of 13 at PR #2494's own head** — verified by running it on the PR's head, not only on the
rebased branch. The PR had been open 15 days without noticing.

The tests below therefore drive the real code path: a fake `urlopen` returning a body, an
`HTTPError`, or raising. Asserting on what the handler *would* do against a seam it does not have
is the "a gate that cannot fail" shape in a different costume — the patch target was unreachable,
so the tests were asserting `mock.assert_called()` on a mock the code never consulted.
"""
from __future__ import annotations

import io
import json
import tempfile
import urllib.error
from pathlib import Path
from unittest.mock import patch

from misakanet.server.handlers.inbox import handle_me_inbox

_URLOPEN = "misakanet.server.handlers.inbox._url_request.urlopen"


class _FakeResponse:
    """Minimal stand-in for the context manager `urlopen` returns."""

    def __init__(self, payload: bytes):
        self._buf = io.BytesIO(payload)

    def read(self):
        return self._buf.read()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _serving(payload):
    return patch(_URLOPEN, return_value=_FakeResponse(json.dumps(payload).encode()))


class TestMeInbox:
    def test_missing_both_params_returns_error(self):
        result = handle_me_inbox({})
        assert result == {"error": "intake_id or dedup_key is required"}

    def test_empty_params_returns_error(self):
        """Whitespace is not an id — it must not turn into a lookup for `' '`."""
        result = handle_me_inbox({"intake_id": "  ", "dedup_key": ""})
        assert "error" in result

    def test_a_resolved_answer_is_passed_through(self):
        body = {"intake_id": "issue-1", "status": "answered", "answer": "see the lesson"}
        with _serving(body):
            assert handle_me_inbox({"intake_id": "issue-1"}) == body

    def test_pending_is_returned_as_is(self):
        body = {"intake_id": "issue-1", "status": "pending"}
        with _serving(body):
            assert handle_me_inbox({"intake_id": "issue-1"})["status"] == "pending"

    def test_converted_carries_the_lesson_id(self):
        body = {"intake_id": "issue-2", "status": "converted", "lesson_id": "dco-auto-fix-workflow"}
        with _serving(body):
            got = handle_me_inbox({"intake_id": "issue-2"})
        assert got["lesson_id"] == "dco-auto-fix-workflow"

    def test_the_lookup_url_carries_the_argument_given(self):
        """The argument has to reach the query string, or the tool answers about nothing."""
        seen = {}

        def _capture(req, timeout=None):
            seen["url"] = req.full_url
            return _FakeResponse(b'{"status":"pending"}')

        with patch(_URLOPEN, _capture):
            handle_me_inbox({"dedup_key": "deadbeefdeadbeef"})
        assert "dedup_key=deadbeefdeadbeef" in seen["url"]
        assert seen["url"].startswith("https://misakanet.org/api/inbox?")

    def test_a_404_becomes_not_found_rather_than_an_error(self):
        err = urllib.error.HTTPError("u", 404, "Not Found", None, None)
        with patch(_URLOPEN, side_effect=err):
            got = handle_me_inbox({"intake_id": "issue-9"})
        assert got["status"] == "not_found"
        assert "error" not in got

    def test_another_http_status_is_unknown_with_the_code_said_out(self):
        err = urllib.error.HTTPError("u", 502, "Bad Gateway", None, None)
        with patch(_URLOPEN, side_effect=err):
            got = handle_me_inbox({"intake_id": "issue-9"})
        assert got["status"] == "unknown"
        assert "502" in got["error"]

    def test_an_unreachable_endpoint_degrades_instead_of_raising(self):
        """An agent must get a sentence it can act on, not a traceback."""
        with patch(_URLOPEN, side_effect=urllib.error.URLError("no route")):
            got = handle_me_inbox({"intake_id": "issue-9"})
        assert got["status"] == "unknown"
        assert got["note"]

    def test_malformed_json_degrades_instead_of_raising(self):
        with patch(_URLOPEN, return_value=_FakeResponse(b"<html>502</html>")):
            got = handle_me_inbox({"intake_id": "issue-9"})
        assert got["status"] == "unknown"

class TestSubmitIntakePollHint:
    """Test that submit_intake returns poll_hint and inbox_tool."""

    def test_submit_returns_poll_hint(self):
        """submit_intake response includes poll_hint and inbox_tool."""
        import os

        # Use temp dir for contribution queue
        test_dir = Path(tempfile.mkdtemp())
        os.environ["MISAKANET_CONTRIBUTION_QUEUE"] = str(test_dir / "queue.jsonl")

        try:
            from misakanet.server.handlers.submit import handle_submit_intake
            result = handle_submit_intake({
                "kind": "missing_lesson",
                "problem": "test problem for poll hint",
                "source": "test",
            })
            assert result.get("submitted") is True
            assert "poll_hint" in result
            assert "misakanet_me_inbox" in result["poll_hint"]
            assert result.get("inbox_tool") == "misakanet_me_inbox"
            assert "dedup_key" in result
            assert len(result["dedup_key"]) == 16  # SHA256 truncated to 16 chars
        finally:
            del os.environ["MISAKANET_CONTRIBUTION_QUEUE"]
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_question_poll_hint_mentions_hours(self):
        """Question kind → poll_hint mentions 24-48 hours."""
        import os

        test_dir = Path(tempfile.mkdtemp())
        os.environ["MISAKANET_CONTRIBUTION_QUEUE"] = str(test_dir / "queue.jsonl")

        try:
            from misakanet.server.handlers.submit import handle_submit_intake
            result = handle_submit_intake({
                "kind": "question",
                "problem": "how to configure X?",
                "source": "test",
            })
            assert "24-48 hours" in result["poll_hint"]
        finally:
            del os.environ["MISAKANET_CONTRIBUTION_QUEUE"]
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)


class TestMeInboxToolDefinition:
    """Test that the tool is properly registered."""

    def test_tool_in_tools_list(self):
        from misakanet.server.tools import TOOLS
        tool_names = [t["name"] for t in TOOLS]
        assert "misakanet_me_inbox" in tool_names

    def test_tool_has_required_fields(self):
        from misakanet.server.tools import TOOLS
        tool = next(t for t in TOOLS if t["name"] == "misakanet_me_inbox")
        assert "description" in tool
        assert "inputSchema" in tool
        assert "Input semantics" in tool["description"]
        assert "Output schema" in tool["description"]
        assert "Error cases" in tool["description"]

    def test_handler_registered(self):
        from misakanet.server.protocol import _HANDLERS
        assert "misakanet_me_inbox" in _HANDLERS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])