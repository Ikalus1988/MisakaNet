#!/usr/bin/env python3
"""The `dist` split, pinned: which generated paths leave `main`, and who may write them.

The decision is in `docs/maintainer/dist-branch-cutover.md` and the mechanism is
`.github/workflows/publish-dist.yml`. Three things about them are load-bearing and silent when
wrong, which is why they are asserted here rather than trusted:

* **The generator order.** `scripts/gen_ranking_snapshot.py` was the sixth generator added to the
  documented sequence and the one that was forgotten — `docs/maintainer/handoff-2026-10-11.md` §80
  records the failure: a lesson was merged, `tests/test_ranking_snapshot.py` went red on a fixture
  nobody had regenerated, and the contributor's first instinct was to call it unrelated. The order
  matters because `sync_lesson_count.py` reads `data/lessons.json`, which
  `update_lessons_json.py` writes.
* **`main` is never pushed to.** `tests/test_no_workflow_pushes_to_main.py` is the authority and
  its scanner is imported here rather than re-implemented, so a workflow cannot pass this file
  while failing that one.
* **The two path lists do not overlap, and together they are every generator's output.** A path
  that moves between them silently changes what the pull-request gate demands and what the
  publisher publishes.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflow's steps")

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "publish-dist.yml"
LESSON_GATE = REPO / ".github" / "workflows" / "lesson-gate.yml"

sys.path.insert(0, str(REPO / "scripts" / "ci"))
sys.path.insert(0, str(REPO / "tests"))

import check_dist_diff as cdd  # noqa: E402  (path inserted above)

from test_no_workflow_pushes_to_main import pushes_to_main, step_scripts  # noqa: E402

#: The generators in the order the repository documents them (`scripts/question_autopilot.py` names
#: the first three for contributors; `update-lessons.yml` adds the index rebuild;
#: `docs/maintainer/handoff-2026-10-11.md` §80 is where the sixth came from).
GENERATORS = (
    "update_lessons_json.py",
    "build_lesson_pages.py",
    "export_okf.py",
    "sync_lesson_count.py",
    "rebuild_lessons_index.py",
    "gen_ranking_snapshot.py",
)


def workflow_text() -> str:
    assert WORKFLOW.exists(), f"{WORKFLOW.name} is gone — the dist branch has no publisher"
    return WORKFLOW.read_text(encoding="utf-8")


def on_block(text: str) -> dict:
    """The `on:` mapping. PyYAML resolves the bare key `on` to the boolean True (YAML 1.1)."""
    data = yaml.safe_load(text)
    return data.get("on") or data.get(True) or {}


# ── the trigger set ──────────────────────────────────────────────────────────────────────────────

def test_it_runs_on_every_push_to_main_and_by_hand():
    block = on_block(workflow_text())
    assert block.get("push", {}).get("branches") == ["main"], (
        "`dist` has to follow `main` everywhere — a `paths:` filter here would leave the branch "
        "serving an old hand-written page whenever the push touched something else")
    assert "workflow_dispatch" in block, (
        "no way to republish by hand: the branch is created by the first run, so the cutover's "
        "first step and any recovery from a bad build would need a new push to `main`")


def test_it_has_a_bound_and_a_concurrency_group():
    data = yaml.safe_load(workflow_text())
    job = data["jobs"]["publish"]
    assert job.get("timeout-minutes"), (
        "a job with no bound holds its runner for the platform default (six hours)")
    assert data.get("concurrency", {}).get("group"), (
        "`dist` is a pure function of `main`, so two runs racing on it can only publish the older "
        "corpus over the newer one")


# ── the sequence ─────────────────────────────────────────────────────────────────────────────────

def test_it_runs_the_generators_in_the_documented_order():
    scripts = "\n".join(step_scripts(WORKFLOW))
    positions = []
    for name in GENERATORS:
        found = [m.start() for m in re.finditer(rf"python3 scripts/{re.escape(name)}", scripts)]
        assert found, f"{name} is not run by {WORKFLOW.name} — `dist` would carry a stale artifact"
        positions.append((found[0], name))
    assert [name for _, name in sorted(positions)] == list(GENERATORS), (
        "the generators run out of the documented order: "
        f"{[name for _, name in sorted(positions)]}")


def test_the_lesson_gate_runs_the_generators_that_write_main_side_files():
    """The gate must keep checking what `main` keeps, without the work it no longer owns."""
    scripts = "\n".join(step_scripts(LESSON_GATE))
    assert "check_dist_diff.py main-side" in scripts, (
        "the pull-request gate no longer asserts the files that stay on `main`")
    assert "scripts/build_lesson_pages.py" not in scripts, (
        "`build_lesson_pages.py` writes the generated site, which does not live on `main` any more "
        "— running it here makes the checkout dirty for the right reason and the gate red for the "
        "wrong one")


# ── the branch ───────────────────────────────────────────────────────────────────────────────────

def test_it_pushes_dist_and_never_main():
    scripts = step_scripts(WORKFLOW)
    assert not any(pushes_to_main(s) for s in scripts), (
        "this workflow pushes to `main`; `main`'s ruleset refuses it and "
        "tests/test_no_workflow_pushes_to_main.py exists to catch exactly that")
    joined = "\n".join(scripts)
    assert "git push --force origin dist:dist" in joined, (
        "`dist` is rebuilt from `main`'s HEAD on every run, so the previous `dist` commit is never "
        "a parent of the new one and the push must not expect a fast-forward")


def test_the_commit_message_carries_no_skip_marker():
    """The `data`-branch precedents use `[skip ci]`; copying it here would disable the deploy.

    `update-badges.yml` and `update-smithery-badge.yml` append it because nothing builds `data`.
    `dist` exists *to be built* — Cloudflare Workers Builds deploys from it — so a skip marker in
    the one commit whose job is to trigger that build is the defect, not a convention.
    """
    text = workflow_text()
    commit_lines = [line.strip() for line in text.splitlines() if "git commit" in line]
    assert commit_lines, "no commit command found — the guard is now vacuous"
    assert not any("[skip ci]" in line for line in commit_lines), (
        f"a [skip ci] marker is in the commit that has to trigger the Cloudflare build: "
        f"{commit_lines}")


def test_dist_advances_on_every_push_to_main():
    """`dist` carries `main`'s whole tree, so a source-only push must still move it.

    The six generators are byte-for-byte idempotent on a clean `main` (measured 2026-10-16: an
    unchanged `git status --porcelain` after all six, ~8 s), which makes a "skip when the
    regeneration produced no diff" step look like a harmless optimisation. It is not: a push that
    only edits a hand-written `docs/**` page leaves the generators with nothing to do, and an early
    exit there would leave `dist` serving the **old** page while the run went green. On today's tree
    it would additionally mean the branch is never created at all — which is the state the cutover
    starts from (`docs/maintainer/dist-branch-cutover.md` §4 A2/A3).
    """
    scripts = "\n".join(step_scripts(WORKFLOW))
    commits = [line.strip() for line in scripts.splitlines() if "git commit" in line]
    assert commits, "the publish step no longer commits anything"
    assert any("--allow-empty" in line for line in commits), (
        f"the publish step no longer commits unconditionally, so a push that changes only source "
        f"leaves `dist` behind: {commits}")
    assert "--cached --quiet" not in scripts, (
        "the publish step gates the commit on the regeneration having produced a diff, which "
        "freezes `dist` on the previous source for a source-only push")


def test_the_slug_seed_distinguishes_no_branch_from_a_failed_fetch():
    """An empty slug map is correct on the first run and catastrophic on any other.

    `docs/.generated-pages.json` is the page generator's sticky-slug *state*. Starting without it
    re-derives every lesson URL from its title, which is how 88 live URLs were orphaned once, so
    "`dist` does not exist yet" (normal, first run) must be told apart from "I could not reach
    `origin`" (a transport or credential failure). `git ls-remote --exit-code` exits 2 for the
    first and 128 for the second; collapsing them (`|| true`) turns a failed fetch into a silent
    mass re-addressing of the site.
    """
    scripts = "\n".join(step_scripts(WORKFLOW))
    assert "ls-remote --exit-code --heads origin dist" in scripts, (
        "the seed step no longer asks whether `dist` exists, so an absent branch and a failed fetch "
        "take the same path")
    assert "seeded docs/.generated-pages.json" in scripts, (
        "the seed step no longer reads the manifest out of the previous dist commit, so the first "
        "run after the deletion follow-up starts with an empty slug map")
    assert re.search(r"\*\)[\s\S]{0,500}?exit 1", scripts), (
        "the seed step has no branch for a real failure — only the `--exit-code` value 2 means an "
        "empty slug map is correct")


# ── the two path lists ───────────────────────────────────────────────────────────────────────────

def test_the_lists_are_disjoint_and_cover_every_generator():
    overlap = set(cdd.DIST_ONLY) & set(cdd.MAIN_SIDE)
    assert not overlap, f"a path is in both lists, so its verdict is undefined: {sorted(overlap)}"
    assert cdd.PUBLISHED == cdd.DIST_ONLY + cdd.MAIN_SIDE
    # One pattern per generator, at minimum: a generator whose output is in neither list would make
    # the publisher fail on the very artifact it exists to publish.
    for pattern in ("docs/lessons/**", "docs/topics/**", "docs/sitemap.xml", "docs/_redirects",
                    "docs/.generated-pages.json", "docs/data/lessons.json",
                    "docs/data/lessons-lite.json", "data/lessons.json", "data/okf/lessons.jsonl",
                    "docs/index.html", "docs/llms.txt", "docs/.well-known/llms.txt",
                    "docs/_lessons_count.txt", "lessons/index.md",
                    "tests/fixtures/ranking-snapshot.json"):
        assert pattern in cdd.PUBLISHED, f"{pattern} is not published by anything"


# ── the guard can go red ─────────────────────────────────────────────────────────────────────────

def test_an_unowned_path_fails_the_publisher():
    found = cdd.problems([("M", "scripts/update_lessons_json.py")])
    assert found and "no generator owns it" in found[0], found
    # …and a generated path does not.
    assert cdd.problems([("M", "docs/lessons/x/index.html"), ("A", "data/lessons.json")]) == []


def test_a_deletion_fails_the_publisher():
    """`dist` must contain every path `main` has; a deletion is a 404 nobody reviewed."""
    found = cdd.problems([("D", "docs/index.html")])
    assert found and "deleted" in found[0], found


def test_the_main_side_check_ignores_what_dist_owns():
    porcelain = (
        " M data/lessons.json\n"
        "?? docs/lessons/brand-new/index.html\n"
        " M docs/data/lessons.json\n"
        "?? docs/data/lessons-lite.json\n"
        " M README.md\n"
    )
    found = cdd.main_side_dirty(porcelain)
    assert found == ["data/lessons.json (M)"], found


def test_the_main_side_check_does_not_fire_on_a_clean_tree():
    assert cdd.main_side_dirty("") == []
