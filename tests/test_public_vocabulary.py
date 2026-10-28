#!/usr/bin/env python3
"""`data/public-vocabulary.json` is an answer key, so it has to be the key, not a copy of the paper.

Two properties, both load-bearing for the lesson gate:

1. **It is in sync with the corpus.** A stale key means legitimate new public tools get flagged (or,
   worse, a token that used to be rare silently becomes "known"). Regenerating is one command, so
   drift has no excuse.
2. **It is built from lesson *bodies*, not just the metadata index.** Measured when the rule was
   written: a metadata-only vocabulary missed ordinary public tools that appear only inside a lesson
   (`unzip`, `copy-item`, `new-item`) and the gate flagged 47 of 651 lessons for writing about public
   software. The bodies are where a corpus actually keeps its words.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import export_public_vocabulary as exporter  # noqa: E402

VOCAB_FILE = REPO / "data" / "public-vocabulary.json"


def test_the_committed_vocabulary_matches_a_fresh_build():
    committed = json.loads(VOCAB_FILE.read_text(encoding="utf-8"))
    fresh = exporter.build()
    assert committed["corpus"] == fresh["corpus"], (
        "data/public-vocabulary.json is out of date — run "
        "`python3 scripts/export_public_vocabulary.py`")


def test_the_allowlist_is_preserved_across_regeneration():
    """The allowlist is the only hand-edited part; a rebuild must never silently drop it."""
    committed = json.loads(VOCAB_FILE.read_text(encoding="utf-8"))
    assert committed["allowlist"] == sorted(set(committed["allowlist"])), "allowlist must be sorted"
    assert exporter.build()["allowlist"] == committed["allowlist"], (
        "regenerating must preserve the allowlist — it is the human-asserted half")


def test_the_vocabulary_contains_body_only_words():
    """A word that appears only in a lesson body must be in the key, or the gate flags public tools."""
    tokens = set(json.loads(VOCAB_FILE.read_text(encoding="utf-8"))["corpus"])
    # `unzip` is the measured example: present in lesson bodies, absent from the metadata index.
    assert "unzip" in tokens
    assert "pytest" in tokens
    # And the motivating negative: an internal platform name is not in the public corpus.
    assert "mico" not in tokens


def test_check_mode_fails_on_a_tampered_key(tmp_path, monkeypatch, capsys):
    """The gate must go red when someone edits the corpus list by hand."""
    tampered = dict(json.loads(VOCAB_FILE.read_text(encoding="utf-8")))
    tampered["corpus"] = [t for t in tampered["corpus"] if t != "pytest"]
    target = tmp_path / "public-vocabulary.json"
    target.write_text(json.dumps(tampered), encoding="utf-8")
    monkeypatch.setattr(exporter, "TARGET", target)
    assert exporter.main(["--check"]) == 1
    assert "out of date" in capsys.readouterr().err
