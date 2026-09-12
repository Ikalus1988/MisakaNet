#!/usr/bin/env python3
"""Generated lesson/topic page invariants (2026-09-12).

Background — what these tests prevent
-------------------------------------
`scripts/build_lesson_pages.py` existed but nothing ran it: one hand-run left the
site serving 205 lesson pages for 378 lessons, 88 pages for titles that no longer
existed, and topic pages whose counts froze at generation time
(`docs/topics/contrib` advertised "176 verified failure lessons" while the index
held 330). Three properties have to hold for a generator to be safe to run in a
loop, and each one is a real bug that was present:

1. **Idempotent** — a second run over its own output changes nothing.
2. **It owns its output** — pages it stops generating are pruned, but only pages
   it generated (never a hand-written file that happens to sit in the tree).
3. **It matches the index** — every page on disk equals what the current
   `data/lessons.json` would produce (the gate the daily job and docs.yml use).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import build_lesson_pages as blp  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

LESSONS = [
    {"id": "bravo", "title": "Bravo lesson", "domain": "contrib", "summary": "b", "tags": ["x"], "url": "lessons/contrib/b.md"},
    {"id": "alpha", "title": "Alpha lesson", "domain": "contrib", "summary": "a", "tags": ["x"], "url": "lessons/contrib/a.md"},
    {"id": "ops-one", "title": "Ops lesson", "domain": "ops", "summary": "o", "tags": ["y"], "url": "lessons/ops/o.md"},
]


def test_repo_pages_match_the_index():
    """The gate: every generated page equals what the CLI would write.

    This used to call `plan(lessons)` — no slug map — while the CLI runs
    `plan_with_slugs(lessons, load_slug_map(root))`. The two only agree while every
    lesson's slug still equals its title-derived slug, so the moment the index
    gained real titles (instead of slug-as-title) this gate reported 653 "missing"
    pages that the CLI had deliberately not created: sticky URLs. A gate that
    exercises a different entry point than the tool it guards is not a gate
    (2026-09-12).
    """
    lessons = json.loads((REPO / "data" / "lessons.json").read_text(encoding="utf-8"))
    known_slugs = blp.load_slug_map(REPO)
    files, slug_map = blp.plan_with_slugs(json.loads(json.dumps(lessons)), known_slugs)
    problems = blp.check(files, root=REPO)
    assert problems == [], (
        "generated pages drifted from data/lessons.json:\n  - "
        + "\n  - ".join(problems[:15])
        + f"\n({len(problems)} path(s)) — fix: python3 scripts/build_lesson_pages.py"
    )

    # The manifest is what keeps live URLs sticky; a slug whose page vanished is a
    # 404 that no page-level comparison would notice.
    dead = [f"{lesson_id} -> {slug}" for lesson_id, slug in slug_map.items()
            if f"docs/lessons/{slug}/index.html" not in files]
    assert dead == [], f"recorded slugs with no generated page (dead URLs): {dead[:5]}"
    manifest = json.loads((REPO / blp.MANIFEST).read_text(encoding="utf-8"))
    assert manifest["pages"] == sorted(files), "the manifest lists a different page set"


def test_generation_is_idempotent(tmp_path):
    files = blp.plan(json.loads(json.dumps(LESSONS)))
    first = blp.sync(files, root=tmp_path)
    assert first["written"], "nothing was written on the first run"
    second = blp.sync(blp.plan(json.loads(json.dumps(LESSONS))), root=tmp_path)
    assert second["written"] == [], f"second run rewrote pages: {second['written'][:3]}"
    assert blp.check(blp.plan(json.loads(json.dumps(LESSONS))), root=tmp_path) == []


def test_pruning_removes_only_generated_pages(tmp_path):
    """A page we generated and no longer generate goes; a hand-written one stays."""
    files = blp.plan(json.loads(json.dumps(LESSONS)))
    blp.sync(files, root=tmp_path)

    orphan = tmp_path / "docs" / "lessons" / "retired-slug" / "index.html"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_text(f"<html><body>{blp.GENERATOR_MARK}</body></html>", encoding="utf-8")

    # Untracked by the generator AND absent from the manifest: never even a candidate.
    handmade = tmp_path / "docs" / "lessons" / "handwritten" / "index.html"
    handmade.parent.mkdir(parents=True, exist_ok=True)
    handmade.write_text("<html><body>Not ours.</body></html>", encoding="utf-8")

    result = blp.sync(blp.plan(json.loads(json.dumps(LESSONS))), root=tmp_path)
    assert "docs/lessons/retired-slug/index.html" in result["pruned"]
    assert not orphan.exists()
    assert handmade.exists(), "an unmanaged file must never be deleted"


def test_manifest_listed_page_without_the_marker_is_kept(tmp_path):
    """The last line of defence: manifest says ours, marker says someone rewrote it."""
    files = blp.plan(json.loads(json.dumps(LESSONS)))
    blp.sync(files, root=tmp_path)

    victim = tmp_path / "docs" / "lessons" / "manual-override" / "index.html"
    victim.parent.mkdir(parents=True, exist_ok=True)
    victim.write_text("<html><body>Hand-written override.</body></html>", encoding="utf-8")
    manifest_path = tmp_path / blp.MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["pages"] = sorted(manifest["pages"] + ["docs/lessons/manual-override/index.html"])
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = blp.sync(blp.plan(json.loads(json.dumps(LESSONS))), root=tmp_path)
    assert victim.exists(), "a manifest entry without the marker must not be deleted"
    assert "docs/lessons/manual-override/index.html" in result["kept"]


def test_manifest_records_every_page(tmp_path):
    files = blp.plan(json.loads(json.dumps(LESSONS)))
    blp.sync(files, root=tmp_path)
    manifest = json.loads((tmp_path / blp.MANIFEST).read_text(encoding="utf-8"))
    assert manifest["pages"] == sorted(files)
    for path in manifest["pages"]:
        assert (tmp_path / path).exists(), f"manifest lists a page that is not on disk: {path}"


def test_topic_pages_use_the_trust_vocabulary():
    """docs/trust-semantics.md: "indexed" for scale claims, never "verified"."""
    files = blp.plan(json.loads(json.dumps(LESSONS)))
    html = "\n".join(files.values())
    assert "verified failure lesson" not in html
    assert "indexed failure lessons about" in html


def test_locale_dirs_do_not_become_topics():
    lessons = json.loads(json.dumps(LESSONS))
    lessons.append({"title": "Spanish mirror", "domain": "es", "summary": "s", "tags": [], "url": "lessons/es/s.md"})
    files = blp.plan(lessons)
    assert not any(p.startswith("docs/topics/es/") for p in files)


def test_topics_index_exists_for_the_search_page_link():
    """docs/search/index.html links to /topics/, which used to be a live 404."""
    files = blp.plan(json.loads(json.dumps(LESSONS)))
    assert "docs/topics/index.html" in files
    assert 'href="/topics/ops/"' in files["docs/topics/index.html"]
    search = (REPO / "docs" / "search" / "index.html").read_text(encoding="utf-8")
    assert 'href="/topics/"' in search, "search page no longer links /topics/ — keep them in sync"


def test_retitling_a_lesson_keeps_its_url(tmp_path):
    """Sticky slugs: editing a title must not orphan a live URL.

    Deriving the slug from the title on every run is what pruned 88 live pages on
    the first wired run, leaving Google with 404s.
    """
    files, slugs = blp.plan_with_slugs(json.loads(json.dumps(LESSONS)))
    blp.sync(files, root=tmp_path, slugs=slugs)
    assert slugs["bravo"] == "bravo-lesson"

    retitled = json.loads(json.dumps(LESSONS))
    retitled[0]["title"] = "Bravo lesson, renamed at last"
    files2, slugs2 = blp.plan_with_slugs(retitled, known_slugs=slugs)
    blp.sync(files2, root=tmp_path, slugs=slugs2)

    assert slugs2["bravo"] == "bravo-lesson", "the URL must survive a retitle"
    page = tmp_path / "docs/lessons/bravo-lesson/index.html"
    assert page.exists(), "the retitled lesson lost its page"
    assert "renamed at last" in page.read_text(encoding="utf-8"), "content must follow the title"
    assert not (tmp_path / "docs/lessons/bravo-lesson-renamed-at-last").exists()


def test_fresh_lessons_get_a_title_slug():
    new = json.loads(json.dumps(LESSONS)) + [
        {"id": "newcomer", "title": "Brand New Lesson", "domain": "ops",
         "summary": "n", "tags": [], "url": "lessons/ops/n.md"}]
    _files, slugs = blp.plan_with_slugs(new)
    assert slugs["newcomer"] == "brand-new-lesson"


def test_slug_map_is_recorded_in_the_manifest(tmp_path):
    files, slugs = blp.plan_with_slugs(json.loads(json.dumps(LESSONS)))
    blp.sync(files, root=tmp_path, slugs=slugs)
    manifest = json.loads((tmp_path / blp.MANIFEST).read_text(encoding="utf-8"))
    assert manifest["slugs"] == dict(sorted(slugs.items()))
