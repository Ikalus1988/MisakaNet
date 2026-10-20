#!/usr/bin/env python3
"""The intake receipt must tell the truth about where the report went.

Why this file exists
--------------------
`misakanet_submit_intake` used to write to the local contribution queue and report
`submitted: true`, with a `poll_hint` telling the caller to run `misakanet_me_inbox` for an
answer. Three things were wrong with that, and each one is a way of saying something false:

1. **Nothing drains the local queue into a GitHub issue.** The only reader is the maintainer CLI
   `scripts/contribution_review.py`. A report written there never reaches MisakaNet, so
   "submitted" was a local file write wearing a success receipt.
2. **The `dedup_key` in the receipt was not the key the queue stored.** The handler computed a
   second hash (SHA-256 over `kind:problem:source`) while the queue stored its own (SHA-256 over
   the redacted title/message). The returned key named nothing that existed, so it could not
   dedup anything — and it was not the key `me_inbox` would look up either.
3. **`me_inbox` could never answer for a local entry.** It proxies the hosted worker, which has
   never heard of a `contrib_…` id.

The fix makes the tool remote-first (the hosted worker is the only place an intake becomes an
issue) and keeps the local queue as the degraded path — with a receipt that says the report did
not reach MisakaNet, and a `me_inbox` that answers locally so the local promise still holds.

Every assertion below can go red: point the handler back at the old local-only behaviour, or
reintroduce a second hash, and the matching test fails.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from misakanet.server.handlers.inbox import handle_me_inbox
from misakanet.server.handlers.submit import handle_submit_intake

_URLOPEN = "misakanet.server.handlers.inbox._url_request.urlopen"
_REMOTE_CALL = "misakanet.remote.call"


@pytest.fixture()
def local_queue(tmp_path, monkeypatch):
    """An isolated contribution queue, with the network switched off.

    The queue path is a module constant resolved at import time, so the env var alone would only
    bite for whichever test happened to import it first. `tests/conftest.py` redirects it per
    session; this pins one test's own file the way the other queue tests do.
    """
    queue = tmp_path / "queue.jsonl"
    monkeypatch.setenv("MISAKANET_INTAKE_DISABLE_REMOTE", "1")
    import scripts.contribution_queue as contribution_queue
    monkeypatch.setattr(contribution_queue, "QUEUE_FILE", queue)
    return queue


def _stored_entries(queue: Path) -> list[dict]:
    if not queue.exists():
        return []
    return [json.loads(line) for line in queue.read_text(encoding="utf-8").splitlines() if line.strip()]


class TestLocalFallbackIsHonest:
    def test_receipt_says_the_report_did_not_reach_misakanet(self, local_queue):
        result = handle_submit_intake({
            "kind": "missing_lesson",
            "problem": "the queue never becomes an issue",
            "source": "test",
        })
        assert result["submitted"] is True
        assert result["delivery"] == "local_queue"
        assert result["note"]
        assert "not" in result["note"].lower() or "only" in result["note"].lower()

    def test_dedup_key_is_the_key_the_queue_actually_stored(self, local_queue):
        """The old receipt invented a second hash that named nothing that existed."""
        result = handle_submit_intake({
            "kind": "missing_lesson",
            "problem": "two different hashes for one report",
            "source": "test",
        })
        entries = _stored_entries(local_queue)
        assert entries, "the local queue took the report"
        assert result["dedup_key"] == entries[0]["dedup_key"]

    def test_poll_hint_has_the_documented_shape(self, local_queue):
        """One reader handles both transports: the object shape, not a sentence."""
        result = handle_submit_intake({
            "kind": "missing_lesson",
            "problem": "poll hint shape",
            "source": "test",
        })
        hint = result["poll_hint"]
        assert isinstance(hint, dict)
        assert set(hint) == {"tool", "argument", "how", "recheck_after_seconds"}
        assert hint["tool"] == "misakanet_me_inbox"
        assert result["intake_id"] in hint["argument"]

    def test_question_and_failure_report_poll_on_different_clocks(self, local_queue):
        question = handle_submit_intake({
            "kind": "question", "problem": "how do I configure this?", "source": "test"})
        report = handle_submit_intake({
            "kind": "missing_lesson", "problem": "it broke", "source": "test"})
        assert question["poll_hint"]["recheck_after_seconds"] == 21600
        assert report["poll_hint"]["recheck_after_seconds"] == 86400


class TestTheLocalLoopCloses:
    def test_me_inbox_answers_a_locally_queued_intake(self, local_queue):
        """The receipt promises a poll; the poll has to work."""
        submitted = handle_submit_intake({
            "kind": "missing_lesson", "problem": "will anyone answer me?", "source": "test"})
        with patch(_URLOPEN, side_effect=AssertionError("the local queue must answer, not the network")):
            got = handle_me_inbox({"intake_id": submitted["intake_id"]})
        assert got["status"] != "not_found"
        assert got["delivery"] == "local_queue"
        assert got["note"]

    def test_me_inbox_finds_a_local_entry_by_its_dedup_key_too(self, local_queue):
        submitted = handle_submit_intake({
            "kind": "missing_lesson", "problem": "find me by key", "source": "test"})
        with patch(_URLOPEN, side_effect=AssertionError("the local queue must answer, not the network")):
            got = handle_me_inbox({"dedup_key": submitted["dedup_key"]})
        assert got["delivery"] == "local_queue"

    def test_an_unknown_id_still_goes_to_the_hosted_endpoint(self, local_queue):
        """A local lookup that misses must not swallow the hosted lookup."""
        with patch(_URLOPEN) as opener:
            opener.return_value.read.return_value = json.dumps(
                {"intake_id": "issue-1", "status": "pending"}).encode()
            opener.return_value.__enter__.return_value = opener.return_value
            got = handle_me_inbox({"intake_id": "issue-1"})
        assert opener.called
        assert got["status"] == "pending"


class TestRemoteIsTheRealPath:
    def test_the_hosted_receipt_is_passed_through_unchanged(self, local_queue, monkeypatch):
        monkeypatch.delenv("MISAKANET_INTAKE_DISABLE_REMOTE", raising=False)
        worker_receipt = {
            "submitted": True,
            "intake_id": "issue-4242",
            "status": "pending_review",
            "dedup_key": "1a2b3c4d",
            "poll_hint": {"tool": "misakanet_me_inbox", "argument": "intake_id=\"issue-4242\"",
                          "how": "re-check later", "recheck_after_seconds": 21600},
            "quality_score": 77,
        }
        with patch(_REMOTE_CALL, return_value=worker_receipt) as call:
            result = handle_submit_intake({
                "kind": "question", "problem": "does it reach the network?", "source": "test"})
        assert call.called
        assert result["delivery"] == "remote"
        assert result["intake_id"] == "issue-4242"
        assert result["dedup_key"] == "1a2b3c4d"
        assert result["poll_hint"] == worker_receipt["poll_hint"]
        assert result["quality_score"] == 77

    def test_the_report_is_not_written_to_the_local_queue_when_the_network_works(self, local_queue, monkeypatch):
        monkeypatch.delenv("MISAKANET_INTAKE_DISABLE_REMOTE", raising=False)
        with patch(_REMOTE_CALL, return_value={"submitted": True, "intake_id": "issue-4242"}):
            handle_submit_intake({
                "kind": "missing_lesson", "problem": "no local copy wanted", "source": "test"})
        assert _stored_entries(local_queue) == []

    def test_an_unreachable_network_falls_back_to_the_local_queue(self, local_queue, monkeypatch):
        monkeypatch.delenv("MISAKANET_INTAKE_DISABLE_REMOTE", raising=False)
        with patch(_REMOTE_CALL, side_effect=OSError("connection refused")):
            result = handle_submit_intake({
                "kind": "missing_lesson", "problem": "the network is down", "source": "test"})
        assert result["submitted"] is True
        assert result["delivery"] == "local_queue"
        assert "connection refused" in result["note"]


class TestNoQueueAndNoNetwork:
    def test_an_installed_client_with_no_network_gets_an_error_not_a_success(self, local_queue, monkeypatch):
        """`scripts/` is not in the wheel, so an installed client has no local queue at all.

        Reporting `submitted: true` there would be the same lie in a new place: the report
        goes nowhere and the caller is told it was filed.
        """
        monkeypatch.delenv("MISAKANET_INTAKE_DISABLE_REMOTE", raising=False)
        monkeypatch.setitem(sys.modules, "scripts.contribution_queue", None)
        with patch(_REMOTE_CALL, side_effect=OSError("connection refused")):
            result = handle_submit_intake({
                "kind": "missing_lesson", "problem": "nowhere to put this", "source": "test"})
        assert result["submitted"] is False
        assert result["error"]
        assert result["hint"]

    def test_a_missing_problem_is_rejected_before_any_network_call(self, local_queue, monkeypatch):
        monkeypatch.delenv("MISAKANET_INTAKE_DISABLE_REMOTE", raising=False)
        with patch(_REMOTE_CALL) as call:
            result = handle_submit_intake({"kind": "missing_lesson"})
        assert not call.called
        assert result["error"] == "problem is required"
