#!/usr/bin/env python3
"""Every hardcoded static URL in the sitemap must be a file that exists.

Measured 2026-10-04: `https://misakanet.org/troubleshooting/` returned **404** while
`https://misakanet.org/troubleshooting.md` returned **200** — the sitemap advertised the directory
form of a page this site serves as a markdown file, and nothing noticed for as long as the entry
existed.

Why this can be checked offline, which is the point. The failure was not "a URL 404s on the
internet"; it was "a URL was written down that no file in this repository backs". That is decidable
from the tree, so it does not need a live probe that would be flaky under CI load and would go
stale the moment the CDN changes.

The two path shapes are genuinely different in this repo and both are legitimate:

- a trailing-slash URL is a directory — `docs/search/index.html` serves `/search/`
- a `.md` URL is served verbatim from the file — `docs/troubleshooting.md` serves `/troubleshooting.md`,
  the same route as `docs/agents/repo-operations.md` (see `docs/agents/repo-operations.md`, "部署后的
  验证习惯")

So the check maps each entry onto the file that serves it, rather than assuming one shape.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from build_lesson_pages import SITE_URL, generate_sitemap  # noqa: E402  (after sys.path)

DOCS = REPO / "docs"


def backing_file(path: str) -> Path | None:
    """The file in `docs/` that serves this site path, or None if nothing does."""
    rel = path[len(SITE_URL):].lstrip("/") if path.startswith(SITE_URL) else path.lstrip("/")
    if rel in ("", "index.html"):
        return DOCS / "index.html"
    if rel.endswith("/"):
        return DOCS / rel / "index.html"
    return DOCS / rel


def test_every_static_sitemap_entry_is_backed_by_a_file():
    """The 404 this catches was in the generator's own hardcoded list, so read it from there."""
    sitemap = generate_sitemap([], [])
    urls = re.findall(r"<loc>([^<]+)</loc>", sitemap)
    # The three hardcoded static pages come before the generated /topics/ and /lessons/ entries.
    static = [u for u in urls if "/topics" not in u and "/lessons/" not in u]
    assert len(static) == 3, f"expected the 3 hardcoded static pages, got {static}"

    missing = []
    for url in static:
        target = backing_file(url)
        if target is None or not target.exists():
            missing.append(f"{url}  (expected {target})")
    assert not missing, (
        "these sitemap URLs have no file behind them, so they are 404s in production:\n  "
        + "\n  ".join(missing)
        + "\nEither point the entry at the file that serves it, or create the page. Note that this "
        "site serves a markdown doc at `/name.md` but a directory at `/name/` — they are different "
        "routes, and the directory form of a markdown page is a 404."
    )


def _planned_sitemap_and_slugs() -> tuple[str, dict[str, str], list[dict]]:
    """Run the real planner and hand back its sitemap text, its slug map, and the lessons.

    The slug a lesson will be served at is decided by `plan_with_slugs` — sticky from the previous
    run, or derived from the title for a new one. A test that re-derived it would be testing its
    own guess, so this asks the generator instead.
    """
    import json

    from build_lesson_pages import (  # noqa: PLC0415  (after sys.path)
        LESSONS_JSON, SITEMAP, load_slug_map, plan_with_slugs,
    )

    lessons = json.loads((REPO / LESSONS_JSON).read_text(encoding="utf-8"))
    files, slug_map = plan_with_slugs(lessons, load_slug_map(REPO))
    return files[SITEMAP.as_posix()], slug_map, lessons


def _non_published(lessons: list[dict]) -> list[dict]:
    return [l for l in lessons
            if (l.get("status") or "published").strip().lower() != "published"]


def test_the_sitemap_advertises_no_non_published_lesson():
    """A sitemap entry is a machine-readable claim, and it has no field for "not published".

    Measured 2026-10-04: all 30 non-published lessons were listed at priority 0.6 / changefreq
    monthly, identical in shape to a published lesson. A sitemap entry cannot carry the
    "Draft (not published)" notice that the page and its meta description carry, so including one
    puts the state in a place where it cannot be expressed — the last surface where a draft and a
    published lesson are indistinguishable. The API already filters drafts
    (`misakanet/graphql/schema.py`), and `lessons/contrib/lesson-quality-requirements.md` says
    outright that drafts "are not indexed".
    """
    sitemap, slug_map, lessons = _planned_sitemap_and_slugs()
    listed = set(re.findall(r"<loc>([^<]+)</loc>", sitemap))

    offenders = []
    for lesson in _non_published(lessons):
        slug = slug_map.get(lesson.get("id", ""))
        if slug and f"{SITE_URL}/lessons/{slug}/" in listed:
            offenders.append(f"{SITE_URL}/lessons/{slug}/  (status: {lesson.get('status')})")

    assert not offenders, (
        f"{len(offenders)} non-published lesson(s) are advertised in the sitemap. A consumer of this "
        f"file cannot tell them from a published lesson — the state has nowhere to go:\n"
        + "\n".join(f"  {o}" for o in offenders[:20]))


def test_a_non_published_lesson_still_gets_a_page():
    """The counterweight, so the sitemap fix cannot quietly become "stop serving drafts".

    Drafts are labelled, not hidden: the page carries a visible "Draft (not published)" notice
    (#2794, "like the API already does"). This test fails if anyone later "fixes" the sitemap by
    dropping draft pages instead, which would remove the review surface rather than the claim.
    """
    import json

    from build_lesson_pages import LESSONS_JSON, load_slug_map, plan_with_slugs  # noqa: PLC0415

    lessons = json.loads((REPO / LESSONS_JSON).read_text(encoding="utf-8"))
    files, slug_map = plan_with_slugs(lessons, load_slug_map(REPO))
    drafts = _non_published(lessons)
    assert drafts, (
        "no non-published lesson exists in data/lessons.json, so this test can no longer tell "
        "'drafts are labelled' from 'drafts are gone'. That distinction is the whole point.")

    missing = [slug_map.get(l.get("id", "")) for l in drafts]
    without_page = [s for s in missing if not s or f"docs/lessons/{s}/index.html" not in files]
    assert not without_page, (
        f"{len(without_page)} non-published lesson(s) lost their page. They should be labelled, "
        f"not removed:\n  " + "\n  ".join(str(s) for s in without_page[:20]))


def test_the_committed_sitemap_matches_its_generator():
    """`--check` exists to catch exactly this: the tree, the generator and the published file
    drifting apart. Regenerating and diffing is the cheap half of the guard."""
    from build_lesson_pages import generate_sitemap as gen  # noqa: F401  (explicit re-read)

    committed = (DOCS / "sitemap.xml").read_text(encoding="utf-8")
    rebuilt = gen([], [])
    # Only compare the static block; the lesson and topic entries depend on the corpus.
    def static_block(text: str) -> list[str]:
        return [l for l in text.splitlines() if "<loc>" in l and "/topics" not in l and "/lessons/" not in l]

    assert static_block(committed) == static_block(rebuilt), (
        "docs/sitemap.xml disagrees with generate_sitemap() about the static pages — one of them was "
        "edited by hand, or the generator changed without the file being regenerated.\n"
        f"  committed: {static_block(committed)}\n  generated: {static_block(rebuilt)}"
    )


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"  {name} ... ", end="", flush=True)
            try:
                fn()
                print("PASS")
            except Exception as e:
                print(f"FAIL: {e}")
