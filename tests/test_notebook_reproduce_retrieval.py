#!/usr/bin/env python3
"""The Colab notebook is data, so it can rot silently — pin its shape.

Why a test for a notebook
--------------------------
A `.ipynb` is JSON that nothing imports and no gate reads: rename a constant, delete the retry loop,
pin a version that never existed, and CI stays green while the artifact every reader opens is wrong.
The failure mode is worse than a broken script, because a notebook *looks* like evidence.

So this pins the parts that make it trustworthy: it is well-formed nbformat 4, it reads the published
immutable URL shape, it paces against the burst guard, and it retries transport failures instead of
counting them as misses (the distinction the whole benchmark rests on).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

NOTEBOOK = Path(__file__).resolve().parent.parent / "docs/notebooks/reproduce-retrieval.ipynb"


def load() -> dict:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def source(nb: dict) -> str:
    return "\n".join("".join(cell["source"]) for cell in nb["cells"])


def test_the_notebook_is_valid_nbformat():
    nb = load()
    assert nb["nbformat"] == 4
    assert nb["nbformat_minor"] >= 5
    assert nb["cells"], "an empty notebook is not reproducible"


def test_it_points_at_an_immutable_versioned_url_not_latest():
    text = source(load())
    version = re.search(r'VERSION\s*=\s*"([^"]+)"', text)
    assert version, "the notebook must pin a version"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-[0-9a-f]{7}", version.group(1)), version.group(1)
    # `latest` moves; a notebook pinned to it reports a different number every run and blames the
    # notebook. The URL shape itself is the guarantee.
    assert "/v{VERSION}/" in text or "${VERSION}" in text


def test_it_paces_and_retries_rather_than_scoring_transport_failures():
    text = source(load())
    assert "DELAY" in text and "ATTEMPTS" in text
    assert "time.sleep" in text, "the anonymous read path has a burst guard per address"
    # The retry loop must exist and the failure must be excluded from the denominator, not counted
    # as `no_match` — that is exactly the bug the zh probe hit on 2026-10-27 (20 of 64 empty bodies
    # would have read as a 31% recall collapse).
    assert "excluded from every rate" in text
    assert "failures" in text


def test_it_takes_the_structured_payload_when_the_endpoint_offers_one():
    text = source(load())
    assert "structuredContent" in text
    assert "content" in text, "older replies carry the payload as JSON inside content[0].text"


def test_it_says_what_it_does_not_show():
    text = source(load())
    assert "Does not" in text
    assert "generated from the target" in text, "the notebook must repeat the sampling caveat"
