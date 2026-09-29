#!/usr/bin/env python3
"""The retrieval badge: one published number about *our* implementation, and the wiring that publishes it.

The decision (owner, 2026-09-29): publish `servedBy` (BM25 vs the naive fallback, today) and do **not**
publish `mcpClients` (per-client call counts, self-declared keys, about other people's tooling). This file
pins the parts of that decision a machine can hold: the message and colour for every shape of the counter,
that the request carries a User-Agent (the edge 403s urllib's default — measured 2026-09-28), that a
transport failure writes nothing instead of publishing "no data", and that the endpoint losing `servedBy`
is a failure rather than a silently meaningless badge.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import update_retrieval_badge as badge  # noqa: E402


# ── the payload ──────────────────────────────────────────────────────────────────────────────────────

def test_a_clean_day_is_bright_green_and_says_so():
    payload = badge.badge_for({"bm25": 342})
    assert payload == {"schemaVersion": 1, "label": "retrieval today", "message": "100% bm25",
                       "color": "brightgreen"}, payload


def test_a_trace_of_fallback_stays_green_and_a_real_share_turns_orange():
    """Falling back is the *older* answer path, not an error: the badge must not cry wolf."""
    assert badge.badge_for({"bm25": 990, "fallback": 10})["color"] == "green"
    assert badge.badge_for({"bm25": 990, "fallback": 10})["message"] == "99% bm25"
    assert badge.badge_for({"bm25": 500, "fallback": 500})["color"] == "orange"
    assert badge.badge_for({"bm25": 500, "fallback": 500})["message"] == "50% bm25"


def test_no_counter_at_all_says_no_data_rather_than_zero_percent():
    for counts in ({}, None, {"bm25": 0, "fallback": 0}):
        payload = badge.badge_for(counts)
        assert payload["message"] == "no data", (counts, payload)
        assert payload["color"] == "lightgrey", (counts, payload)


# ── the request and the answer ───────────────────────────────────────────────────────────────────────

class _Response:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_the_request_carries_an_explicit_user_agent():
    """Without one the edge answers 403 on this host, which reads as an outage (2026-09-28)."""
    seen = {}

    def opener(request, timeout=None):
        seen["ua"] = request.get_header("User-agent")
        seen["url"] = request.full_url
        return _Response({"servedBy": {"bm25": 7}})

    status, counts = badge.fetch_index("https://example.test/api/search-index", opener=opener)
    assert (status, counts) == ("ok", {"bm25": 7}), (status, counts)
    assert seen["ua"] == badge.USER_AGENT, seen
    assert seen["ua"], "an empty User-Agent is the failure mode this test exists for"


def test_a_transport_failure_is_not_an_error_and_writes_nothing(monkeypatch, tmp_path):
    def broken(request, timeout=None):
        raise TimeoutError("the read operation timed out")

    status, counts = badge.fetch_index("https://example.test/", opener=broken)
    assert (status, counts) == (badge.UNREACHABLE, None), (status, counts)

    out = tmp_path / "retrieval.json"
    out.write_text('{"message": "yesterday"}', encoding="utf-8")
    # `main` must leave the file alone: a badge that cannot be refreshed keeps yesterday's value rather
    # than claiming "no data" because a runner had a bad minute. Patched so this stays an offline test —
    # a unit test that reaches the network is a test that fails for reasons it does not own.
    monkeypatch.setattr(badge, "fetch_index", lambda *a, **k: (badge.UNREACHABLE, None))
    assert badge.main(["--source", "https://example.test/", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {"message": "yesterday"}


def test_an_endpoint_that_lost_served_by_fails_instead_of_publishing_nonsense(monkeypatch):
    def opener(request, timeout=None):
        return _Response({"available": True, "docCount": 426})

    with pytest.raises(SystemExit):
        badge.fetch_index("https://example.test/", opener=opener)


def test_main_writes_the_badge_it_computed(monkeypatch, tmp_path):
    monkeypatch.setattr(badge, "fetch_index", lambda *a, **k: ("ok", {"bm25": 90, "fallback": 10}))
    out = tmp_path / "badges" / "retrieval.json"
    assert badge.main(["--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["message"] == "90% bm25", payload
    assert payload["label"] == "retrieval today", payload


# ── the wiring: a badge nobody points at is not published ────────────────────────────────────────────

BADGE_FILE = "badges/retrieval.json"


def test_the_workflow_writes_the_file_the_readmes_point_at():
    workflow = (REPO / ".github" / "workflows" / "update-badges.yml").read_text(encoding="utf-8")
    assert BADGE_FILE.replace("badges/", "badges/") in workflow, (
        "the badge workflow does not write the file the READMEs read")
    assert "scripts/update_retrieval_badge.py" in workflow, "the step exists but does not run the script"

    for rel in ("README.md", "README.zh-CN.md"):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert f"data/{BADGE_FILE}" in text, f"{rel} does not publish the retrieval badge"
        # …and the badge must not be the *only* place the number lives in that file: a hand-written
        # percentage would go stale exactly like the lesson counts used to.
        assert "retrieval.json" in text and "% bm25" not in text, (
            f"{rel} hand-writes a retrieval percentage next to a live badge")
