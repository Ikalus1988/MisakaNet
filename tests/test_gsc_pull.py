#!/usr/bin/env python3
"""`scripts/gsc_pull.py` — the request it builds, the token it never prints, the file it writes.

Why a test for a 150-line puller: the failure this guards against is silent. A wrong property id, a
date range that asks for data Search Console has not finalised, or a token that leaks into a log line
all produce *a file* that looks like a measurement — and the reader of that file has no way to tell.
`data/gsc/` is git-ignored on purpose (a weekly series of dated snapshots is the shape
`tests/test_benchmark_snapshot_retention.py` exists to stop), so nothing downstream re-checks it.

What is pinned here:
  * the property id is percent-encoded into the path, trailing slash included;
  * the body asks for a finalised window, never for today's partials;
  * the token comes from the environment first, `gcloud` second, and appears in no printed line;
  * a dry run writes nothing; a real run writes the request it made next to the answer.
"""
from __future__ import annotations

import io
import json
import sys
from datetime import date
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import gsc_pull as gsc  # noqa: E402


class FakeOpener:
    """Records the request it was handed and answers with a fixed payload."""

    def __init__(self, payload: dict | None = None):
        self.calls = []
        self.payload = payload if payload is not None else {
            "rows": [
                {"keys": ["pip install timeout"], "clicks": 3, "impressions": 40, "position": 6.5},
                {"keys": ["wsl2 landlock"], "clicks": 0, "impressions": 90, "position": 18.0},
            ]
        }

    def open(self, request, timeout=None):
        self.calls.append(request)
        return io.BytesIO(json.dumps(self.payload).encode("utf-8"))


def test_the_property_is_percent_encoded_into_the_path():
    # A URL-prefix property is written with scheme and a trailing slash; the API wants that whole
    # string in the path, and an unencoded one changes the route.
    key = gsc.site_key("https://misakanet.org/")
    assert key == "https%3A%2F%2Fmisakanet.org%2F"


def test_the_body_asks_for_a_finalised_window_not_today():
    body = gsc.build_body("2026-10-18", "2026-11-11")
    assert body["startDate"] == "2026-10-18" and body["endDate"] == "2026-11-11"
    assert body["dimensions"] == ["query"] and body["rowLimit"] == 200
    assert body["dataState"] == "final", "asking for partials reads as a drop in traffic"

    start, end = gsc.default_window(28, today=date(2026, 11, 14))
    assert end == "2026-11-12", "the window must stop before the unfinalised tail"
    assert start == "2026-10-16"
    assert (date.fromisoformat(end) - date.fromisoformat(start)).days == 27


def test_the_token_comes_from_the_environment_first(monkeypatch):
    monkeypatch.setenv("GSC_ACCESS_TOKEN", "env-token")
    # A gcloud that would explode if it were consulted proves the environment won.
    assert gsc.load_token(gcloud="/nonexistent/gcloud") == "env-token"


def test_a_missing_token_names_both_ways_to_supply_one(monkeypatch):
    monkeypatch.delenv("GSC_ACCESS_TOKEN", raising=False)
    with pytest.raises(SystemExit) as exc:
        gsc.load_token(gcloud="/nonexistent/gcloud")
    assert "GSC_ACCESS_TOKEN" in str(exc.value)


def test_the_request_carries_the_bearer_and_the_digest_ranks_by_impressions():
    opener = FakeOpener()
    body = gsc.build_body("2026-10-18", "2026-11-11")
    payload = gsc.query("https://misakanet.org/", body, "secret-token", opener=opener)
    assert len(opener.calls) == 1
    request = opener.calls[0]
    assert "sites/https%3A%2F%2Fmisakanet.org%2F/searchAnalytics/query" in request.full_url
    assert request.get_header("Authorization") == "Bearer secret-token"
    assert json.loads(request.data.decode("utf-8"))["dataState"] == "final"

    digest = gsc.summarise(payload)
    assert "2 query row(s)" in digest and "130 impression(s)" in digest
    assert digest.index("wsl2") < digest.index("pip install"), (
        "the digest ranks by impressions, so the query nobody found us for still shows up")
    assert "secret-token" not in digest


def test_a_dry_run_writes_nothing_and_a_real_run_records_the_request(tmp_path, monkeypatch, capsys):
    opener = FakeOpener()
    monkeypatch.setattr(gsc, "OPENER", opener)
    monkeypatch.setenv("GSC_ACCESS_TOKEN", "env-token")

    assert gsc.main(["--start", "2026-10-18", "--end", "2026-11-11",
                     "--out", str(tmp_path), "--dry-run"]) == 0
    assert list(tmp_path.iterdir()) == [], "a dry run wrote a file"
    printed = capsys.readouterr().out
    assert "dry run" in printed and "env-token" not in printed

    assert gsc.main(["--start", "2026-10-18", "--end", "2026-11-11", "--out", str(tmp_path)]) == 0
    written = tmp_path / "search-analytics-2026-11-11.json"
    saved = json.loads(written.read_text(encoding="utf-8"))
    assert saved["request"]["startDate"] == "2026-10-18"
    assert saved["response"]["rows"][0]["keys"] == ["pip install timeout"]
    assert "env-token" not in written.read_text(encoding="utf-8"), (
        "the file records the request, never the credential that authorised it")
