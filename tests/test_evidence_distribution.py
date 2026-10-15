#!/usr/bin/env python3
"""The evidence distribution in `docs/trust-semantics.md` must match the corpus.

`backlog-and-growth-2026-09-20.md` §3.9 asked for the E0-E4 distribution to be published
before any downgrade mechanism is designed. Publishing it is the easy half; the half that
decides whether it is worth anything is whether it **stays true**. Every other number in
this repository's maintainer docs has gone stale — `growth-funnel.md`'s baseline has never
been refreshed since it was written — so the number gets a gate of its own.

This test is the gate. It is deliberately a thin wrapper over the script rather than a
re-implementation of the counting: two implementations of "what counts as E0" would drift,
and then the test would be asserting the wrong thing while looking rigorous.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "evidence_distribution.py"
DOC = REPO / "docs" / "trust-semantics.md"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=REPO, timeout=120,
    )


def test_the_published_distribution_matches_the_corpus():
    """The committed table is what the corpus says today, not what it said once."""
    result = _run("--check", str(DOC))
    assert result.returncode == 0, (
        "docs/trust-semantics.md carries a stale evidence distribution — "
        f"run `python3 scripts/evidence_distribution.py` and paste the table.\n"
        f"checker said: {result.stderr.strip()}"
    )


def test_check_fails_when_the_table_drifts(tmp_path):
    """A one-digit edit has to turn the gate red, or the gate is decoration.

    §90.4.1's rule applied to a gate rather than to a test: "if reverting does not go
    red, it is ornamental". A check that only ever passes proves nothing, and the only way
    to know it bites is to make it bite on purpose.
    """
    original = DOC.read_text(encoding="utf-8")
    doctored = original.replace("| **E2** (declared) | 76 |", "| **E2** (declared) | 75 |")
    if doctored == original:
        pytest.skip("the E2 row no longer says 76 — update the mutation to a row that exists")
    target = tmp_path / "trust-semantics.md"
    target.write_text(doctored, encoding="utf-8")
    result = _run("--check", str(target))
    assert result.returncode == 1, (
        "a doctored distribution still passed the check — the gate cannot see drift"
    )


def test_missing_file_is_a_failure_not_a_skip(tmp_path):
    """A deleted page must fail loudly; a missing document is not a passing document."""
    result = _run("--check", str(tmp_path / "does-not-exist.md"))
    assert result.returncode == 1
