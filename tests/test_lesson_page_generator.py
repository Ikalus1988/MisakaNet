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
import subprocess
import sys
from pathlib import Path

import pytest

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


# ── a search hit's id must be a working URL ─────────────────────────────────────────────────────────
# Measured on the live site 2026-09-29: 73 of 426 lessons have a frontmatter `id` that differs from their
# title-derived page slug, so `/lessons/<id>/` answered **404** for 17% of the corpus while the page existed
# under another name — and `docs/llms.txt` promises `https://misakanet.org/lessons/<slug>/`, which is what a
# consumer has after a `misakanet_search` call. The alias pages below make the id resolve; these tests pin
# both the page and the two properties that keep it harmless (canonical to the real page, absent from the
# sitemap).

def _plan(lessons):
    files, slugs = blp.plan_with_slugs(lessons, {})
    return files, slugs


def test_an_id_that_differs_from_its_slug_gets_a_redirect_page():
    lessons = [{"id": "short-id", "title": "A Much Longer Title That Becomes The Page Slug", "domain": "x"}]
    files, _ = _plan(lessons)
    slug = blp.slugify("A Much Longer Title That Becomes The Page Slug")
    assert f"docs/lessons/{slug}/index.html" in files, sorted(files)
    assert f"docs/lessons/short-id/index.html" in files, (
        "the id `misakanet_search` returns must resolve, or the documented page URL 404s")

    alias = files["docs/lessons/short-id/index.html"]
    # Site-relative since 2026-09-29 (see the absolute-origin rule below): `rel="canonical"` resolves a
    # relative URL against the page, and the origin was the shape a secret-scanning heuristic matched.
    assert f'<link rel="canonical" href="/lessons/{slug}/">' in alias, alias
    assert f'meta http-equiv="refresh" content="0; url=/lessons/{slug}/"' in alias, alias
    assert blp.GENERATOR_MARK in alias, (
        "without the marker the generator does not own the file and can never prune it")


def test_no_alias_is_planned_when_the_id_is_already_the_slug():
    title = "Some Lesson Title"
    lessons = [{"id": blp.slugify(title), "title": title, "domain": "x"}]
    files, _ = _plan(lessons)
    lesson_paths = {p for p in files if p.startswith("docs/lessons/")}
    assert lesson_paths == {f"docs/lessons/{blp.slugify(title)}/index.html"}, lesson_paths


def test_a_real_page_wins_over_an_alias_at_the_same_path():
    """A lesson whose *id* equals another lesson's *slug* must not have its page overwritten."""
    lessons = [
        {"id": "collides-with-a-slug", "title": "First Lesson", "domain": "x"},
        {"id": "second", "title": "Collides With A Slug", "domain": "x"},
    ]
    files, _ = _plan(lessons)
    real = files["docs/lessons/collides-with-a-slug/index.html"]
    assert "canonical" in real and "http-equiv" not in real, (
        "the real page for lesson 2 was replaced by lesson 1's redirect: " + real[:200])


def test_the_alias_is_absent_from_the_sitemap():
    lessons = [{"id": "short-id", "title": "A Much Longer Title That Becomes The Page Slug", "domain": "x"}]
    files, _ = _plan(lessons)
    sitemap = files[blp.SITEMAP.as_posix()]
    assert "/lessons/short-id/" not in sitemap, (
        "the alias is a redirect, not a second page — putting it in the sitemap asks crawlers to index it")
    assert f"/lessons/{blp.slugify(lessons[0]['title'])}/" in sitemap, sitemap[:400]


def test_every_lesson_id_has_a_generated_page_on_disk():
    """The property the live site needs: after `build_lesson_pages.py`, every id resolves.

    This is the repository-side version of "`/lessons/<id>/` is not a 404" — the docs/ tree is what gets
    deployed, so a missing file here is a 404 there.
    """
    rows = json.loads((REPO / "data" / "lessons.json").read_text(encoding="utf-8"))
    missing = [row["id"] for row in rows
               if not (REPO / "docs" / "lessons" / row["id"] / "index.html").exists()]
    assert not missing, (
        f"{len(missing)} lesson ids have no page at `/lessons/<id>/` (run build_lesson_pages.py): "
        f"{missing[:5]}")


# ── the two properties the plan cannot express (2026-09-30) ───────────────────────────────────────
#
# `check()` compares the generator's plan against the pages the generator wrote. Both sides come
# from `data/lessons.json`, so a lesson the plan never contained — one that cannot be given a page —
# is invisible to it, and a manifest that lost a slug entry is invisible too. Neither is the same
# question as the id-alias test above: that one asks whether `/lessons/<id>/` exists, while the live
# URL is `/lessons/<slug>/`, and the slug is knowable only from the manifest.
#
# The two properties are therefore tested, and gated by `main()`, as relations over the corpus and
# the manifest rather than over the plan.

# The two shapes of "cannot be given a page" that reach the generator in practice: a `title:` key
# with an empty value (PyYAML gives None), and a title that is long enough for `lesson_gate.py`
# but slugifies to nothing because `slugify()` strips every non-word character.
UNTITLED = {"id": "untitled-lesson-probe", "title": "", "domain": "ops", "summary": "p",
            "tags": [], "url": "lessons/ops/untitled-lesson-probe.md"}
EMOJI_TITLED = {"id": "emoji-title-probe", "title": "\U0001F525" * 5, "domain": "ops", "summary": "p",
                "tags": [], "url": "lessons/ops/emoji-title-probe.md"}


def _run_cli(root: Path, *args: str) -> subprocess.CompletedProcess:
    """The real CLI against a scratch root — `main()` is the gate, not the helper."""
    return subprocess.run(
        [sys.executable, str(REPO / "scripts" / "build_lesson_pages.py"), *args, "--root", str(root)],
        cwd=REPO, capture_output=True, text=True, timeout=300)


def _write_corpus(root: Path, lessons: list) -> None:
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data" / "lessons.json").write_text(json.dumps(lessons, ensure_ascii=False), encoding="utf-8")


def test_an_unpageable_lesson_is_a_named_failure_not_a_silent_skip(tmp_path):
    """A lesson that can never get a page is a red gate that names it, in both modes.

    Measured on the un-fixed script (2026-09-30): a 3-lesson corpus holding one untitled lesson and
    one emoji-titled lesson planned **1** page, wrote it, and exited 0 — and `--check` then printed
    "✅ every generated page matches the index", because the plan and the disk agreed with each other
    while two corpus lessons had no page at all.
    """
    corpus = json.loads(json.dumps(LESSONS)) + [dict(UNTITLED), dict(EMOJI_TITLED)]
    _write_corpus(tmp_path, corpus)

    red = _run_cli(tmp_path, "--check")
    assert red.returncode == 1, red.stdout + red.stderr
    # Named by id, both of them — the ids are the fact this asserts, not the sentence around them.
    assert UNTITLED["id"] in red.stderr and EMOJI_TITLED["id"] in red.stderr, red.stderr

    # Write mode refuses too, before it writes anything: a plan that silently drops lessons is the
    # half-synced tree `update_lessons_json.py` already refuses to commit.
    red_write = _run_cli(tmp_path)
    assert red_write.returncode == 1, red_write.stdout + red_write.stderr
    assert not (tmp_path / "docs").exists(), "pages were written for a corpus holding unpageable lessons"

    # Green once the two titles are real, and then a page exists for each of the three lessons.
    corpus[-2]["title"] = "A probe lesson that now has a title"
    corpus[-1]["title"] = "Fire probe lesson"
    _write_corpus(tmp_path, corpus)
    green = _run_cli(tmp_path)
    assert green.returncode == 0, green.stdout + green.stderr
    assert _run_cli(tmp_path, "--check").returncode == 0
    for slug in ("bravo-lesson", "a-probe-lesson-that-now-has-a-title", "fire-probe-lesson"):
        assert (tmp_path / "docs" / "lessons" / slug / "index.html").is_file(), slug


def test_every_corpus_lesson_has_a_page_on_disk():
    """The gate, over the real corpus: corpus + recorded slug map -> a page must exist.

    Independent of the generator's own plan on purpose. `check()` compares the plan to the pages the
    plan wrote, so it cannot notice a lesson that was never planned; this walks `data/lessons.json`
    and resolves each lesson through `docs/.generated-pages.json` (or the `/lessons/<id>/` alias).
    """
    lessons = json.loads((REPO / "data" / "lessons.json").read_text(encoding="utf-8"))
    assert len(lessons) > 400, f"only {len(lessons)} lessons — the corpus moved, not the pages"
    assert len(blp.load_slug_map(REPO)) > 400, "the slug map is empty — this gate would pass vacuously"
    assert blp.corpus_page_problems(lessons, root=REPO) == []


def test_the_corpus_page_gate_reports_a_missing_page(tmp_path):
    """Guard the guard: the relation goes red in each shape it claims to cover."""
    lessons = json.loads(json.dumps(LESSONS))
    files, slugs = blp.plan_with_slugs(lessons, {})
    blp.sync(files, root=tmp_path, slugs=slugs)
    assert blp.corpus_page_problems(LESSONS, root=tmp_path) == []

    # 1. The page at the recorded (live) slug is gone, and so is the id alias: the lesson is a 404
    #    under both of its names.
    slug_page = tmp_path / "docs" / "lessons" / "bravo-lesson" / "index.html"
    alias = tmp_path / "docs" / "lessons" / "bravo" / "index.html"
    assert alias.is_file(), "no alias page for an id that differs from its slug — the alias writer moved"
    slug_page.unlink()
    alias.unlink()
    problems = blp.corpus_page_problems(LESSONS, root=tmp_path)
    assert len(problems) == 1, problems
    assert "bravo" in problems[0] and "bravo-lesson/index.html" in problems[0], problems[0]

    # 2. The id alias alone satisfies this gate (2026-09-29 alias pages; the task's "either the slug
    #    page or the id alias"). It must not be allowed to hide the missing live page, and it cannot:
    #    the alias is a redirect to `/lessons/<slug>/`, so the plan-versus-disk gate in the same
    #    `--check` run still holds the slug page and reports it.
    alias.write_text(files["docs/lessons/bravo/index.html"], encoding="utf-8")
    assert blp.corpus_page_problems(LESSONS, root=tmp_path) == []
    assert blp.check(files, root=tmp_path) == [f"{slug_page.relative_to(tmp_path).as_posix()}: "
                                              "missing (would be created)"], blp.check(files, root=tmp_path)

    # 3. A lesson the slug map does not know is a failure even when a page is on disk: the recorded
    #    slug is what keeps a live URL sticky, and re-deriving it is how 88 pages were orphaned once.
    manifest_path = tmp_path / blp.MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["slugs"].pop("bravo")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    problems = blp.corpus_page_problems(LESSONS, root=tmp_path)
    assert len(problems) == 1 and "bravo" in problems[0], problems

    # 4. A lesson new to the corpus that the generator has never planned — the "never planned at
    #    all" case `check()` cannot see, because nothing in the plan mentions it.
    newcomer = {"id": "newcomer", "title": "Brand New Lesson", "domain": "ops", "summary": "n",
                "tags": [], "url": "lessons/ops/n.md"}
    problems = blp.corpus_page_problems(LESSONS + [newcomer], root=tmp_path)
    assert [p for p in problems if "newcomer" in p], problems

    # 5. An *empty* recorded slug is not a recorded slug. `plan_with_slugs` writes `""` into the slug
    #    map for a title that slugifies to nothing, and `""` resolves to `docs/lessons/index.html` —
    #    the lessons directory index — which must never be mistaken for a lesson's page. Found
    #    2026-09-30 by removing the unpageable gate and watching this check go green off that file.
    (tmp_path / "docs" / "lessons" / "index.html").write_text("<html>directory index</html>",
                                                             encoding="utf-8")
    manifest["slugs"]["bravo"] = ""
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    problems = blp.corpus_page_problems(LESSONS, root=tmp_path)
    assert len(problems) == 1 and "bravo" in problems[0], problems

    # 6. A manifest with no slug map at all is one named problem, not a page-missing claim about
    #    every lesson whose id differs from its slug.
    manifest_path.unlink()
    problems = blp.corpus_page_problems(LESSONS, root=tmp_path)
    assert len(problems) == 1 and blp.MANIFEST.as_posix() in problems[0], problems


def test_a_lesson_merge_regenerates_the_pages():
    """The writer, so "a merged lesson gets a page" has a mechanism rather than a habit.

    Measured 2026-09-30: `build_lesson_pages.py` ran only from `update-lessons.yml`'s daily cron
    (plus `--check` from `docs.yml`, which filters on `docs/**` and compares the plan to the pages
    the plan wrote), while `sync-d1.yml` made a merged lesson searchable on the push itself. A
    search hit therefore led to a page that did not exist yet, for up to a day.
    """
    yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflow trigger block")
    workflow = REPO / ".github" / "workflows" / "update-lessons.yml"
    data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    on = data.get("on") or data.get(True) or {}  # PyYAML resolves the bare key `on` to True
    assert "push" in on, (
        "update-lessons.yml no longer runs on a push, so a merged lesson has no page until the "
        "daily cron — the gap this trigger closes")
    push = on["push"] or {}
    assert "main" in (push.get("branches") or []), push
    assert "lessons/**" in (push.get("paths") or []), push
    steps = next(iter(data["jobs"].values()))["steps"]
    assert any("build_lesson_pages.py" in str(step.get("run") or "") for step in steps), (
        "the push-triggered run no longer regenerates the pages")



# ── generated redirect pages carry no absolute URL ──────────────────────────────────────────────────
# GitHub's secret-scanning heuristic (`HARDCODED_SECRET`, tool `plugin-scanner 2.2.0`) flagged two alias
# pages on 2026-09-29 — `docs/lessons/idempotent-task-claim/index.html:6` and
# `docs/lessons/disk-full-agent-tmp-gc/index.html:6`. Both lines were the *canonical* link, and both slugs
# are ordinary lesson titles that happen to contain secret-flavoured words ("Idempotent task claim **keys**
# for snipers", "Disk full from agent tmp dirs — **GC pattern**"). Nothing was leaked: the lesson sources
# carry no credential-shaped string and `scripts/check_published_secrets.py` is green over every published
# prose file. The canonical is now site-relative (valid for `rel="canonical"`), so a generated file whose
# only content is a redirect no longer contains an absolute URL — and this rule keeps that shape from coming
# back, because the next title with "token" or "secret" in it would trip the same heuristic.

def test_generated_redirect_pages_do_not_embed_an_absolute_origin():
    aliases = [p for p in (REPO / "docs" / "lessons").glob("*/index.html")
               if "Moved —" in p.read_text(encoding="utf-8")[:200]]
    assert aliases, "no alias pages found — this rule has lost its subject (did the generator change?)"
    offenders = []
    for page in aliases:
        text = page.read_text(encoding="utf-8")
        for origin in blp.SITE_URL, "http://", "https://raw.githubusercontent.com":
            if origin in text:
                offenders.append(f"{page.relative_to(REPO).as_posix()}: {origin}")
    assert not offenders, (
        "these generated redirect pages embed an absolute URL; an ordinary lesson title that slugifies to a "
        "secret-flavoured string then reads as a hardcoded endpoint to a scanner: " + "; ".join(offenders[:5]))


def test_the_relative_canonical_rule_notices_an_absolute_origin():
    """Guard: the rule reads the repository, so its failure mode needs a fixture."""
    def has_absolute(text: str) -> bool:
        return any(origin in text for origin in (blp.SITE_URL, "http://", "https://raw.githubusercontent.com"))

    assert has_absolute(f'<link rel="canonical" href="{blp.SITE_URL}/lessons/x/">'), "fixture must trip the rule"
    assert not has_absolute('<link rel="canonical" href="/lessons/x/">'), "a relative canonical is fine"
