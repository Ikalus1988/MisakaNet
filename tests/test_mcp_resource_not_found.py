#!/usr/bin/env python3
"""An unresolved `resources/read` must be a JSON-RPC error, not a success envelope.

The defect this gate exists for (#5141 / #5204)
-----------------------------------------------
`handle_resources_read` signals a miss by returning `{"error": "Unknown resource: <uri>"}`,
and `protocol.py` wrapped *whatever came back* in a successful
`result.contents[0].text`. So a caller that trusts the envelope —
`json.loads(resp["result"]["contents"][0]["text"])` — received an error object as if it were
the resource body, and a caller that checks `"error" in resp` never saw one at all.
MCP assigns an unresolved resource URI to -32002; the detail is preserved under `data`.

What is pinned here
-------------------
1. an unknown URI answers `error.code == -32002` and carries no `result`;
2. the original detail survives in `error.data.detail`, so the diagnostics are not lost;
3. a URI that does resolve still answers a normal `result.contents`, unchanged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from misakanet.server.protocol import handle_request  # noqa: E402


def _read(uri: str) -> dict:
    return handle_request({
        "jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": uri},
    })


def test_unknown_uri_is_a_protocol_error():
    resp = _read("misakanet://does-not-exist")
    assert "result" not in resp, f"a miss must not answer a result: {resp}"
    assert resp["error"]["code"] == -32002
    assert resp["error"]["data"]["uri"] == "misakanet://does-not-exist"


def test_detail_is_preserved():
    resp = _read("misakenet://typo-in-scheme")
    assert "Unknown resource" in resp["error"]["data"]["detail"]


def test_resolvable_uri_still_answers_contents():
    resp = _read("misaka://lessons/index")
    assert "error" not in resp
    payload = json.loads(resp["result"]["contents"][0]["text"])
    assert "lessons" in payload


if __name__ == "__main__":  # runnable without pytest, for a bare checkout
    for fn in (test_unknown_uri_is_a_protocol_error, test_detail_is_preserved,
               test_resolvable_uri_still_answers_contents):
        fn()
        print(f"ok  {fn.__name__}")
