"""One reader for an MCP reply, whatever frame it arrived in (#3548).

The endpoint answers plain JSON to `Accept: application/json` and SSE to an `Accept` that mentions
`text/event-stream`; the payload inside is byte-identical (measured 2026-10-19). A caller that did
`json.loads(response.read())` therefore died on `'e'` of `event:` and printed `intake_id=RAW` — which
reads exactly like "the submission failed" while it had in fact succeeded.

Fixtures here are copies of the live frame, not invented shapes.
"""
from __future__ import annotations

import json

import pytest

from misakanet.mcp_reply import McpReplyUnreadable, McpRpcError, parse_mcp_reply

# The success shape of `misakanet_submit_intake` (worker `register-proxy-sw.js:4712-4746`), trimmed
# to the fields a caller reads.
SUCCESS = {
    "submitted": True,
    "intake_id": "issue-3535",
    "status": "pending_review",
    "issue_url": "https://github.com/Ikalus1988/MisakaNet/issues/3535",
    "dedup_key": "8b91e400-e95",
    "receipt": "Filed as issue #3535.",
}


def envelope(payload: dict) -> dict:
    """The worker's `tools/call` result: both halves carry the same object."""
    return {"jsonrpc": "2.0", "id": 1, "result": {
        "content": [{"type": "text", "text": json.dumps(payload)}],
        "structuredContent": payload,
        "resultType": "complete",
    }}


def sse(document: dict) -> str:
    return f"event: message\ndata: {json.dumps(document)}\n\n"


def test_plain_json_reply():
    payload = parse_mcp_reply(json.dumps(envelope(SUCCESS)).encode())
    assert payload["intake_id"] == "issue-3535"
    assert payload["status"] == "pending_review"
    assert payload["issue_url"].endswith("/issues/3535")


def test_sse_reply_equals_plain_reply():
    """The direct #3548 regression: same payload, different frame, identical dict."""
    plain = parse_mcp_reply(json.dumps(envelope(SUCCESS)).encode())
    streamed = parse_mcp_reply(sse(envelope(SUCCESS)).encode())
    assert streamed == plain


def test_sse_keepalive_and_multiline_data():
    """A keepalive is not the reply, and `data:` may be split across several lines."""
    document = envelope(SUCCESS)
    text = json.dumps(document)
    # Split where a newline is legal JSON whitespace (between members), because SSE joins multiple
    # `data:` lines with a newline — splitting inside a string would produce invalid JSON and the
    # reader would be right to reject it.
    cut = text.index('"result"')
    body = (
        ": keepalive\n\n"
        "event: connected\ndata: {}\n\n"
        "event: message\n"
        f"data: {text[:cut]}\n"
        f"data: {text[cut:]}\n\n"
    )
    payload = parse_mcp_reply(body.encode())
    assert payload["intake_id"] == "issue-3535"


def test_unreadable_raises_never_raw():
    with pytest.raises(McpReplyUnreadable) as info:
        parse_mcp_reply(b"<html><body>502 Bad Gateway</body></html>", status=502)
    message = str(info.value)
    assert "502" in message
    assert "<html>" in message  # the snippet is what makes it debuggable
    assert "RAW" not in message

    with pytest.raises(McpReplyUnreadable):
        parse_mcp_reply(b"event: message\ndata: {\"jsonrpc\": \"2.0\", \"id\": 1")  # truncated frame


def test_structured_content_absent_still_resolves():
    """The local stdio server sends only a text block (`misakanet/server/protocol.py:90-102`)."""
    body = {"jsonrpc": "2.0", "id": 1, "result": {
        "content": [{"type": "text", "text": json.dumps(SUCCESS)}]}}
    assert parse_mcp_reply(json.dumps(body).encode())["intake_id"] == "issue-3535"


def test_a_duplicate_without_status_is_not_unreadable():
    """Four of the five intake outcomes carry no `status`; absent is a fact, not a decode failure."""
    duplicate = {
        "submitted": False, "duplicate": True, "pending": True,
        "intake_id": "issue-900", "dedup_key": "abc123",
    }
    payload = parse_mcp_reply(json.dumps(envelope(duplicate)).encode())
    assert payload["duplicate"] is True
    assert "status" not in payload


def test_a_json_rpc_error_is_not_unreadable():
    body = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "Unauthorized"}}
    with pytest.raises(McpRpcError) as info:
        parse_mcp_reply(json.dumps(body).encode(), status=401)
    assert info.value.code == -32000
    assert "Unauthorized" in str(info.value)


def test_empty_body_is_an_error_not_an_empty_dict():
    with pytest.raises(McpReplyUnreadable):
        parse_mcp_reply(b"", status=503)
