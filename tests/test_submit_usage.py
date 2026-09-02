#!/usr/bin/env python3
"""Tests for handle_submit_usage — worker usage-report routing (TODO #submit.py).

Covers the outcome → endpoint mapping with a mocked HTTP transport so the
tests are deterministic and offline-safe:
  solved      -> POST /api/helpful            (feeds me_events helpful votes)
  partial     -> POST /api/feedback too_basic (unsolved map)
  not-helpful -> POST /api/feedback irrelevant (unsolved map + stale lessons)
  offline     -> status "logged" fallback
"""
import json
import os
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from misakanet.server.handlers.submit import handle_submit_usage  # noqa: E402


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def _fake_urlopen(status=200, body=None):
    body = body if body is not None else {}
    return mock.patch("urllib.request.urlopen", return_value=FakeResponse(status, body))


def _capture_urlopen():
    captured = {}

    class Capture(FakeResponse):
        def __init__(self, status, body):
            super().__init__(status, body)
            captured["url"] = self.url
            captured["payload"] = json.loads(self.data.decode())

        @property
        def url(self):
            return self._url

        @property
        def data(self):
            return self._data

    def factory(req, timeout=None):
        inst = Capture(200, {})
        inst._url = req.full_url
        inst._data = req.data
        return inst

    return mock.patch("urllib.request.urlopen", side_effect=factory), captured


def test_solved_posts_helpful_vote():
    with _fake_urlopen(status=200, body={"lesson_id": "dco-x", "count": 3}) as m:
        result = handle_submit_usage({"lesson_id": "dco-x", "outcome": "solved"})
    assert result["status"] == "submitted"
    assert result["remote"] == "helpful"
    assert result["helpful_count"] == 3
    req = m.call_args[0][0]
    assert req.full_url == "https://misakanet.org/api/helpful"
    assert json.loads(req.data) == {"lesson_id": "dco-x"}


def test_partial_posts_too_basic_feedback():
    with _fake_urlopen(status=200, body={"accepted": 1}) as m:
        result = handle_submit_usage({"lesson_id": "dco-x", "outcome": "partial", "query": "dco signoff"})
    assert result["status"] == "submitted"
    assert result["feedback"] == "too_basic"
    payload = json.loads(m.call_args[0][0].data)
    assert payload["lesson_id"] == "dco-x"
    assert payload["feedback"] == "too_basic"
    assert payload["query"] == "dco signoff"


def test_not_helpful_posts_irrelevant_feedback():
    with _fake_urlopen(status=200, body={"accepted": 1}) as m:
        result = handle_submit_usage({"lesson_id": "dco-x", "outcome": "not-helpful"})
    assert result["status"] == "submitted"
    payload = json.loads(m.call_args[0][0].data)
    assert payload["feedback"] == "irrelevant"
    # query falls back to lesson_id when not provided
    assert payload["query"] == "dco-x"


def test_unknown_outcome_is_error_no_network():
    with mock.patch("urllib.request.urlopen") as m:
        result = handle_submit_usage({"lesson_id": "x", "outcome": "wat"})
    assert result["status"] == "error"
    m.assert_not_called()


def test_missing_lesson_id_rejected():
    result = handle_submit_usage({"outcome": "solved"})
    assert "error" in result


def test_offline_falls_back_to_logged():
    with mock.patch("urllib.request.urlopen", side_effect=OSError("network down")):
        result = handle_submit_usage({"lesson_id": "x", "outcome": "solved"})
    assert result["status"] == "logged"
    assert "recorded locally" in result.get("note", "")


def test_disable_remote_env_forces_logged():
    os.environ["MISAKANET_USAGE_DISABLE_REMOTE"] = "1"
    try:
        with mock.patch("urllib.request.urlopen") as m:
            result = handle_submit_usage({"lesson_id": "x", "outcome": "solved"})
        assert result["status"] == "logged"
        m.assert_not_called()
    finally:
        del os.environ["MISAKANET_USAGE_DISABLE_REMOTE"]


def test_api_base_override():
    os.environ["MISAKANET_API_BASE"] = "http://127.0.0.1:9999"
    try:
        with _fake_urlopen(status=200, body={"count": 1}) as m:
            handle_submit_usage({"lesson_id": "x", "outcome": "solved"})
        req = m.call_args[0][0]
        assert req.full_url == "http://127.0.0.1:9999/api/helpful"
    finally:
        del os.environ["MISAKANET_API_BASE"]
