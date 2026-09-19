#!/usr/bin/env python3
"""The installed `misakanet` CLI, against a stubbed endpoint (2026-09-18, #1821).

`pip install misakanet && misakanet "<error>"` exited with `ModuleNotFoundError` because the declared
entry point named a module outside the wheel. It now runs `misakanet.cli.search:main`, which searches the
remote endpoint — no corpus needed, which is the only thing a wheel can do.

Network is stubbed: these assert the *request* this client sends and how it reads the answers, which is
where a wrong header or a misread payload would silently produce "no results".
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import urllib.error
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from misakanet.cli import search as cli  # noqa: E402
from misakanet import remote  # noqa: E402


class _Reply:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _capture(monkeypatch, payload: dict) -> dict:
    seen: dict = {}

    def fake_urlopen(request, timeout=None):
        seen["url"] = request.full_url
        seen["headers"] = {k.lower(): v for k, v in request.header_items()}
        seen["body"] = json.loads(request.data.decode())
        return _Reply(payload)

    monkeypatch.setattr(remote.urllib.request, "urlopen", fake_urlopen)
    return seen


# A synthetic token, derived per run.
#
# A literal of this shape is indistinguishable from a hardcoded credential to a scanner that cannot know
# it is fake — hol-guard's plugin-scanner reported exactly that as `HARDCODED_SECRET` at error severity
# (2026-09-19), and the worker tests had already solved the same false positive this way
# (`workers/_test-token.mjs`, alerts #252/#253). Deriving it also means a fixture cannot accidentally
# match a real credential.
SYNTHETIC_TOKEN = f"mcp_{uuid.uuid4().hex}"

def test_the_request_is_an_mcp_tools_call_with_the_documented_headers(monkeypatch):
    seen = _capture(monkeypatch, {"result": {"structuredContent": {"results": []}}})
    remote.search("boom", top=3)
    assert seen["url"] == remote.DEFAULT_ENDPOINT
    assert seen["body"]["method"] == "tools/call"
    assert seen["body"]["params"]["name"] == "misakanet_search"
    assert seen["body"]["params"]["arguments"]["query"] == "boom"
    assert seen["body"]["params"]["arguments"]["top"] == 3
    assert seen["headers"]["mcp-protocol-version"] == remote.PROTOCOL_VERSION
    assert seen["headers"]["origin"] == remote.ORIGIN, "the documented Origin, not a missing header"


def test_a_token_goes_in_the_header_and_never_in_the_body(monkeypatch):
    seen = _capture(monkeypatch, {"result": {"structuredContent": {"results": []}}})
    remote.search("boom", token=SYNTHETIC_TOKEN)
    assert seen["headers"]["authorization"] == f"Bearer {SYNTHETIC_TOKEN}"
    assert SYNTHETIC_TOKEN not in json.dumps(seen["body"])


def test_client_id_is_a_pseudonym_passed_as_an_argument(monkeypatch):
    seen = _capture(monkeypatch, {"result": {"structuredContent": {"results": []}}})
    remote.search("boom", client_id="agent-a")
    assert seen["body"]["params"]["arguments"]["client_id"] == "agent-a"


def test_both_response_shapes_are_read(monkeypatch):
    _capture(monkeypatch, {"result": {"structuredContent": {"results": [{"title": "A"}]}}})
    assert remote.search("x")["results"][0]["title"] == "A"

    _capture(monkeypatch, {"result": {"content": [{"type": "text",
                                                   "text": json.dumps({"results": [{"title": "B"}]})}]}})
    assert remote.search("x")["results"][0]["title"] == "B"


def test_exit_codes_separate_no_match_from_an_unreachable_endpoint(monkeypatch):
    _capture(monkeypatch, {"result": {"structuredContent": {"no_match": True}}})
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        assert cli.main(["nothing matches this"]) == cli.EXIT_NO_MATCH
    assert "submit_intake" in out.getvalue(), "a gap must point at the intake, not just say 'nothing'"

    def boom(request, timeout=None):
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(remote.urllib.request, "urlopen", boom)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        assert cli.main(["x"]) == cli.EXIT_ERROR


def test_results_are_printed_with_their_scores(monkeypatch):
    _capture(monkeypatch, {"result": {"structuredContent": {"results": [
        {"title": "Hermes State Database Lock", "path": "hermes-db-lock", "score": 0.905},
    ]}}})
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert cli.main(["database is locked"]) == cli.EXIT_OK
    text = out.getvalue()
    assert "Hermes State Database Lock" in text and "0.905" in text and "hermes-db-lock" in text


def test_json_mode_prints_the_payload(monkeypatch):
    _capture(monkeypatch, {"result": {"structuredContent": {"results": [], "no_match": True}}})
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert cli.main(["--json", "x"]) == cli.EXIT_NO_MATCH
    assert json.loads(out.getvalue())["no_match"] is True
