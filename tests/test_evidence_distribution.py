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
    # The row is read out of the document rather than typed: the mutation used to name `76` while the
    # table said `77`, so the `if doctored == original` guard turned this red case into a permanent
    # skip — a gate that could no longer fail, which is the failure this whole file is about.
    row = next((line for line in original.splitlines() if line.startswith("| **E2** (declared) |")), None)
    assert row is not None, "the E2 row disappeared — this fixture mutates the published table"
    doctored = original.replace(row, row.replace("| 77 |", "| 76 |", 1))
    if doctored == original:
        pytest.skip(f"the E2 row no longer reads `| 77 |` — update the mutation: {row!r}")
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


# ── --write: the block is replaced, the rest of the page is untouched ────────────────────────────

def test_write_replaces_the_block_and_leaves_the_prose_alone(tmp_path):
    """The step this replaces is a human pasting a table, which is why two contributor PRs were
    machine-unrebuildable on 2026-11-23: every other conflict was in a generator-owned file."""
    from scripts import evidence_distribution as ed

    original = DOC.read_text(encoding="utf-8")
    doctored = original.replace("| **E1** (declared) |", "| **E1** (declared) | ", 1)
    target = tmp_path / "trust-semantics.md"
    target.write_text(doctored + "\n\n## A section after the block\n\nprose\n", encoding="utf-8")

    before_prose = target.read_text(encoding="utf-8").split(ed.BLOCK_START)[0]
    after_prose = target.read_text(encoding="utf-8").split(ed.BLOCK_END, 1)[1]

    result = subprocess.run([sys.executable, str(SCRIPT), "--write", str(target)],
                            capture_output=True, text=True, cwd=REPO)
    assert result.returncode == 0, result.stderr
    assert _run("--check", str(target)).returncode == 0, "the written file must pass --check"

    written = target.read_text(encoding="utf-8")
    assert written.startswith(before_prose), "text before the block changed"
    assert written.endswith(after_prose), "text after the block changed"


def test_write_refuses_a_file_with_no_marker(tmp_path):
    from scripts import evidence_distribution as ed

    target = tmp_path / "no-marker.md"
    target.write_text("just prose\n", encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), "--write", str(target)],
                            capture_output=True, text=True, cwd=REPO)
    assert result.returncode != 0
    assert "marker" in (result.stderr + result.stdout)
    assert target.read_text(encoding="utf-8") == "just prose\n", "a refused write must not touch it"
