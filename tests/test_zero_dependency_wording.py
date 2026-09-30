#!/usr/bin/env python3
"""A retired slogan may survive only as history (intake #2486, owner decision D2).

`zero-dependency` / 零依赖 was used for "no third-party packages" and read as "nothing to prepare" — while a
**Python ≥ 3.10 interpreter** is a hard prerequisite and the optional `--semantic` path downloads a large
model. A reader reported the misreading, so the term is **retired** in current copy in favour of
`stdlib-only (no third-party packages)`, and this file is what keeps it retired.

Two rules, both mechanism-shaped:

1. the retired phrases do not appear in current, user-facing copy — dated snapshots, the corpus and tests are
   history and may quote them;
2. a surface that makes the claim must also state the prerequisite in the same file, because "no third-party
   packages" is only honest next to "Python ≥ 3.10 required".
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

RETIRED = re.compile(r"zero[- ]dep(?:endency|endencies|s)?|零依赖", re.IGNORECASE)

# History keeps its wording: dated snapshots, transcripts, corpus material and the tests that quote the
# report. Each entry is a directory whose files are records rather than current guidance.
HISTORY = (
    "archive/", "data/", "lessons/", "tasks/", "tests/",
    "docs/adr/", "docs/agents/crawler-intake-bot.md", "docs/baseline/", "docs/benchmarks/", "docs/blog/",
    "docs/bounty-notes/", "docs/data/", "docs/field-reports/", "docs/journey-reports/", "docs/lessons/",
    "docs/maintainer/", "docs/openclaw-pr/", "docs/prd/", "docs/releases/", "docs/reports/",
    "docs/reviews/", "docs/roadmap/",
)

# The glossary is where the retirement itself is recorded, so the phrase must appear there.
GLOSSARY = "docs/glossary.md"

# Surfaces that make the stdlib-only claim to a newcomer; each must state the prerequisite it is next to.
CLAIM_SURFACES = ("README.md", "README.zh-CN.md", "docs/dsh-installation.md", "docs/LIMITATIONS.md",
                  "docs/CONCEPTS.md")
CLAIM = re.compile(r"stdlib-only|纯标准库|standard library|标准库", re.IGNORECASE)
PREREQUISITE = re.compile(r"3\.10")


def user_facing_files(root: Path | None = None) -> list[Path]:
    repo = Path(root) if root is not None else REPO
    files = []
    for path in sorted(repo.rglob("*")):
        if not path.is_file() or path.suffix not in (".md", ".html", ".json", ".py"):
            continue
        rel = path.relative_to(repo).as_posix()
        if rel.startswith((".git/",)) or "node_modules" in rel:
            continue
        if any(rel.startswith(prefix) for prefix in HISTORY):
            continue
        files.append(path)
    return files


def retired_phrase_offenders(root: Path | None = None) -> list[str]:
    repo = Path(root) if root is not None else REPO
    offenders = []
    for path in user_facing_files(repo):
        rel = path.relative_to(repo).as_posix()
        if rel == GLOSSARY:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if RETIRED.search(line):
                offenders.append(f"{rel}:{number}: {line.strip()[:100]}")
    return offenders


def main() -> int:
    offenders = retired_phrase_offenders()
    missing = [rel for rel in CLAIM_SURFACES
               if CLAIM.search((REPO / rel).read_text(encoding="utf-8"))
               and not PREREQUISITE.search((REPO / rel).read_text(encoding="utf-8"))]
    if not offenders and not missing:
        print("OK no current copy uses the retired slogan, and every claim surface states Python >= 3.10")
        return 0
    for line in offenders:
        print(f"retired slogan in current copy: {line}")
    for rel in missing:
        print(f"claims stdlib-only without the interpreter prerequisite: {rel}")
    return 1


def test_no_current_copy_uses_the_retired_slogan():
    offenders = retired_phrase_offenders()
    assert not offenders, (
        "these current, user-facing lines still use the retired slogan (use `stdlib-only (no third-party "
        "packages)`; if the line is a dated record, move it under one of the HISTORY prefixes):\n  - "
        + "\n  - ".join(offenders))


def test_the_slogan_rule_notices_a_current_use(tmp_path):
    """Guard: the rule reads the repository, so its red case needs a fixture."""
    (tmp_path / "guide.md").write_text("Install with zero dependencies.\n", encoding="utf-8")
    offenders = retired_phrase_offenders(tmp_path)
    assert offenders and "guide.md" in offenders[0], offenders
    # …and a file under a HISTORY prefix is a record, not current copy.
    (tmp_path / "docs" / "journey-reports").mkdir(parents=True)
    (tmp_path / "docs" / "journey-reports" / "2026-07-18-note.md").write_text(
        "zero-dependency core\n", encoding="utf-8")
    assert retired_phrase_offenders(tmp_path) == offenders, (
        "a dated journey report is history and must keep its wording")


def test_every_surface_that_claims_stdlib_only_states_the_prerequisite():
    missing = []
    for rel in CLAIM_SURFACES:
        text = (REPO / rel).read_text(encoding="utf-8")
        if CLAIM.search(text) and not PREREQUISITE.search(text):
            missing.append(rel)
    assert not missing, (
        "these files claim stdlib-only without saying that a Python >= 3.10 interpreter is still required, "
        "which is the misreading a reader reported: " + ", ".join(missing))


def test_the_glossary_records_the_retirement():
    glossary = (REPO / GLOSSARY).read_text(encoding="utf-8")
    assert "Retired terms" in glossary and RETIRED.search(glossary), (
        "the term's history belongs in the glossary: without it the next reader re-invents the slogan")
