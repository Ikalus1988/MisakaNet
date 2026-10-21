#!/usr/bin/env python3
"""Which pages the site's gates cover — one definition, four callers (#3541, §122.6).

**The bug this file exists to kill.** "Which pages are in scope" was written out three times —
in `check_design_convergence.py`, in `sync_design_tokens.py` and in `sync_site_partials.py` — and
each copy said the same thing: *every `docs/**/*.html` except `_partials/`, `lessons/` and
`topics/`*. Three copies of one rule is three rules to keep in sync, and the repo's own history
calls this bug class out by name: "都是同一种病：两个作者各写一份" (two authors, one rule) —
handoff §122.3. A copy that is merely *behind* is a silent hole; a copy that is merely *ahead* is
a page nobody gated.

**What changed, and why it matters.** The generated lesson and topic pages were outside the
partition, so the design-convergence gate read 14 hand-written pages and called the site
converged while 571 pages carried their own hardcoded palette (handoff §122.6 item 2: "生成的 571
个课程页**不在门禁范围内**（判据 1 / 11 只查 14 个手写页面）"). They are in scope now, and the
generator — not a hand edit — is what puts them there.

**The partition, in one place.** Three sets, defined once:

* *partials* (`docs/_partials/`) — sources, not pages. They are copied into pages; they are never
  pages themselves.
* *generated* (`docs/lessons/`, `docs/topics/`) — written by `scripts/build_lesson_pages.py`. The
  generator is their only writer, so the sync scripts may **check** them but never rewrite them.
* *scoped* — everything else under `docs/`: the hand-written pages.

`gated_pages()` is the union of *scoped* and *generated*: every page a reader can reach, and
therefore every page the design gate reads.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = Path("docs")

#: The directory of shared *sources* — the token block and the site-links row. Its `.html` files
#: are copied into pages; they are not pages.
PARTIALS_DIR = "_partials"

#: The generated trees. `scripts/build_lesson_pages.py` owns them; nothing else writes them.
GENERATED_TREES = ("lessons", "topics")


def is_generated(rel: Path) -> bool:
    """Whether this path (relative to `docs/`) is inside a generated tree."""
    return any(part in GENERATED_TREES for part in rel.parts)


def is_scoped(rel: Path) -> bool:
    """Whether this path (relative to `docs/`) is a hand-written page.

    The hand-written pages are the ones a script may *rewrite* in place. The generated ones are
    not: their writer is the generator, and a second writer is how a page ends up with two
    sources of truth (the bug class §122.3 names).
    """
    if PARTIALS_DIR in rel.parts:
        return False
    return not is_generated(rel)


def html_pages(root: Path = REPO) -> list[Path]:
    """Every `.html` file under `docs/`, partials included."""
    return sorted((root / DOCS).rglob("*.html"))


def scoped_pages(root: Path = REPO) -> list[Path]:
    """The hand-written pages — the ones a sync script may rewrite."""
    return [page for page in html_pages(root)
            if is_scoped(page.relative_to(root / DOCS))]


def generated_pages(root: Path = REPO) -> list[Path]:
    """The generated lesson and topic pages."""
    return [page for page in html_pages(root)
            if is_generated(page.relative_to(root / DOCS))]


def gated_pages(root: Path = REPO) -> list[Path]:
    """Every page a reader can reach: the hand-written ones and the generated ones.

    This is what the design-convergence gate reads. Excluding the generated tree from it is what
    left 571 pages unwatched (handoff §122.6 item 2).
    """
    return [page for page in html_pages(root)
            if PARTIALS_DIR not in page.relative_to(root / DOCS).parts]
