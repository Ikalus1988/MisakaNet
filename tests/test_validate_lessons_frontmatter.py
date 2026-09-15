#!/usr/bin/env python3
"""`validate_lessons.extract_frontmatter` must read every frontmatter form in the corpus.

Background — the false failure this pins
---------------------------------------
Many lessons carry **JSON frontmatter followed by a YAML-ish `provenance:` tail** inside
the same ``---`` block. The D1 sync and ``update_lessons_json`` read those with
``json.JSONDecoder().raw_decode`` (documented in ``sync_lessons_to_d1.parse_frontmatter``),
but the schema validator used ``json.loads``, which raises ``Extra data`` on the tail. It
then fell through to its line-based YAML reader — which cannot read a JSON object — and
returned a dict without ``title``/``domain``.

Nothing noticed because the validator only looks at *changed* lesson files: the failure
appeared as soon as a domain rewrite touched 25+ ``lessons/en/*`` files and CI reported
``'title' is a required property`` for lessons that had been valid all along (2026-09-15).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.validate_lessons import extract_frontmatter  # noqa: E402

JSON_WITH_PROVENANCE = """---
{
  "title": "Restart long-lived earn loops after code fixes",
  "domain": "devops",
  "tags": ["ops", "restart"],
  "status": "published",
  "created": "2026-07-24",
  "confidence": "0.9"
}
provenance:
  source: "external"
  contributor: "someone"
---

## Problem

Something went wrong.
"""

PRETTY_JSON = """---
{
  "title": "A pretty-printed JSON lesson",
  "domain": "devops",
  "tags": ["ops"],
  "status": "published"
}
---

## Problem

Body.
"""

YAML_FRONTMATTER = """---
title: A plain YAML lesson
domain: devops
tags: [ops, yaml]
status: published
---

## Problem

Body.
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "lesson.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_json_frontmatter_with_a_provenance_tail_keeps_title_and_domain(tmp_path):
    """The exact shape that produced the false schema failure."""
    fm, err = extract_frontmatter(_write(tmp_path, JSON_WITH_PROVENANCE))
    assert err is None, err
    assert fm["title"] == "Restart long-lived earn loops after code fixes"
    assert fm["domain"] == "devops"
    assert fm["tags"] == ["ops", "restart"]
    # The tail must not be mistaken for frontmatter keys.
    assert "provenance" not in fm


def test_pretty_printed_json_frontmatter_still_parses(tmp_path):
    fm, err = extract_frontmatter(_write(tmp_path, PRETTY_JSON))
    assert err is None, err
    assert fm["title"] == "A pretty-printed JSON lesson"


def test_yaml_frontmatter_still_parses(tmp_path):
    """The fallback reader must keep working: most of the corpus is YAML."""
    fm, err = extract_frontmatter(_write(tmp_path, YAML_FRONTMATTER))
    assert err is None, err
    assert fm["title"] == "A plain YAML lesson"
    assert fm["domain"] == "devops"


def test_every_json_frontmatter_lesson_in_the_corpus_reads_its_title():
    """Scan rather than hardcode, so the corpus can move without breaking this."""
    checked = 0
    broken = []
    for path in (REPO / "lessons").rglob("*.md"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            continue
        block_start = text.find("{", 4, 400)
        if block_start == -1 or text[4:block_start].strip():
            continue  # not a JSON-frontmatter lesson
        fm, err = extract_frontmatter(path)
        checked += 1
        if err or not (fm or {}).get("title"):
            broken.append((path.relative_to(REPO).as_posix(), err))
    assert checked > 0, "no JSON-frontmatter lesson found — this scan needs updating"
    assert broken == [], f"JSON-frontmatter lessons whose title cannot be read: {broken}"


def test_the_provenance_tail_is_valid_json_on_its_own_terms():
    """Guard the guard: the fixture really does break a naive `json.loads`."""
    raw = JSON_WITH_PROVENANCE.split("---")[1].strip()
    try:
        json.loads(raw)
    except json.JSONDecodeError as exc:
        assert "Extra data" in str(exc)
    else:
        raise AssertionError("the fixture no longer reproduces the parse failure")
