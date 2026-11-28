#!/usr/bin/env python3
"""`scripts/audit_review_band.py` must be able to fail, or the band stops in the middle again.

Measured 2026-11-28: 90 open intakes from the September/October form carried `needs-info` — the label
half of the review band (`docs/maintainer/intake-triage.md` §2) — and **12 of them had never been
asked for a cause**. The label half looks identical whether or not the comment half ran, so the
missing half was invisible for as long as it existed.

Two properties are pinned here, and the second one is the point:

1. the statistic is "labelled but never asked", not "labelled";
2. a non-zero value is a **failing exit status**, because that is the only form of this fact anything
   consumes. A script whose numbers are printed but never checked is the shape that produced the gap.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import audit_review_band as band  # noqa: E402


def _run(monkeypatch, intakes, asked_numbers):
    monkeypatch.setattr(band, "open_intakes", lambda: intakes)
    monkeypatch.setattr(band, "asked", lambda n: n in asked_numbers)
    return band.main([])


OLD = {"number": 1, "title": "[Intake] an old report", "createdAt": "2026-10-14T00:00:00Z"}
NEW = {"number": 2, "title": "[Intake] a new report", "createdAt": "2026-11-20T00:00:00Z"}


def test_a_completed_band_is_green(monkeypatch):
    assert _run(monkeypatch, [OLD, NEW], {1}) == 0


def test_an_unasked_old_form_intake_fails(monkeypatch):
    """The 2026-11-28 shape: labelled, never asked."""
    assert _run(monkeypatch, [OLD, NEW], set()) == 1


def test_the_current_form_is_not_the_band(monkeypatch):
    """A November intake has the Root Cause field; asking it would be noise, and passing on it is right."""
    assert _run(monkeypatch, [NEW], set()) == 0


def test_an_empty_read_is_not_a_pass(monkeypatch):
    """0/0 — the queue could not be read, which is not the same as a clean queue (#3759)."""
    assert _run(monkeypatch, [], set()) == 2


def test_the_bands_are_decided_by_form_generation_not_by_label(monkeypatch):
    """`needs-info` is written by two different producers (see `label_audit.CORPUS_ONLY`).

    It marks an intake awaiting a cause in this flow, and an issue awaiting a maintainer reply in
    others. Deciding the band from the label would pull both into one statistic; the field the form
    emitted is the fact that actually separates them.
    """
    assert band.band(1, "2026-10-31T23:59:59Z") == "old-form"
    assert band.band(1, "2026-11-01T00:00:00Z") == "current-form"


def test_the_marker_is_the_one_the_published_template_carries():
    """A different marker would re-comment every issue a second time.

    The template is in `docs/maintainer/intake-triage.md` §2 and in 90 comments already sent; the
    marker is the only stable identifier in it.
    """
    assert band.MARKER == "<!-- needs-root-cause -->"
    triage = (REPO / "docs" / "maintainer" / "intake-triage.md").read_text(encoding="utf-8")
    assert "needs-root-cause" in triage, (
        "the triage contract no longer mentions the marker; the band's replay guard depends on it")


def test_the_summary_mode_reads_a_payload_it_did_not_produce(tmp_path, capsys):
    """The workflow's summary step reads `band.json` from a file.

    That split exists because an inline `python3 - <<'PY'` block inside a YAML `run:` folds the
    document's indentation into the heredoc — the first version of this workflow did not parse at
    all. Keeping the formatting in the script means `yaml.safe_load` is the only reader of the YAML.
    """
    payload = tmp_path / "band.json"
    payload.write_text(
        '{"open_intakes": 180, "old_form": 90, "old_form_unasked": 2, "numbers": [1662, 2203]}',
        encoding="utf-8")
    assert band.main(["--summary", str(payload)]) == 0
    out = capsys.readouterr().out
    assert "never asked **2**" in out
    assert "#1662, #2203" in out
