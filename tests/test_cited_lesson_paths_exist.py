#!/usr/bin/env python3
"""A doc that cites a lesson path must cite one that exists — the narrow version of a broad idea.

Why narrow, and why only lessons
--------------------------------
While fixing #2396 (three published lessons were invisible because they sat at the root of `lessons/`) the
six path references left behind were found by hand. The obvious follow-up — "every path in backticks in
`docs/**` must exist" — was measured and **rejected**: 69 such paths are absent across 35 documents, and
almost all of them are *correct prose* in one of four legitimate shapes:

1. **history** — `docs/maintainer/handoff-2026-09-12.md` names `workers/register-proxy.js`, which was the
   name that file had that week; `ROADMAP.md`'s adjudication table names `scripts/freshness_scorer.py` and
   says in the same row that it does not exist;
2. **a tombstone** — four documents name `data/counter.json` to explain that it was deleted on 2026-09-28;
3. **an input that has not been produced yet** — `docs/reputation.md` names `data/usage_reports.json`,
   which is exactly the path `scripts/reputation.py` reads and creates on first use;
4. **a plan** — `docs/ring0-founder-track.md` says "Update `docs/plans/ring-system.md`", a document that
   was never written.

A gate that flags all four is a gate that gets switched off, and an exemption table covering them would be
80% of the gate. So the rule is the one shape that has **no legitimate exception** and that this repository
renames often (three lessons moved today, and lesson files get renamed whenever a title changes): *if a
maintained document tells a reader to read `lessons/…md`, that file must be there.* Dated and historical
documents are out of scope — they are records, and a record that names the path a file had at the time is
not a defect (the same reason `ROADMAP.md`'s snapshot keeps its old numbers).

Measured when this was added: two findings, both in `docs/email-intake-examples.md`, where an example
claimed an intake had been "published as `lessons/contrib/…md`" for a lesson the corpus never had. They are
fixed in the same change by dropping the filename (the example is about the intake, not the file).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"

# Documents that describe the repository as it is *today*. Dated snapshots, reviews, handoffs, PRDs and
# reports are records: their paths belong to the day they were written.
HISTORICAL = (
    "docs/maintainer/handoff-", "docs/reviews/", "docs/blog/", "docs/releases/", "docs/prd/",
    "docs/journey-reports/", "docs/bounty-notes/", "docs/roadmap/", "docs/benchmarks/",
    "docs/field-reports/", "docs/reports/", "docs/data/", "docs/archive/", "docs/community/",
    "docs/articles/", "docs/adr/", "docs/baseline/", "docs/analytics/", "docs/topics/",
    "docs/lessons/", "docs/maintainer/capability-inventory-", "docs/maintainer/state-of-the-repo.md",
    "docs/maintainer/handoff", "docs/agents/ci-failure-pattern-analysis-",
)
DATED = re.compile(r"-\d{4}-\d{2}-\d{2}(?:-[a-z0-9-]+)?\.md$")
# `lessons/…md` inside backticks. Placeholders (`<slug>`, `*`, `YYYY`) are not citations of a file.
CITATION = re.compile(r"`(lessons/[A-Za-z0-9._/-]+\.md)`")


def maintained_docs(docs: Path = DOCS, repo: Path = REPO) -> list[Path]:
    """Every markdown document that describes the repository as it is now."""
    candidates = list(docs.rglob("*.md")) + [repo / name for name in
                                             ("README.md", "AGENTS.md", "ARCHITECTURE.md", "JOIN.md",
                                              "CONTRIBUTING.md", "ROADMAP.md", "DEPLOYMENT.md", "API.md")]
    kept = []
    for path in candidates:
        if not path.is_file():
            continue
        posix = path.relative_to(repo).as_posix()
        if any(posix.startswith(prefix) for prefix in HISTORICAL) or DATED.search(posix):
            continue
        kept.append(path)
    return sorted(kept)


def stale_citations(docs: Path = DOCS, repo: Path = REPO) -> list[str]:
    found = []
    for path in maintained_docs(docs, repo):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in CITATION.finditer(text):
            cited = match.group(1)
            if any(ch in cited for ch in ("<", ">", "*", "{")):
                continue
            if not (repo / cited).is_file():
                line = text.count("\n", 0, match.start()) + 1
                found.append(f"{path.relative_to(repo).as_posix()}:{line}: {cited}")
    return found


def test_the_scan_covers_the_documents_it_claims_to():
    """A glob that matched nothing (or two files) would make the gate below vacuous."""
    docs = maintained_docs()
    assert len(docs) > 40, f"only {len(docs)} maintained documents scanned — the filter moved"
    citations = sum(len(CITATION.findall(p.read_text(encoding="utf-8", errors="ignore"))) for p in docs)
    # Measured 2026-09-28: 15 citations across the maintained documents. The number is small because most
    # lesson references live in the historical trees (which this gate deliberately does not scan) — what
    # matters is that it is not zero and does not quietly become zero.
    assert citations >= 10, f"only {citations} lesson citations found — the pattern moved"


def test_every_cited_lesson_path_exists():
    stale = stale_citations()
    assert stale == [], (
        "these documents tell a reader to open a lesson file that is not there:\n  - "
        + "\n  - ".join(stale)
        + "\nRename the citation (a lesson file's path changes when the title changes), or — if the "
        "document is describing what *used to be* there — move it into the historical tree, where a path "
        "from its own week is a record rather than a claim."
    )


def test_the_rule_can_fail(tmp_path: Path) -> None:
    """The control: a fixture document citing a lesson that does not exist must be reported."""
    docs = tmp_path / "docs"
    (docs / "agents").mkdir(parents=True)
    (tmp_path / "lessons" / "contrib").mkdir(parents=True)
    (tmp_path / "lessons" / "contrib" / "real.md").write_text("# real\n", encoding="utf-8")
    (docs / "agents" / "guide.md").write_text(
        "Read `lessons/contrib/real.md`, then `lessons/contrib/gone.md`.\n", encoding="utf-8")
    found = stale_citations(docs, tmp_path)
    assert len(found) == 1 and "gone.md" in found[0], found

    # And a historical document is not scanned: the same citation there is a record, not a claim.
    (docs / "maintainer").mkdir()
    (docs / "maintainer" / "handoff-2026-01-01.md").write_text(
        "Then we had `lessons/contrib/gone.md`.\n", encoding="utf-8")
    assert stale_citations(docs, tmp_path) == found, stale_citations(docs, tmp_path)
