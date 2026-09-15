#!/usr/bin/env python3
"""The domain vocabulary is data, and the corpus is held to it (issue #1687).

Background — what went wrong
---------------------------
Domain values had accumulated by accretion: 56 of them, including ``contrib`` (the
*directory* a lesson lives in, used as a topic for 39 lessons), ``devops`` vs ``ops``,
``network`` vs ``networking``, ``agent``/``agents``/``ai-agents``, ``ruby/performance``
and ``memory_management``. Nobody could review that list because it was never written
down: ``lesson_gate.allowed_domains()`` accepted every value *any lesson already used*,
so the first lesson to spell a domain a new way legalized that spelling forever.

``data/domains.json`` is now the review surface — canonical values, aliases, retired
values, and the per-lesson replacement for the directory-shaped ones — and this file
pins the invariants that keep it honest:

1. the vocabulary is well formed (unique canonical values, aliases that point at
   canonical values and never at each other, retired values that are not canonical);
2. the corpus carries nothing else (via ``normalize_domains.py --check``, the same gate
   CI runs);
3. the gate and the checker read the same list, so they cannot disagree;
4. an unknown domain is actually rejected — the guard is not vacuous.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import lesson_gate  # noqa: E402
from scripts import normalize_domains  # noqa: E402

VOCAB = json.loads((REPO / "data" / "domains.json").read_text(encoding="utf-8"))


def test_vocabulary_is_well_formed():
    canonical = VOCAB["canonical"]
    assert canonical, "the vocabulary must list canonical values"
    assert len(canonical) == len(set(canonical)), "duplicate canonical value"
    assert canonical == sorted(canonical), "canonical list should stay sorted"
    assert all(v == v.strip().lower() and " " not in v.strip() or " " in v for v in canonical)
    for value in canonical:
        # A domain names a topic: no slashes (that how `ruby/performance` happened),
        # no underscores (`memory_management`), lowercase, no stray whitespace.
        assert "/" not in value, f"{value!r} looks like a path, not a domain"
        assert "_" not in value, f"{value!r} uses underscores"
        assert value == value.strip().lower(), f"{value!r} is not normalized"
    assert "contrib" not in canonical, "a directory name must never be a domain again"


def test_aliases_point_at_canonical_values():
    """The invariant that was missing when this file was written.

    `ruby/performance → ruby` and `memory_management → memory` mapped onto values that
    were not in the canonical list, so the corpus ended up carrying values the
    vocabulary did not contain — the checker reported the lessons it had just fixed.
    """
    canonical = set(VOCAB["canonical"])
    aliases = VOCAB.get("aliases") or {}
    for source, target in aliases.items():
        assert source not in canonical, f"{source!r} is both canonical and an alias"
        assert target in canonical, f"{source!r} → {target!r}, which is not canonical"
    assert not (set(aliases) & canonical), "an alias must not shadow a canonical value"


def test_retired_values_are_documented_and_not_canonical():
    canonical = set(VOCAB["canonical"])
    for value, reason in (VOCAB.get("retired") or {}).items():
        assert value not in canonical, f"{value!r} is retired but still canonical"
        assert reason and len(reason) > 10, f"{value!r} needs a reason a reviewer can read"


def test_contrib_replacement_targets_are_canonical():
    canonical = set(VOCAB["canonical"])
    for path, target in (VOCAB.get("contrib_replacement") or {}).items():
        assert target in canonical, f"{path} → {target!r}, which is not canonical"


def test_notes_only_describe_known_values():
    known = set(VOCAB["canonical"]) | set(VOCAB.get("aliases") or {})
    for value in (VOCAB.get("notes") or {}):
        assert value in known, f"note for unknown value {value!r}"


def test_every_lesson_domain_is_canonical():
    """The gate CI runs, run here so a bad domain fails in the test suite too."""
    proc = subprocess.run([sys.executable, str(REPO / "scripts" / "normalize_domains.py"), "--check"],
                          cwd=REPO, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_gate_and_checker_read_the_same_vocabulary():
    """Two readers of one list: if these drift, one of them is lying."""
    assert lesson_gate.allowed_domains() == {v.lower() for v in VOCAB["canonical"]}


def test_gate_rejects_a_domain_outside_the_vocabulary(tmp_path):
    """Guard the guard: the rejection path must actually fire."""
    lesson = tmp_path / "not-a-domain-lesson.md"
    lesson.write_text(
        "---\n"
        "title: A lesson with an invented domain\n"
        "domain: totally-made-up\n"
        "tags: [one, two]\n"
        "status: published\n"
        "evidence_level: E1\n"
        "---\n\n"
        "## Problem\n\nSomething broke.\n\n"
        "## Root Cause\n\nA reason.\n\n"
        "## Solution\n\nA fix.\n\n"
        "## Verification\n\n`pytest -q`\n",
        encoding="utf-8",
    )
    errors = lesson_gate.validate_lesson(lesson) if hasattr(lesson_gate, "validate_lesson") else None
    if errors is None:  # the gate exposes only the CLI; exercise that
        proc = subprocess.run([sys.executable, str(REPO / "scripts" / "lesson_gate.py"), str(lesson)],
                              cwd=REPO, capture_output=True, text=True, timeout=120)
        assert proc.returncode != 0, proc.stdout
        assert "totally-made-up" in proc.stdout + proc.stderr
        return
    assert any("totally-made-up" in e for e in errors), errors


def test_public_domain_count_is_derived_from_the_vocabulary():
    """The published number counts canonical values in use — nothing else.

    `sync_lesson_count.canonical_domains()` is the definition behind the "N domains"
    copy and the domains badge, so it has to agree with the vocabulary *and* with the
    corpus: a value the vocabulary does not list must not be countable, and every
    counted value must be listed.
    """
    from scripts import sync_lesson_count as slc

    counted_dirs = ("core", "contrib", "en")  # the dirs the public count covers
    counted = set()
    for path in (REPO / "lessons").rglob("*.md"):
        if path.name in normalize_domains.EXCLUDED or path.name.startswith("."):
            continue
        if path.relative_to(REPO / "lessons").parts[0] not in counted_dirs:
            continue
        domain = slc._lesson_domain(path)
        if domain:
            counted.add(domain)

    assert counted <= set(VOCAB["canonical"]), sorted(counted - set(VOCAB["canonical"]))
    assert slc.canonical_domains(REPO) == len(counted)
