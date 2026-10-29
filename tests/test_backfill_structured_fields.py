#!/usr/bin/env python3
"""`scripts/backfill_structured_fields.py` — the parser and the writer, not the model.

The measured reason this tool exists in *propose* mode: 394 of 651 lessons (61%) have no
`summary_plain`/`trigger`/`verify`, and `AGENTS.md` tells an agent to read `summary_plain` aloud
verbatim on a hit. Without it the agent paraphrases the Problem section, which is the thing the field
was added to prevent.

The measured reason it is not run in bulk: the models available on the included tier are not good
enough. Three were tried on the same lessons —

    8b    "Manual merge bottleneck fixed with auto-merge CI pipeline"
    70b   "Manual merge broke, auto CI pipeline fixed it"      (and, on a Chinese lesson, a
                                                                 truncated mixed-language fragment)
    32b   "Manual merges slow down PR processing; auto-merge CI pipeline automates checks, tests, and"
           (cut mid-sentence)

A vague sentence in a field the reading contract quotes verbatim is worse than an empty one: empty is
honest, vague is an instruction to say something useless. So the generator stays a review tool and the
tests pin the two parts that must be right when a human does run it.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import backfill_structured_fields as backfill  # noqa: E402


def test_a_json_object_inside_prose_is_accepted():
    raw = 'Sure!\n{"summary_plain": "a", "trigger": "b", "verify": "c"}\nDone.'
    assert backfill.parse_fields(raw) == {"summary_plain": "a", "trigger": "b", "verify": "c"}


def test_a_missing_field_rejects_the_whole_object():
    """Half a record would leave the lesson with an empty field and no signal that it failed."""
    assert backfill.parse_fields('{"summary_plain": "a", "trigger": "b"}') is None


def test_an_empty_or_unparseable_answer_is_a_failure():
    assert backfill.parse_fields("no json here") is None
    assert backfill.parse_fields('{"summary_plain": "", "trigger": "b", "verify": "c"}') is None


def test_newlines_are_flattened_because_the_field_is_quoted_inline():
    fields = backfill.parse_fields('{"summary_plain": "a\\nb", "trigger": "b", "verify": "c"}')
    assert fields["summary_plain"] == "a b"


def test_the_writer_inserts_keys_before_the_closing_fence(tmp_path, monkeypatch):
    lesson = tmp_path / "lessons" / "core" / "x.md"
    lesson.parent.mkdir(parents=True)
    lesson.write_text("---\ntitle: x\n---\n\n## Problem\nboom\n", encoding="utf-8")
    monkeypatch.setattr(backfill, "LESSONS_DIR", tmp_path / "lessons")
    row = {"url": "lessons/core/x.md"}
    assert backfill.in_frontmatter(row, {"summary_plain": "s", "trigger": "t", "verify": "v"})
    text = lesson.read_text(encoding="utf-8")
    assert text.startswith("---\ntitle: x\n")
    assert 'summary_plain: "s"' in text
    assert text.index("verify:") < text.index("\n---", 3)


def test_the_writer_is_idempotent(tmp_path, monkeypatch):
    """Re-running a batch must not duplicate keys — the failure mode of a resumable backfill."""
    lesson = tmp_path / "lessons" / "core" / "x.md"
    lesson.parent.mkdir(parents=True)
    lesson.write_text("---\ntitle: x\n---\n\n## Problem\nboom\n", encoding="utf-8")
    monkeypatch.setattr(backfill, "LESSONS_DIR", tmp_path / "lessons")
    row = {"url": "lessons/core/x.md"}
    fields = {"summary_plain": "s", "trigger": "t", "verify": "v"}
    assert backfill.in_frontmatter(row, fields)
    assert not backfill.in_frontmatter(row, fields)
    assert lesson.read_text(encoding="utf-8").count("summary_plain:") == 1
