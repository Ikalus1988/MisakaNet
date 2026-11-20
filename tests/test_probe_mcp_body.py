#!/usr/bin/env python3
"""The body-integrity probe must fail on a short body and refuse to fail on a bad network.

The interesting failure (#5245) is a response whose body stops early, and the regression it guards
against is the *next* refactor that starts emitting short bodies without noticing. Both are cheap to
pin with synthetic bytes, which is why nothing here touches a socket:

* `parse_response()` is a pure function of the bytes that arrived, so every way a body can be cut
  (declared length unmet, chunked framing unterminated, headers only, nothing at all) is a fixture;
* `verdict()` is a pure function of three summaries, so "answered nothing" and "answered, but short"
  are distinguishable in a test rather than on a bad morning against production.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

spec = importlib.util.spec_from_file_location("probe_mcp_body", REPO / "scripts" / "probe_mcp_body.py")
pmb = importlib.util.module_from_spec(spec)
sys.modules["probe_mcp_body"] = pmb
spec.loader.exec_module(pmb)


def http(headers: list[str], body: bytes) -> bytes:
    return ("HTTP/1.1 200 OK\r\n" + "\r\n".join(headers) + "\r\n\r\n").encode() + body


def chunks(*parts: bytes) -> bytes:
    """Frame each part as one chunk, with the zero-length terminator."""
    out = b""
    for part in parts:
        out += b"%x\r\n" % len(part) + part + b"\r\n"
    return out + b"0\r\n\r\n"


ENVELOPE = b'{"jsonrpc":"2.0","id":1,"result":{"tools":[]}}'
JSON_HEADERS = ["Content-Type: application/json", f"Content-Length: {len(ENVELOPE)}"]


# ── what arrived ────────────────────────────────────────────────────────────────────────────────
def test_a_complete_json_body_is_complete():
    parsed = pmb.parse_response(http(JSON_HEADERS, ENVELOPE), first_ms=10, total_ms=20)
    assert parsed.answered and parsed.complete
    assert parsed.declared == len(ENVELOPE)
    assert parsed.body_bytes == len(ENVELOPE)
    assert parsed.short_by == 0
    assert parsed.jsonrpc is True


def test_a_body_that_stops_early_is_short_and_says_by_how_much():
    """The shape of #5245: the headers promise 3713, the connection delivers 605."""
    parsed = pmb.parse_response(http(JSON_HEADERS, ENVELOPE[:10]), first_ms=10, total_ms=20)
    assert parsed.answered
    assert parsed.complete is False
    assert parsed.short_by == len(ENVELOPE) - 10
    assert parsed.jsonrpc is False


def test_headers_alone_still_report_what_was_promised():
    parsed = pmb.parse_response(http(JSON_HEADERS, ENVELOPE), first_ms=10, total_ms=20)
    cut = b"HTTP/1.1 200 OK\r\nContent-Length: 3713\r\n"     # no blank line: died before the body
    parsed_cut = pmb.parse_response(cut, first_ms=10, total_ms=20)
    assert parsed.complete is True
    assert parsed_cut.answered is True
    assert parsed_cut.complete is False
    assert parsed_cut.short_by == 3713


def test_chunked_with_its_terminator_is_complete():
    parsed = pmb.parse_response(http(
        ["Content-Type: text/event-stream", "Transfer-Encoding: chunked"],
        chunks(ENVELOPE[:16], ENVELOPE[16:])),
        first_ms=5, total_ms=50)
    assert parsed.chunked is True
    assert parsed.complete is True
    assert parsed.body_bytes == len(ENVELOPE)


def test_chunked_without_its_terminator_is_not_complete():
    """A chunked body that ends mid-stream is a cut even though nothing announced a length."""
    framed = chunks(ENVELOPE[:16], ENVELOPE[16:]).rsplit(b"0\r\n\r\n", 1)[0]
    parsed = pmb.parse_response(http(["Transfer-Encoding: chunked"], framed), first_ms=5, total_ms=50)
    assert parsed.chunked is True
    assert parsed.complete is False


def test_an_unparsable_chunk_size_is_not_complete():
    parsed = pmb.parse_response(http(["Transfer-Encoding: chunked"], b"zz\r\nabc\r\n0\r\n\r\n"),
                                first_ms=5, total_ms=5)
    assert parsed.complete is False


def test_nothing_at_all_is_not_answered():
    parsed = pmb.parse_response(b"", first_ms=None, total_ms=30_000)
    assert parsed.answered is False
    assert parsed.error == "empty response"


def test_an_sse_body_is_complete_but_is_not_a_json_envelope():
    event = b"event: message\ndata: " + ENVELOPE + b"\n\n"
    parsed = pmb.parse_response(http(["Content-Type: text/event-stream",
                                       "Transfer-Encoding: chunked"], chunks(event)),
                                first_ms=5, total_ms=50)
    assert parsed.complete is True
    assert parsed.content_type.startswith("text/event-stream")
    assert parsed.jsonrpc is False        # expected: the envelope is inside the SSE frame


# ── the request we send ────────────────────────────────────────────────────────────────────────
def test_the_request_asks_for_one_protocol_version_and_names_its_client():
    raw = pmb.request_bytes("example.invalid", "tools/call", pmb.SSE_ACCEPT, pmb.SEARCH_PARAMS)
    head, _, body = raw.partition(b"\r\n\r\n")
    assert b"Accept: application/json, text/event-stream" in head
    assert b"MCP-Protocol-Version: 2025-06-18" in head
    assert b"X-MisakaNet-Client: misakanet-body-probe" in head
    assert f"Content-Length: {len(body)}".encode() in head
    assert b'"method": "tools/call"' in body


# ── the judgement ──────────────────────────────────────────────────────────────────────────────
def summary(*, answered=20, samples=20, short=0, missing=0, jsonrpc=20):
    return {
        "samples": samples, "answered": answered, "answered_rate": answered / samples,
        "complete": answered - short, "short": short, "short_by_max": missing,
        "jsonrpc": jsonrpc, "errors": [], "first_p50_ms": 900, "total_p50_ms": 1800,
        "body_p50_bytes": 3700,
    }


HEALTHY = summary()


def test_a_clean_run_passes():
    result = pmb.verdict(HEALTHY, HEALTHY, summary(jsonrpc=0))
    assert result["conclusion"] == "pass"
    assert all(check["ok"] for check in result["checks"])


def test_one_short_body_fails_even_in_a_small_sample():
    result = pmb.verdict(HEALTHY, summary(short=1, missing=3108), summary(jsonrpc=0))
    assert result["conclusion"] == "fail"
    failed = [c for c in result["checks"] if not c["ok"]]
    assert [c["name"] for c in failed] == ["json: no short body"]
    assert "3108" in failed[0]["detail"]


def test_a_link_that_answers_nothing_is_inconclusive_not_a_failure():
    """The check refuses to convict the code for the network it ran on."""
    dead = summary(answered=2, samples=20)
    result = pmb.verdict(dead, dead, dead)
    assert result["conclusion"] == "inconclusive"
    assert "could not measure" in result["reason"]
    assert result["checks"] == []


def test_a_slow_baseline_does_not_become_a_body_verdict():
    slow_but_answered = summary()          # latency is not part of this judgement at all
    result = pmb.verdict(slow_but_answered, HEALTHY, summary(jsonrpc=0))
    assert result["conclusion"] == "pass"


def test_a_json_body_that_stops_parsing_fails_on_the_envelope():
    result = pmb.verdict(HEALTHY, summary(jsonrpc=0), summary(jsonrpc=0))
    assert result["conclusion"] == "fail"
    failed = [c["name"] for c in result["checks"] if not c["ok"]]
    assert failed == ["json: envelope parses"]
