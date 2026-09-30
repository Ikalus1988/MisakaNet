#!/usr/bin/env python3
"""Bind the two copies of the corpus the site ships (2026-09-29).

The failure these tests exist to prevent
----------------------------------------
`data/lessons.json` is the canonical snapshot; `docs/data/lessons.json` is what the browser downloads.
Nothing bound them — the site copy existed only as `cp data/lessons.json docs/data/lessons.json` inside
the three-hourly `.github/workflows/build-feed.yml`, and no check looked at both files at once. Between a
regeneration and the next feed run the site served an index that disagreed with the repository it was
built from. Measured 2026-09-29: **426 vs 418** lessons, for about a day, with nothing red. They agreed
again only because the 3-hourly job happened to have run — timing, not a guarantee.

Three assertions, in the order the defect has to be closed:

1. **the repository half** — `compare_index_copies(data/lessons.json, docs/data/lessons.json)` is empty
   on the real checkout;
2. **the guard half** — the same function, handed two files in a temp directory that differ, reports the
   difference. A check that reads the repository and can never go red is the failure mode this
   repository has already paid for (#2045), so the fixture half is not optional;
3. **the producer half** — the generator that owns `data/lessons.json` also writes the site copy, so the
   guarantee comes from the daily `update-lessons.yml` job rather than from a later schedule; and the
   audit job in `.github/workflows/pr-checks.yml` runs `pytest tests/`, so a divergence fails CI.

Run: `python3 -m pytest tests/test_docs_data_copy.py -q`
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts import check_docs_data_copy as cdc  # noqa: E402
from scripts import update_lessons_json as gen  # noqa: E402

CANONICAL = REPO / "data" / "lessons.json"
PUBLISHED = REPO / "docs" / "data" / "lessons.json"
PR_CHECKS = REPO / ".github" / "workflows" / "pr-checks.yml"


def write_index(path: Path, lessons: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lessons, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def lesson(lid: str, **fields) -> dict:
    return {"id": lid, "title": lid.upper(), **fields}


# ── the repository half ────────────────────────────────────────────────────────────────────────

def test_the_site_copy_carries_the_same_lessons_as_the_canonical_index():
    """The gate itself: one corpus, shipped twice, currently the same."""
    problems = cdc.compare_index_copies(CANONICAL, PUBLISHED)
    assert problems == [], (
        "docs/data/lessons.json is not the same corpus as data/lessons.json:\n  - "
        + "\n  - ".join(problems)
        + "\nRegenerate the site copy from the canonical index "
          "(`python3 scripts/update_lessons_json.py` writes both) instead of hand-editing it."
    )


def test_the_repo_gate_is_not_vacuous_on_two_empty_files():
    """Two empty files would also be "in sync" — pin that the real corpus is not empty."""
    canonical = cdc.load_index(CANONICAL)
    published = cdc.load_index(PUBLISHED)
    assert len(canonical) > 100, f"the canonical index holds {len(canonical)} lessons — is it truncated?"
    assert len(published) > 100, f"the site copy holds {len(published)} lessons — is it truncated?"


# ── the guard half: break the artifact in a temp dir, require the check to go red ──────────────

def test_identical_copies_are_reported_as_in_sync(tmp_path):
    """The green direction, so the red cases below mean something."""
    a = write_index(tmp_path / "data" / "lessons.json", [lesson("a"), lesson("b"), lesson("c")])
    b = write_index(tmp_path / "docs" / "data" / "lessons.json", [lesson("a"), lesson("b"), lesson("c")])
    assert cdc.compare_index_copies(a, b) == []


def test_a_lesson_missing_from_the_site_copy_is_reported(tmp_path):
    """The measured 2026-09-29 shape: the canonical index grew, the copy did not."""
    a = write_index(tmp_path / "data" / "lessons.json",
                    [lesson("a"), lesson("b"), lesson("waiting-for-the-feed-run")])
    b = write_index(tmp_path / "docs" / "data" / "lessons.json", [lesson("a"), lesson("b")])
    problems = cdc.compare_index_copies(a, b)
    assert problems, "a lesson present in the canonical index and missing from the site copy passed"
    joined = "\n".join(problems)
    assert "waiting-for-the-feed-run" in joined, f"the failure does not name the missing lesson:\n{joined}"
    assert "3" in joined and "2" in joined, f"the failure does not give both counts:\n{joined}"


def test_a_lesson_that_only_the_site_copy_has_is_reported(tmp_path):
    """The other direction: a rollback of the canonical index leaves the site ahead."""
    a = write_index(tmp_path / "data" / "lessons.json", [lesson("a"), lesson("b")])
    b = write_index(tmp_path / "docs" / "data" / "lessons.json", [lesson("a"), lesson("b"), lesson("ghost")])
    problems = cdc.compare_index_copies(a, b)
    assert problems, "a lesson only the site copy has passed the comparison"
    assert "ghost" in "\n".join(problems)


def test_duplicate_ids_are_reported(tmp_path):
    """Same length and same *set* of ids, different corpus — length+set alone would miss it."""
    a = write_index(tmp_path / "data" / "lessons.json", [lesson("a"), lesson("a"), lesson("b")])
    b = write_index(tmp_path / "docs" / "data" / "lessons.json", [lesson("a"), lesson("b"), lesson("b")])
    problems = cdc.compare_index_copies(a, b)
    assert problems, "duplicated ids on both sides passed the comparison"
    assert any("repeats" in problem for problem in problems), problems


def test_the_same_ids_with_stale_fields_are_reported(tmp_path):
    """A copy that kept every id but froze the rendered fields is stale the same way."""
    a = write_index(tmp_path / "data" / "lessons.json", [lesson("a", preview="the current preview")])
    b = write_index(tmp_path / "docs" / "data" / "lessons.json", [lesson("a", preview="yesterday's")])
    problems = cdc.compare_index_copies(a, b)
    assert problems, "a site copy with the right ids but stale lesson data passed"
    assert any("stale" in problem for problem in problems), problems


@pytest.mark.parametrize("shape,payload", [
    ("a dict wrapping the list", {"lessons": [{"id": "a"}]}),
    ("a bare string entry", ["a"]),
    ("an entry with no id", [{"title": "no id here"}]),
    ("an entry with an empty id", [{"id": ""}]),
    ("invalid JSON", None),
])
def test_a_copy_that_is_not_a_lesson_index_is_a_problem_not_a_crash(tmp_path, shape, payload):
    """A shape it cannot read must be *reported*: a traceback reads as broken infrastructure."""
    a = write_index(tmp_path / "data" / "lessons.json", [lesson("a")])
    b = tmp_path / "docs" / "data" / "lessons.json"
    b.parent.mkdir(parents=True, exist_ok=True)
    b.write_text("{" if payload is None else json.dumps(payload), encoding="utf-8")

    problems = cdc.compare_index_copies(a, b)  # must not raise
    assert problems, f"the published copy shaped as {shape} was reported as in sync"
    assert any("published copy is unusable" in problem for problem in problems), (
        f"the {shape} shape was reported without saying which copy is the unusable one: {problems}"
    )


def test_a_missing_file_is_a_problem_not_a_crash(tmp_path):
    a = write_index(tmp_path / "data" / "lessons.json", [lesson("a")])
    problems = cdc.compare_index_copies(a, tmp_path / "docs" / "data" / "lessons.json")
    assert any("published copy is unusable" in problem for problem in problems), problems


def test_the_cli_exit_code_is_the_gate(tmp_path):
    """`scripts/check_docs_data_copy.py` is runnable standalone; its exit code is the verdict."""
    a = write_index(tmp_path / "data" / "lessons.json", [lesson("a"), lesson("b")])
    b = write_index(tmp_path / "docs" / "data" / "lessons.json", [lesson("a"), lesson("b")])
    assert cdc.main(["--canonical", str(a), "--published", str(b)]) == 0

    write_index(b, [lesson("a")])
    assert cdc.main(["--canonical", str(a), "--published", str(b)]) == 1, (
        "the CLI exited 0 on two copies that differ, so nothing that shells out to it can fail"
    )


# ── the producer half: the job that owns the corpus writes both files ──────────────────────────

def test_the_generator_writes_the_site_copy_too(tmp_path, monkeypatch):
    """Drives the real `main()` against a fixture corpus and requires both files to appear.

    This is the guarantee: `update-lessons.yml` runs this generator daily, so the copy cannot wait for
    the three-hourly feed job. Both index paths are patched (they are module constants precisely so a
    test can do this) — the repository's own files are never touched.
    """
    lessons = tmp_path / "lessons" / "core"
    lessons.mkdir(parents=True)
    (lessons / "fixture-lesson.md").write_text(
        "---\ntitle: Fixture\ndomain: devops\n---\n\n## Problem\n\nx\n\n## Root Cause\n\ny\n"
        "\n## Solution\n\nz\n\n## Verification\n\nw\n",
        encoding="utf-8")

    canonical = tmp_path / "data" / "lessons.json"
    published = tmp_path / "docs" / "data" / "lessons.json"
    # The generator writes into the checkout's `data/`, which exists; a fixture has to make it.
    canonical.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(gen, "LESSONS_DIR", tmp_path / "lessons")
    monkeypatch.setattr(gen, "OUTPUT", canonical)
    monkeypatch.setattr(gen, "PUBLISHED_INDEX", canonical)
    monkeypatch.setattr(gen, "DOCS_INDEX", published)
    # The count surfaces describe the *published* index; refreshing them here would write into the
    # real README for a fixture. The generator's own gate over that is
    # `tests/test_no_test_writes_repo_data.py`.
    monkeypatch.setattr(gen, "refresh_lesson_count_markers", lambda count: None)

    gen.main()

    assert canonical.exists(), "the generator wrote no canonical index"
    assert published.exists(), (
        "the generator wrote data/lessons.json without docs/data/lessons.json — the site copy would "
        "then wait for the three-hourly build-feed run, which is the divergence this pins"
    )
    assert published.read_bytes() == canonical.read_bytes(), "the site copy is not a copy of the index"
    assert cdc.compare_index_copies(canonical, published) == []
    # The browser projection is written by the same run, and it follows the patched site copy: the path is
    # derived from `DOCS_INDEX` at call time, so a redirected run cannot reach into the repository (the
    # first version of that function used an import-time constant and wrote a fixture corpus into
    # `docs/data/lessons-lite.json` during this very suite).
    projection = published.with_name("lessons-lite.json")
    assert projection.exists(), "the generator wrote the corpus but not the browser projection"
    import json as _json
    rows = _json.loads(projection.read_text(encoding="utf-8"))
    assert [r["id"] for r in rows] == [e["id"] for e in _json.loads(canonical.read_text(encoding="utf-8"))]
    assert cdc.compare_lite_projection(canonical, projection) == []


def test_a_redirected_generator_run_leaves_the_site_copy_alone(tmp_path, monkeypatch):
    """`MISAKANET_LESSONS_INDEX` (what conftest sets) must not rewrite the published copy.

    `tests/conftest.py` redirects every test run's `data/lessons.json`; if the redirect did not also
    cover this new write, the suite would rewrite `docs/data/lessons.json` with the fixture index and
    the next test to compare the two files would fail for a reason nobody caused.
    """
    lessons = tmp_path / "lessons" / "core"
    lessons.mkdir(parents=True)
    (lessons / "fixture-lesson.md").write_text(
        "---\ntitle: Fixture\ndomain: devops\n---\n\n## Problem\n\nx\n\n## Root Cause\n\ny\n"
        "\n## Solution\n\nz\n\n## Verification\n\nw\n",
        encoding="utf-8")

    elsewhere = tmp_path / "elsewhere" / "lessons.json"
    elsewhere.parent.mkdir(parents=True, exist_ok=True)
    site_copy = tmp_path / "docs" / "data" / "lessons.json"
    site_copy.parent.mkdir(parents=True)
    site_copy.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(gen, "LESSONS_DIR", tmp_path / "lessons")
    monkeypatch.setattr(gen, "OUTPUT", elsewhere)
    monkeypatch.setattr(gen, "DOCS_INDEX", site_copy)

    gen.main()

    assert elsewhere.exists(), "the redirected run wrote no index at all"
    assert site_copy.read_text(encoding="utf-8") == "[]\n", (
        "a run whose index went somewhere else still rewrote docs/data/lessons.json"
    )
    assert not site_copy.with_name("lessons-lite.json").exists(), (
        "a run whose index went somewhere else still wrote the browser projection"
    )


# ── which job runs this file ───────────────────────────────────────────────────────────────────

def test_the_audit_job_runs_pytest_over_the_whole_tests_directory():
    """A new test file is only a gate if the required job collects it.

    `pr-checks.yml`'s `audit` job is the required check, and its `pytest` step is the thing that would
    run this file. It must target the `tests/` *directory*: an explicit file list (the shape that once
    left `workers/d1-fts-search.test.mjs` red on main for months) would silently not collect a test
    added later, which is exactly how a gate stops being a gate.
    """
    yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflow (a core requirement)")
    workflow = yaml.safe_load(PR_CHECKS.read_text(encoding="utf-8"))
    for step in workflow["jobs"]["audit"]["steps"]:
        if step.get("id") == "pytest":
            break
    else:
        raise AssertionError("the `Run Test Suite` step (id: pytest) disappeared from pr-checks.yml")

    # Drop comment lines and shell line-continuations: a target named only inside a comment must not
    # satisfy this, and the folded command is what actually runs.
    lines = [line for line in (step.get("run") or "").splitlines()
             if not line.lstrip().startswith("#")]
    tokens = " ".join(lines).replace("\\", " ").split()
    assert "tests/" in tokens, (
        "the audit job's pytest invocation no longer collects the tests/ directory, so a test added "
        f"later would not run on any PR. Command: {' '.join(tokens)}"
    )


# ── the browser projection (2026-09-30) ─────────────────────────────────────────────────────────────
# Both search pages read `title/summary/domain/tags` and nothing else, so they now fetch
# `docs/data/lessons-lite.json` (149 KB raw / 60 KB gzip) instead of the corpus (1.32 MB raw / 418 KB) —
# 7× less for an identical local search. The projection is written by the job that owns the corpus, and
# these tests hold the three relations that make it a *view* rather than a second dataset.

def test_the_browser_projection_is_a_view_of_the_corpus():
    problems = cdc.compare_lite_projection(cdc.CANONICAL, cdc.LITE)
    assert problems == [], problems
    size = cdc.LITE.stat().st_size
    assert size < cdc.LITE_MAX_BYTES, (
        f"the projection grew to {size:,} bytes; it exists to be far smaller than the corpus")


def test_the_projection_rule_notices_a_missing_lesson(tmp_path):
    """Guard the guard: this check reads the repository, so its red case needs a fixture."""
    canonical = write_index(tmp_path / "data" / "lessons.json", [lesson("a"), lesson("b")])
    thin = write_index(tmp_path / "lite.json", [{"id": "a", "title": "A", "summary": "s",
                                                "domain": "d", "tags": []}])
    problems = cdc.compare_lite_projection(canonical, thin)
    assert any("missing from the projection" in p for p in problems), problems


def test_the_projection_rule_notices_the_size_regression_it_exists_to_prevent(tmp_path):
    """`preview` is why the corpus was 1.32 MB; a projection that carries it again is the regression."""
    rows = [{"id": "a", "title": "A", "summary": "s", "domain": "d", "tags": [], "preview": "x" * 400_000}]
    canonical = write_index(tmp_path / "data" / "lessons.json", [lesson("a")])
    fat = write_index(tmp_path / "lite.json", rows)
    problems = cdc.compare_lite_projection(canonical, fat)
    assert any("carries ['preview']" in p for p in problems), problems
    assert any("over the" in p and "ceiling" in p for p in problems), (
        "the ceiling is what catches a *new* long field the field list cannot know about: " + str(problems))


def test_the_projection_rule_accepts_the_same_ids_in_another_order(tmp_path):
    """Order is the corpus's business, not the projection's — a reshuffle must not read as drift."""
    canonical = write_index(tmp_path / "data" / "lessons.json", [lesson("a"), lesson("b")])
    shuffled = write_index(tmp_path / "lite.json", [
        {"id": "b", "title": "B", "summary": "s", "domain": "d", "tags": []},
        {"id": "a", "title": "A", "summary": "s", "domain": "d", "tags": []},
    ])
    assert cdc.compare_lite_projection(canonical, shuffled) == []


def test_both_search_pages_use_the_projection_and_keep_the_corpus_as_a_fallback():
    """The wiring, checked on the two files a browser actually loads."""
    for rel in ("docs/index.html", "docs/search/index.html"):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert "lessons-lite.json" in text, f"{rel} does not load the browser projection"
        assert "lessons.json" in text, f"{rel} dropped the corpus fallback"
    # and the corpus URL must not be the one the local search fetches first
    index = (REPO / "docs" / "index.html").read_text(encoding="utf-8")
    assert 'return LESSONS_LITE_URL;' in index, (
        "the homepage's getLessonsUrl() must return the projection; the corpus is the fallback")
    search = (REPO / "docs" / "search" / "index.html").read_text(encoding="utf-8")
    assert "fetchLessonsOnce(LESSONS_LITE_URL)" in search, "the search page must try the projection first"
    assert "fetchLessonsOnce(LESSONS_FULL_URL)" in search, (
        "the search page must fall back to the corpus when the projection is missing")
    # …and neither page may fan out per item while doing it: this site forbids that pattern outright
    # (`tests/test_site_request_fanout.py`), and the first version of this fallback was a `for … of` loop.
    for rel, text in (("docs/index.html", index), ("docs/search/index.html", search)):
        assert "for (const url of [LESSONS_LITE_URL" not in text, f"{rel} reintroduced the fan-out loop"


def test_the_search_page_fetches_the_lesson_body_instead_of_shipping_every_body():
    """`preview` used to ride along in the corpus (~1.09 MB of it) for one inline panel."""
    search = (REPO / "docs" / "search" / "index.html").read_text(encoding="utf-8")
    assert "fetchLessonBody" in search, "the on-demand body fetch disappeared"
    assert "misakanet_get_lesson" in search, "the panel must read the documented public read path"
    assert "lesson.preview" in search or "preview" in search, (
        "the panel should still accept a projection/corpus that carries preview, so the fallback works")
