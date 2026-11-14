#!/usr/bin/env python3
"""The three Analytics Engine queries, against the **real** API — the only test that can catch SQL.

Why this file exists: `tests/test_analytics_ae_query.py` asserts substrings, and three invalid
queries passed it while the live endpoint rejected every one of them (2026-11-15):

* `if(SUM(_sample_interval) = 0, 0, <double>)` — *"the 2nd and 3rd arguments to IF() function must
  have the same type"*;
* `ORDER BY blob1` after `SELECT blob1 AS tool` — *"unable to find type of column: blob1"*;
* `ORDER BY SUM(_sample_interval)` — the same resolution failure.

A substring assertion cannot see any of that. This module runs each query for real and asserts the
API accepts it.

It is **skipped by default** because it needs a credential and the network:

    CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ACCOUNT_ID=... python3 -m pytest tests/test_analytics_ae_live.py -q

CI has neither, so it skips there. That is deliberate rather than convenient: a live smoke that
silently runs in CI would turn a network hiccup into a red build, and a live smoke that is *never*
run is invisible — so the docstring above is the instruction, and the skip reason names the two
variables.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import ae_query  # noqa: E402

TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
ACCOUNT = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()

pytestmark = pytest.mark.skipif(
    not (TOKEN and ACCOUNT),
    reason="needs CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID (see this module's docstring); "
           "this is the only check that can catch a syntactically plausible but invalid query",
)


def _run(sql: str) -> dict:
    request = ae_query.build_request(sql, account_id=ACCOUNT, token=TOKEN)
    with urllib.request.urlopen(request, timeout=60) as response:
        assert response.status == 200, f"HTTP {response.status}"
        return json.loads(response.read().decode("utf-8"))


@pytest.mark.parametrize("builder", [
    ("miss_rate", ae_query.miss_rate_sql),
    ("latency", ae_query.latency_sql),
    ("top_missed", ae_query.top_missed_sql),
])
def test_the_live_api_accepts_every_query(builder):
    name, build = builder
    payload = _run(build(7))
    assert "meta" in payload and "data" in payload, (
        f"{name}: the endpoint answered without a result shape — {str(payload)[:200]}")
