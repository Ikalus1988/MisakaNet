"""Contract test for issue #1363's ``question`` intake kind.

Run against the deployed MCP endpoint with::

    MISAKANET_MCP_URL=https://misakanet.org/mcp pytest -q \
        tests/test_issue_1363_question_intake.py

The test is opt-in so normal CI never creates a real intake issue.
"""
import json
import os
import urllib.request

import pytest


MCP_URL = os.getenv("MISAKANET_MCP_URL")
pytestmark = pytest.mark.skipif(not MCP_URL, reason="set MISAKANET_MCP_URL for live MCP contract test")


def call_tool(name, arguments, request_id=1):
    assert MCP_URL is not None
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    request = urllib.request.Request(
        MCP_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "MisakaNet-issue-1363-contract-test/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        assert response.status == 200
        return json.loads(response.read())


def test_question_kind_is_accepted_and_structured():
    """A question is accepted and returned as a created, structured intake."""
    result = call_tool(
        "misakanet_submit_intake",
        {
            "kind": "question",
            "problem": "How do I configure MCP server authentication for production?",
            "source": "issue-1363-contract-test",
        },
    )
    assert "error" not in result, result
    text = result["result"]["content"][0]["text"]
    response = json.loads(text)
    assert response["submitted"] is True
    assert response["intake_id"]
    assert "github issue" in response["receipt"].lower()



def test_search_response_is_valid_json():
    """The deployed search tool returns a parseable result envelope."""
    result = call_tool(
        "misakanet_search",
        {"query": "quantum computing error correction"},
        request_id=2,
    )
    text = result["result"]["content"][0]["text"]
    response = json.loads(text)
    assert isinstance(response["results"], list)
    assert response["query"] == "quantum computing error correction"
