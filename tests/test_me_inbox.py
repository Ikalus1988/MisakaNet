#!/usr/bin/env python3
"""`misakanet_me_inbox` — check an intake's status without re-submitting it.

Why this file was rewritten again (2026-11-03, #3577)
-----------------------------------------------------
The 2026-10-20 rewrite replaced a patch target that never existed (`_query_d1`) with the real one,
`_url_request.urlopen` — and the tests then passed against a URL that 404s in production:

    GET https://misakanet.org/api/inbox?intake_id=issue-1528  ->  404 {"error":"Not found"}

There is no `/api/inbox` route in the worker (`grep` for it in `workers/register-proxy-sw.js`
finds only the MCP tool). So every stdio lookup that was not in the local contribution queue
answered `status: "not_found"`, while the hosted tool answered `status: "unknown"` with the reason:

    stdio   {"intake_id": "issue-1528", "status": "not_found",
             "note": "No intake found with this ID or dedup_key."}
    hosted  {"intake_id": "issue-1528", "status": "unknown",
             "note": "Nothing found in the D1 question table, the lesson corpus, or the dedup
                      store. Read this as 'cannot be determined', not 'never happened' ..."}

Mocking the wrong seam is how both generations of this test stayed green: the first mocked a
function that did not exist, the second mocked a request that reaches nothing. The handler now
forwards to the hosted `misakanet_me_inbox` tool through `misakanet/remote.py` — the same MCP
client `me_events` uses — so these tests patch `remote.call`, which is the seam the code has.

What is pinned:
1. the forwarded tool name and argument names are the hosted ones (a renamed argument here would
   silently look up nothing);
2. a hosted payload is returned unchanged, including the hosted `unknown` status;
3. a network failure is reported as an unreachable endpoint, never as `not_found` — "cannot be
   determined" and "never happened" are different answers and only one of them was true;
4. a locally queued intake is answered from the local queue without a network call.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest  # the __main__ block below

from misakanet.server.handlers.inbox import handle_me_inbox

_REMOTE_CALL = "misakanet.remote.call"


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
        with patch(_REMOTE_CALL, return_value=body):
            assert handle_me_inbox({"intake_id": "issue-1"}) == body

    def test_pending_is_returned_as_is(self):
        body = {"intake_id": "issue-1", "status": "pending"}
        with patch(_REMOTE_CALL, return_value=body):
            assert handle_me_inbox({"intake_id": "issue-1"})["status"] == "pending"

    def test_converted_carries_the_lesson_id(self):
        body = {"intake_id": "issue-2", "status": "converted", "lesson_id": "dco-auto-fix-workflow"}
        with patch(_REMOTE_CALL, return_value=body):
            got = handle_me_inbox({"intake_id": "issue-2"})
        assert got["lesson_id"] == "dco-auto-fix-workflow"

    def test_a_hosted_unknown_is_passed_through_instead_of_becoming_not_found(self):
        """The hosted tool's honest "cannot be determined" must survive the proxy."""
        body = {"intake_id": "issue-1528", "status": "unknown",
                "note": "Read this as 'cannot be determined', not 'never happened'."}
        with patch(_REMOTE_CALL, return_value=body):
            got = handle_me_inbox({"intake_id": "issue-1528"})
        assert got["status"] == "unknown"
        assert "cannot be determined" in got["note"]

    def test_it_calls_the_hosted_tool_with_the_same_argument_names(self):
        """A renamed argument looks up nothing and answers `unknown` about a real intake."""
        seen = {}

        def _capture(tool, arguments, **kwargs):
            seen["tool"] = tool
            seen["arguments"] = arguments
            seen["timeout"] = kwargs.get("timeout")
            return {"intake_id": "dedup-deadbeef", "status": "pending"}

        with patch(_REMOTE_CALL, _capture):
            handle_me_inbox({"dedup_key": "deadbeef"})
        assert seen["tool"] == "misakanet_me_inbox"
        assert seen["arguments"] == {"dedup_key": "deadbeef"}
        assert seen["timeout"] and seen["timeout"] > 0

    def test_an_unreachable_endpoint_is_unknown_not_not_found(self):
        """This is the whole defect: a failed read used to be reported as a missing intake."""
        with patch(_REMOTE_CALL, side_effect=OSError("connection refused")):
            got = handle_me_inbox({"intake_id": "issue-9"})
        assert got["status"] == "unknown"
        assert got["error"] == "hosted_endpoint_unavailable"
        assert "connection refused" in got["note"]
        assert "nothing about whether the intake exists" in got["note"]

    def test_a_non_payload_reply_degrades_instead_of_raising(self):
        with patch(_REMOTE_CALL, return_value=["not", "a", "dict"]):
            got = handle_me_inbox({"intake_id": "issue-9"})
        assert got["status"] == "unknown"
        assert got["error"] == "unexpected_reply"

    def test_a_locally_queued_intake_is_answered_without_a_network_call(self):
        """A `contrib_…` id exists only on this machine; the hosted service cannot know it."""
        import scripts.contribution_queue as contribution_queue
        from misakanet.server.handlers.submit import handle_submit_intake

        queue = Path(tempfile.mkdtemp()) / "queue.jsonl"
        with patch.object(contribution_queue, "QUEUE_FILE", queue), patch.dict(
            "os.environ", {"MISAKANET_INTAKE_DISABLE_REMOTE": "1"}
        ):
            receipt = handle_submit_intake({
                "kind": "missing_lesson", "problem": "local only", "source": "test"})
            with patch(_REMOTE_CALL) as call:
                got = handle_me_inbox({"intake_id": receipt["intake_id"]})
        assert not call.called, "a local id must not be sent to the hosted endpoint"
        assert got["delivery"] == "local_queue"
        assert got["intake_id"] == receipt["intake_id"]


class TestSubmitIntakePollHint:
    """`submit_intake` returns a poll hint that can actually be followed.

    The hint used to be a sentence naming `misakanet_me_inbox`, and the intake it pointed at was a
    local queue id the hosted endpoint has never heard of — so the sentence promised a lookup that
    could only answer "not found". The hint is now the same object shape the hosted endpoint
    returns, and `me_inbox` answers locally queued intakes from the local queue.
    """

    def test_submit_returns_poll_hint(self):
        """submit_intake response includes a poll hint naming the inbox tool."""
        import scripts.contribution_queue as contribution_queue

        queue = Path(tempfile.mkdtemp()) / "queue.jsonl"
        with patch.object(contribution_queue, "QUEUE_FILE", queue):
            from misakanet.server.handlers.submit import handle_submit_intake
            result = handle_submit_intake({
                "kind": "missing_lesson",
                "problem": "test problem for poll hint",
                "source": "test",
            })
        assert result.get("submitted") is True
        assert result.get("delivery") == "local_queue"
        assert "poll_hint" in result
        assert result["poll_hint"]["tool"] == "misakanet_me_inbox"
        assert result["intake_id"] in result["poll_hint"]["argument"]
        assert "dedup_key" in result
        assert len(result["dedup_key"]) == 16  # the local queue's SHA-256 prefix, not the worker's

    def test_question_poll_hint_carries_the_recheck_clock(self):
        """Question kind → the hosted endpoint's own advice: 21600s, not a sentence."""
        import scripts.contribution_queue as contribution_queue

        queue = Path(tempfile.mkdtemp()) / "queue.jsonl"
        with patch.object(contribution_queue, "QUEUE_FILE", queue):
            from misakanet.server.handlers.submit import handle_submit_intake
            result = handle_submit_intake({
                "kind": "question",
                "problem": "how to configure X?",
                "source": "test",
            })
        assert result["poll_hint"]["recheck_after_seconds"] == 21600
        assert result["poll_hint"]["how"]


class TestMeInboxToolDefinition:
    """The local definition has to describe what the tool actually returns."""

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

    def test_the_description_names_the_statuses_the_tool_can_return(self):
        """It used to describe `me_events` (`events[]`, `poll_hint`) — the wrong tool's shape."""
        from misakanet.server.tools import TOOLS
        description = next(
            t for t in TOOLS if t["name"] == "misakanet_me_inbox")["description"]
        for status in ("answered", "pending", "converted", "unknown"):
            assert status in description, status
        assert "events[]" not in description, "me_inbox returns no events[] — that is me_events"
        assert "events" not in description.split("Output schema")[1].split("Error cases")[0]

    def test_handler_registered(self):
        from misakanet.server.protocol import _HANDLERS
        assert "misakanet_me_inbox" in _HANDLERS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
