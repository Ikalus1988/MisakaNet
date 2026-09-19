#!/usr/bin/env python3
"""The intake rate limiter must not be keyed by a value the caller chooses.

`ip_key = source or "anon"` meant a caller could reset its own quota by sending a different `source`
label — a rate limit with a self-service key (2026-09-18 review, 意见 7). The key is now the client
address when the transport can see it, and only falls back to the label when it cannot.

These tests exercise the pure decision function; the address lookup itself is transport plumbing
(FastMCP's request context) and is not mocked here.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import mcp_http_server as srv  # noqa: E402


def test_a_real_client_address_wins_over_the_source_label():
    key, kind = srv._rate_limit_key("mcp", "203.0.113.9")
    assert (key, kind) == ("203.0.113.9", "ip")


def test_two_labels_from_one_address_share_a_bucket():
    """The old bug in one line: changing `source` used to hand the caller a fresh quota."""
    first, _ = srv._rate_limit_key("mcp", "203.0.113.9")
    second, _ = srv._rate_limit_key("something-else", "203.0.113.9")
    assert first == second


def test_without_an_address_the_key_is_the_label_and_says_so():
    key, kind = srv._rate_limit_key("curl", "")
    assert key == "source:curl"
    assert kind == "source", "the honest answer: this bucket is client-chosen and spoofable"


def test_no_address_and_no_label_still_produces_one_bucket():
    key, kind = srv._rate_limit_key("", "")
    assert key == "source:anon"
    assert kind == "source"


def test_the_refusal_message_flags_a_spoofable_key():
    """A limit that is only enforced per label must not read as if it were per caller."""
    source = (REPO / "scripts" / "mcp_http_server.py").read_text(encoding="utf-8")
    assert "该键可被调用方自设" in source, (
        "the refusal message must say when the key was the client-supplied label"
    )
